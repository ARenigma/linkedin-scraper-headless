import os
import json
import time
import threading
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd

from config import logger, RESUME_FILE, OUTPUT_FOLDER, RESUME_TIMEOUT
from upload_to_drive import upload_to_drive

class StateManager:
    """Handles state management for the LinkedIn scraper."""
    
    def __init__(self):
        self.filename = None
        self.last_save_time = time.time()
        self.final_upload_completed = False
        
    def save_resume_point(self, combo_counter: int, keyword: str, location: str) -> None:
        """
        Save the current scraping state to resume later.
        
        Args:
            combo_counter: Current combination counter
            keyword: Current keyword being processed
            location: Current location being processed
        """
        state = {
            "combo_counter": combo_counter,
            "keyword": keyword,
            "location": location,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            with open(RESUME_FILE, "w") as f:
                json.dump(state, f)
            logger.info(f"Saved resume point at combo #{combo_counter}: '{keyword}' in '{location}'")
        except Exception as e:
            logger.warning(f"Failed to save resume point: {e}")
            
    def load_resume_point(self) -> Optional[Dict[str, Any]]:
        """
        Load previously saved resume point if available.
        
        Returns:
            Dictionary with resume state or None if no resume file exists
        """
        if not os.path.exists(RESUME_FILE):
            return None
            
        try:
            with open(RESUME_FILE, "r") as f:
                state = json.load(f)
                logger.info(f"Found resume point: combo #{state['combo_counter']} at '{state['keyword']}' / '{state['location']}'")
                return state
        except Exception as e:
            logger.warning(f"Failed to load resume point: {e}")
            return None
            
    def delete_resume_point(self) -> None:
        """Delete resume file after complete scraping."""
        if os.path.exists(RESUME_FILE):
            try:
                os.remove(RESUME_FILE)
                logger.info("Deleted resume point")
            except Exception as e:
                logger.warning(f"Failed to delete resume file: {e}")
                
    def handle_resume_decision(self) -> Optional[Dict[str, Any]]:
        """
        If resume file exists, ask user if they want to resume or start fresh.
        
        Returns:
            Resume state dictionary or None to start fresh
        """
        if not os.path.exists(RESUME_FILE):
            return None
            
        try:
            state = self.load_resume_point()
            if not state:
                return None
                
            # Make the resume prompt more visible
            print("\n" + "=" * 80)
            print("RESUME FILE FOUND!".center(80))
            print("=" * 80)
            print(f"Last scrape stopped at: Keyword '{state['keyword']}' in '{state['location']}'")
            print(f"Combo #{state['combo_counter']}")
            if state.get('timestamp'):
                print(f"Timestamp: {state['timestamp']}")
            
            # Check for existing output files to give more context
            date_folder = datetime.now().strftime("%Y-%m-%d")
            full_output_dir = os.path.join(OUTPUT_FOLDER, date_folder)
            
            if os.path.exists(full_output_dir):
                files = [f for f in os.listdir(full_output_dir) if f.endswith('.xlsx')]
                interim_files = [f for f in files if '_INTERIM' in f]
                complete_files = [f for f in files if '_COMPLETE' in f]
                error_files = [f for f in files if '_ERROR' in f]
                
                if interim_files:
                    print(f"\nFound {len(interim_files)} interim result file(s) from previous runs.")
                    print(f"Most recent: {interim_files[-1]}")
                    
                if error_files:
                    print(f"\nFound {len(error_files)} error result file(s) from previous runs.")
                    print(f"Most recent: {error_files[-1]}")
                    print("These files were saved when the scraper encountered fatal errors.")
                    
                if complete_files:
                    print(f"\nFound {len(complete_files)} completed result file(s) from previous runs.")
                    print(f"Most recent: {complete_files[-1]}")
                    
            print("=" * 80)
            
            # Set up a timer with user input
            user_choice = {"answer": None}

            def ask_input():
                choice = input("\nWould you like to (R)esume or (F)resh start? [R/F] ").strip().lower()
                user_choice["answer"] = choice

            # Create and start the input thread
            input_thread = threading.Thread(target=ask_input)
            input_thread.daemon = True
            input_thread.start()
            
            # Wait for input with timeout
            timeout = RESUME_TIMEOUT  # seconds
            start_time = time.time()
            remaining = timeout
            
            # Show countdown while waiting for input
            while input_thread.is_alive() and remaining > 0:
                sys.stdout.write(f"\rAuto-starting fresh in {int(remaining)} seconds... ")
                sys.stdout.flush()
                time.sleep(0.5)
                remaining = timeout - (time.time() - start_time)
            
            # Clear the countdown line
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()
            
            # Process the choice
            choice = user_choice["answer"]
            
            if choice == "r":
                logger.info("Resuming previous scrape")
                return state
            elif choice == "f":
                logger.info("Starting fresh as selected by user")
                self.delete_resume_point()
                return None
            else:
                # Timeout or invalid input
                logger.info("No valid input received — starting fresh automatically")
                self.delete_resume_point()
                return None
                
        except Exception as e:
            logger.warning(f"Failed to process resume point: {e}")
            return None
            
    def save_jobs_no_upload(self, jobs: List[Dict[str, Any]], filename: Optional[str] = None) -> str:
        """
        Save jobs to XLSX file without uploading to Drive (for periodic saves).
        
        Args:
            jobs: List of job dictionaries to save
            filename: Optional filename to save to (will overwrite)
            
        Returns:
            Path to saved file
        """
        if not jobs:
            logger.warning("No jobs to save")
            return self.filename or ""
        
        # Create dated folder inside output
        date_folder = datetime.now().strftime("%Y-%m-%d")
        full_output_dir = os.path.join(OUTPUT_FOLDER, date_folder)
        os.makedirs(full_output_dir, exist_ok=True)

        if filename is None:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H%M")
            filename = os.path.join(full_output_dir, f"linkedin_jobs_{timestamp}.xlsx")
        
        try:
            # Remove duplicate jobs by Job ID if available
            unique_jobs = []
            job_ids = set()
            
            for job in jobs:
                job_id = job.get("Job ID")
                # If job has an ID and it's not already in our set, add it to unique jobs
                if job_id and job_id not in job_ids:
                    job_ids.add(job_id)
                    unique_jobs.append(job)
                # If job has no ID, keep it (old behavior)
                elif not job_id:
                    unique_jobs.append(job)
                
            if len(unique_jobs) < len(jobs):
                logger.info(f"Removed {len(jobs) - len(unique_jobs)} duplicate jobs by Job ID")
                jobs = unique_jobs
            
            # Create DataFrame
            df = pd.DataFrame(jobs)
            
            # Create a Pandas Excel writer using the openpyxl engine
            writer = pd.ExcelWriter(filename, engine='openpyxl')
            
            # Write DataFrame to Excel
            df.to_excel(writer, index=False, sheet_name='LinkedIn Jobs')
            
            # Get the worksheet object
            worksheet = writer.sheets['LinkedIn Jobs']
            
            # Import necessary openpyxl styles for formatting
            from openpyxl.styles import Font, PatternFill
            
            # Create hyperlink font style
            hyperlink_font = Font(color="0563C1", underline="single")
            
            # Identify URL columns for hyperlinking
            url_columns = []
            for i, col in enumerate(df.columns):
                if 'url' in col.lower() or 'link' in col.lower():
                    url_columns.append((i, col))
            
            # Add hyperlinks to URL columns
            for row_num in range(2, len(df) + 2):  # +2 because Excel is 1-indexed and has a header row
                for col_idx, col_name in url_columns:
                    col_letter = chr(65 + col_idx)  # Convert to Excel column letter (A, B, C, etc.)
                    cell_pos = f"{col_letter}{row_num}"
                    url_value = df.iloc[row_num-2, col_idx]
                    
                    if url_value and isinstance(url_value, str) and (url_value.startswith('http://') or url_value.startswith('https://')):
                        # Set hyperlink and formatting
                        worksheet[cell_pos].hyperlink = url_value
                        worksheet[cell_pos].font = hyperlink_font
            
            # Save the Excel file
            writer.close()
            
            self.filename = filename
            logger.info(f"Saved {len(jobs)} jobs to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save jobs: {e}")
            
        return self.filename
    
    def save_jobs(self, jobs: List[Dict[str, Any]], filename: Optional[str] = None, is_final: bool = True) -> str:
        """
        Save jobs to XLSX file and optionally upload to Drive (for final saves).
        
        Args:
            jobs: List of job dictionaries to save
            filename: Optional filename to save to (will overwrite)
            is_final: Whether this is the final save that should be uploaded
            
        Returns:
            Path to saved file
        """
        # First, save the file locally
        saved_file = self.save_jobs_no_upload(jobs, filename)
        
        # Upload to Drive ONLY if it's an interim save (not the final complete save)
        # Final complete files will be uploaded after renaming in rename_file_complete
        if is_final and not self.final_upload_completed and saved_file:
            # Only upload if this is an interrupted save (not a successful completion)
            # Check if we're in a keyboard interrupt handler
            import inspect
            stack = inspect.stack()
            caller_name = stack[1].function if len(stack) > 1 else ""
            
            if caller_name == "handle_keyboard_interrupt":
                # Upload to Google Drive for interrupted saves
                drive_link = upload_to_drive(saved_file)
                if drive_link:
                    logger.info(f"INTERIM RESULTS: File uploaded to Google Drive: {drive_link}")
                    self.final_upload_completed = True
            
        return saved_file
    
    def save_jobs_periodic(self, jobs: List[Dict[str, Any]], interval_minutes: int = 10) -> Optional[str]:
        """
        Track time and periodically save jobs.
        
        Args:
            jobs: List of job dictionaries to save
            interval_minutes: How often to save (in minutes)
            
        Returns:
            Path to saved file or None if no save occurred
        """
        current_time = time.time()
        
        # If enough time has passed or it's the first save
        if current_time - self.last_save_time >= interval_minutes * 60:
            if jobs:
                # For periodic saves, use save_jobs_no_upload to avoid multiple uploads
                if interval_minutes == 0:  # Force immediate save without upload
                    self.filename = self.save_jobs(jobs, self.filename, is_final=False)
                else:  # Regular periodic save
                    self.filename = self.save_jobs_no_upload(jobs, self.filename)
                    
                logger.info(f"Auto-saved at {datetime.now().strftime('%H:%M:%S')}")
                self.last_save_time = current_time
                return self.filename
        
        return None
    
    def rename_file_complete(self) -> Optional[str]:
        """
        Rename the output file to indicate the scraping completed successfully.
        
        Returns:
            Path to renamed file or None if rename failed
        """
        if not self.filename or not os.path.exists(self.filename):
            return None
            
        base, ext = os.path.splitext(self.filename)
        new_filename = f"{base}_COMPLETE{ext}"
        
        try:
            # First try using os.rename which should replace the file
            try:
                os.rename(self.filename, new_filename)
            except Exception as rename_error:
                # If rename fails (can happen on some Windows setups), create a copy and delete original
                logger.debug(f"Regular rename failed: {rename_error}. Trying copy and delete approach.")
                import shutil
                shutil.copy2(self.filename, new_filename)
                
                # Make sure the copy succeeded before deleting original
                if os.path.exists(new_filename):
                    # Delete the original file to avoid duplicates
                    os.remove(self.filename)
                else:
                    raise Exception("Failed to create completed file copy")
                
            logger.info(f"Renamed file to {new_filename} to indicate complete scraping")
            self.filename = new_filename
            
            # Always upload the final complete file to Google Drive
            # Reset the upload flag to ensure we upload the completed file
            self.final_upload_completed = False
            
            # Upload the renamed complete file
            drive_link = upload_to_drive(new_filename)
            if drive_link:
                logger.info(f"COMPLETE RESULTS: File uploaded to Google Drive: {drive_link}")
                self.final_upload_completed = True
            
            return new_filename
        except Exception as e:
            logger.error(f"Failed to rename file: {e}")
            return self.filename
            
    def handle_keyboard_interrupt(self, jobs: List[Dict[str, Any]]) -> None:
        """
        Handle keyboard interrupt (CTRL+C) gracefully with clear resume instructions.
        
        Args:
            jobs: List of job dictionaries to save before exiting
        """
        print("\n" + "=" * 80)
        print("SCRAPING PAUSED - YOU CAN RESUME LATER".center(80))
        print("=" * 80)
        print("You pressed Ctrl+C to stop the scraping process.")
        print("The current progress has been saved.")
        print("Run the script again to see the resume option.")
        print("=" * 80)
        
        # Save jobs if we have any
        if jobs:
            # If we already have a filename, add _INTERIM suffix if not present
            if self.filename and os.path.exists(self.filename):
                base, ext = os.path.splitext(self.filename)
                if not "_INTERIM" in base:
                    interim_filename = f"{base}_INTERIM{ext}"
                    try:
                        # First try using os.rename which should replace the file
                        try:
                            os.rename(self.filename, interim_filename)
                        except Exception as rename_error:
                            # If rename fails (can happen on some Windows setups), create a copy and delete original
                            logger.debug(f"Regular rename failed: {rename_error}. Trying copy and delete approach.")
                            import shutil
                            shutil.copy2(self.filename, interim_filename)
                            
                            # Make sure the copy succeeded before deleting original
                            if os.path.exists(interim_filename):
                                # Delete the original file to avoid duplicates
                                os.remove(self.filename)
                            else:
                                raise Exception("Failed to create interim file copy")
                                
                        self.filename = interim_filename
                        logger.info(f"Renamed file to {interim_filename} to indicate interim results")
                    except Exception as e:
                        logger.warning(f"Failed to rename file as interim: {e}")
            
            # Use save_jobs with is_final=True to upload the interim file
            saved_file = self.save_jobs(jobs, self.filename, is_final=True)
            
        # Force a 3-second delay to make sure the message is seen
        time.sleep(3)
        
        # Final confirmation
        print("\nExiting now...")
        time.sleep(1) 