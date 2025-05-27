#!/usr/bin/env python3
"""
LinkedIn Job Scraper (Headless)
A modular tool to scrape job listings from LinkedIn based on keywords and locations.
"""

import time
import sys
from typing import List, Dict, Any, Optional, Tuple
from playwright.sync_api import sync_playwright

from config import (
    logger, USERNAME, PASSWORD, FILTER_KEYWORDS, 
    LOCATIONS, DEFAULT_TIME_FILTER, MAX_RETRIES,
    DEFAULT_JOB_COUNT, MAX_WORKERS
)
from browser_utils import BrowserManager
from linkedin_auth import LinkedInAuth
from job_scraper import JobScraper, all_jobs
from state_manager import StateManager
from upload_to_drive import upload_to_drive

def scrape_all_keywords(
    job_scraper: JobScraper,
    keywords: List[str], 
    locations: List[str],
    resume_state: Optional[Dict[str, Any]],
    time_filter: int,
    job_count: Optional[int],
    state_manager: StateManager
) -> List[Dict[str, Any]]:
    """
    Scrape jobs for all keyword-location combinations.
    
    Args:
        job_scraper: JobScraper instance
        keywords: List of keywords to search for
        locations: List of locations to search in
        resume_state: Resume state dictionary or None
        time_filter: Time filter in seconds
        job_count: Maximum number of jobs to scrape per combination
        state_manager: StateManager instance for tracking progress
        
    Returns:
        List of all scraped jobs
    """
    combo_counter = 0
    resumed = False
    
    try:
        # Process each keyword-location combination
        for keyword in keywords:
            for location in locations:
                combo_counter += 1
                
                # Handle resume logic
                if resume_state and not resumed:
                    if combo_counter < resume_state["combo_counter"]:
                        logger.info(f"Skipping combo #{combo_counter}: '{keyword}' in '{location}' (already completed)")
                        continue
                    elif combo_counter == resume_state["combo_counter"]:
                        logger.info(f"Resuming from combo #{combo_counter}: '{keyword}' in '{location}'")
                        resumed = True
                
                logger.info(f"\nScraping combo #{combo_counter}: '{keyword}' in '{location}'")
                
                # Scrape jobs for this combination
                try:
                    combo_jobs = job_scraper.scrape_jobs(keyword, location, job_count, time_filter)
                    logger.info(f"Found {len(combo_jobs)} jobs for '{keyword}' in '{location}'")
                    
                    # Save progress - using global all_jobs list - periodic save without upload
                    state_manager.save_jobs_periodic(all_jobs)
                    
                    # Save cookies after each scrape
                    if hasattr(job_scraper, 'context'):
                        from browser_utils import BrowserManager
                        BrowserManager(None).save_cookies(job_scraper.context)
                
                except Exception as e:
                    logger.error(f"Error scraping '{keyword}' in '{location}': {e}")
                    # Save what we have so far - force immediate save without upload
                    if all_jobs:
                        state_manager.save_jobs_periodic(all_jobs, 0)
                
        # Final save of all jobs - this is the only place we should upload to Drive normally
        if all_jobs:
            state_manager.save_jobs(all_jobs, is_final=True)
            state_manager.rename_file_complete()
            state_manager.delete_resume_point()
            
    except KeyboardInterrupt:
        logger.warning("Scraping interrupted by user")
        state_manager.handle_keyboard_interrupt(all_jobs)
        sys.exit(1)
        
    return all_jobs

def main():
    """Main entry point for the LinkedIn scraper."""
    logger.info("Starting LinkedIn Job Scraper (Headless)")
    
    # Step 1: Verify credentials
    if not USERNAME or not PASSWORD:
        logger.error("LinkedIn credentials not found. Set LINKEDIN_USERNAME and LINKEDIN_PASSWORD env vars.")
        sys.exit(1)
    
    # Step 2: Set scraping parameters from config (derived from command-line args)
    max_workers = MAX_WORKERS
    time_filter = DEFAULT_TIME_FILTER
    job_count = DEFAULT_JOB_COUNT
    
    # Step 3: Get resume decision
    state_manager = StateManager()
    resume_state = state_manager.handle_resume_decision()
    
    logger.info(f"Using time filter: {time_filter // 86400} day(s), job count: {'unlimited' if job_count is None else job_count}, workers: {max_workers}")
    
    # Step 4: Main scraping process with reconnection handling
    try:
        with sync_playwright() as p:
            reconnect_attempts = 0
            
            while reconnect_attempts < MAX_RETRIES:
                try:
                    # Initialize browser manager for headless operation
                    browser_manager = BrowserManager(p)
                    page, context, browser = browser_manager.connect()
                    
                    # Initialize LinkedIn auth and log in
                    auth = LinkedInAuth(USERNAME, PASSWORD)
                    page, context = auth.login(page, context, browser)
                    
                    # Initialize job scraper with batch processing
                    job_scraper = JobScraper(page, context, max_workers=max_workers)
                    
                    # Start scraping process based on resume state
                    scraped_jobs = scrape_all_keywords(
                        job_scraper, 
                        FILTER_KEYWORDS, 
                        LOCATIONS, 
                        resume_state,
                        time_filter,
                        job_count,
                        state_manager
                    )
                    
                    logger.info(f"Scraping completed. Total jobs collected: {len(all_jobs)}")
                    break  # Exit the reconnection loop if successful
                    
                except Exception as e:
                    reconnect_attempts += 1
                    logger.error(f"Fatal error (attempt {reconnect_attempts}/{MAX_RETRIES}): {e}")
                    
                    # Save any jobs we've collected so far - without upload
                    if all_jobs:
                        state_manager.save_jobs_periodic(all_jobs, 0)
                    
                    if reconnect_attempts < MAX_RETRIES:
                        retry_delay = 30  # seconds
                        logger.info(f"Waiting {retry_delay} seconds before reconnection attempt...")
                        time.sleep(retry_delay)
    
    except Exception as e:
        logger.error(f"Critical error in main process: {e}")
        # Ensure we save and upload any collected jobs - this is a final save with upload
        if all_jobs:
            saved_file = state_manager.save_jobs(all_jobs, is_final=True)
            if saved_file:
                logger.info(f"Emergency save completed to {saved_file}")
    
    finally:
        logger.info("LinkedIn Job Scraper finished")

if __name__ == "__main__":
    main()