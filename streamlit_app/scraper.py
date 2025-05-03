"""
LinkedIn Job Scraper module for the Streamlit app.
"""
import os
import sys
import time
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright

# Import required modules from parent directory
sys.path.append("..")
from linkedin_scraper_modular_headless.browser_utils import BrowserManager
from linkedin_scraper_modular_headless.linkedin_auth import LinkedInAuth
from linkedin_scraper_modular_headless.job_scraper import JobScraper
from models import ScrapeConfig, ScrapingStatus, JobDetails
from config import logger, OUTPUT_DIR

class StreamlitScraper:
    """LinkedIn job scraper for use with Streamlit."""
    
    def __init__(self):
        """Initialize the scraper."""
        self.status = ScrapingStatus(status="idle", progress=0.0)
        self.scrape_thread = None
        self.jobs = []
        self.output_file = None
    
    def start_scraping(self, config: ScrapeConfig) -> None:
        """
        Start scraping in a separate thread.
        
        Args:
            config: Scraping configuration
        """
        if self.scrape_thread and self.scrape_thread.is_alive():
            self.status.status = "already_running"
            return
        
        self.status = ScrapingStatus(
            status="starting", 
            progress=0.0,
            current_keyword=None,
            current_location=None,
            total_jobs=0,
            completed=False
        )
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = os.path.join(OUTPUT_DIR, f"linkedin_jobs_{timestamp}.xlsx")
        
        # Start scraping in a separate thread
        self.scrape_thread = threading.Thread(
            target=self._scrape_jobs,
            args=(config,),
            daemon=True
        )
        self.scrape_thread.start()
    
    def _scrape_jobs(self, config: ScrapeConfig) -> None:
        """
        Scrape jobs based on configuration.
        
        Args:
            config: Scraping configuration
        """
        try:
            self.status.status = "running"
            self.jobs = []
            
            with sync_playwright() as p:
                try:
                    # Initialize browser manager
                    browser_manager = BrowserManager(p, headless=config.headless)
                    page, context, browser = browser_manager.connect()
                    
                    # Log in to LinkedIn
                    auth = LinkedInAuth(config.username, config.password)
                    page, context = auth.login(page, context, browser)
                    
                    # Initialize job scraper
                    job_scraper = JobScraper(page, context, max_workers=config.max_workers)
                    
                    # Calculate total combinations for progress tracking
                    total_combos = len(config.keywords) * len(config.locations)
                    current_combo = 0
                    
                    # Convert time filter from days to seconds
                    time_filter_seconds = config.time_filter_days * 24 * 60 * 60
                    
                    # Process each keyword-location combination
                    for keyword in config.keywords:
                        for location in config.locations:
                            current_combo += 1
                            
                            # Update status
                            self.status.current_keyword = keyword
                            self.status.current_location = location
                            self.status.progress = (current_combo - 1) / total_combos * 100
                            
                            logger.info(f"Scraping jobs for '{keyword}' in '{location}'")
                            
                            # Scrape jobs
                            try:
                                new_jobs = job_scraper.scrape_jobs(
                                    keyword, 
                                    location, 
                                    config.job_count, 
                                    time_filter_seconds
                                )
                                
                                # Add keyword and location info to jobs
                                for job in new_jobs:
                                    job['scraped_keyword'] = keyword
                                    job['scraped_location'] = location
                                
                                self.jobs.extend(new_jobs)
                                self.status.total_jobs = len(self.jobs)
                                
                                # Save jobs periodically
                                if self.jobs and current_combo % 2 == 0:
                                    self._save_jobs_to_excel()
                                
                            except Exception as e:
                                logger.error(f"Error scraping '{keyword}' in '{location}': {e}")
                                self.status.error_message = str(e)
                    
                    # Final save of all jobs
                    if self.jobs:
                        self._save_jobs_to_excel()
                    
                    self.status.status = "completed"
                    self.status.progress = 100.0
                    self.status.completed = True
                    
                except Exception as e:
                    logger.error(f"Fatal error during scraping: {e}")
                    self.status.status = "error"
                    self.status.error_message = str(e)
        
        except Exception as outer_e:
            logger.error(f"Outer error: {outer_e}")
            self.status.status = "error"
            self.status.error_message = str(outer_e)
    
    def _save_jobs_to_excel(self) -> None:
        """Save scraped jobs to an Excel file."""
        try:
            df = pd.DataFrame(self.jobs)
            df.to_excel(self.output_file, index=False)
            logger.info(f"Saved {len(self.jobs)} jobs to {self.output_file}")
        except Exception as e:
            logger.error(f"Error saving jobs to Excel: {e}")
    
    def get_status(self) -> ScrapingStatus:
        """Get the current scraping status."""
        return self.status
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get the list of scraped jobs."""
        return self.jobs
    
    def get_output_file(self) -> Optional[str]:
        """Get the path to the output file."""
        return self.output_file if os.path.exists(self.output_file) else None

# Singleton scraper instance
scraper = StreamlitScraper() 