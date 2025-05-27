from typing import List, Dict, Any, Optional, Set
import time
import re
from tqdm import tqdm
from playwright.sync_api import Page, BrowserContext
from concurrent.futures import ThreadPoolExecutor
import threading
import os
import urllib.parse
import json

from config import logger, DEFAULT_TIMEOUT, DEFAULT_WAIT, SHORT_WAIT
from job_details import JobDetailsExtractor

# Global list to store all jobs that have been found
all_jobs = []

class JobScraper:
    """Handles LinkedIn job scraping functionality."""
    
    def __init__(self, page: Page, context: BrowserContext, max_workers: int = 3):
        self.page = page
        self.context = context
        self.job_details_extractor = JobDetailsExtractor()
        self.max_workers = max_workers
        self.processed_job_ids = set()  # Track already processed job IDs
        self._lock = threading.Lock()  # Thread synchronization
        
    def scrape_jobs(self, keyword: str, location: str, max_count: Optional[int] = None, time_filter: int = 86400) -> List[Dict[str, Any]]:
        """
        Scrape jobs for a given keyword and location combination.
        
        Args:
            keyword: Job search keyword
            location: Location to search in
            max_count: Maximum number of jobs to scrape (None for unlimited)
            time_filter: Time filter in seconds (default: 1 day)
            
        Returns:
            List of job details dictionaries
        """
        #logger.info(f"Scraping jobs for '{keyword}' in '{location}'")
        jobs = []
        start = 0  # pagination offset, increases by 25 for each page
        consecutive_empty_pages = 0
        max_empty_pages = 2
        
        with tqdm(total=max_count if max_count else 0, desc=f"Processing '{keyword}'", unit="job") as progress:
            while True:
                # Check if we've reached our max job count
                if max_count is not None and len(jobs) >= max_count:
                    logger.info(f"Reached max job count: {max_count}")
                    break
                
                # Check if we've seen too many empty pages
                if consecutive_empty_pages >= max_empty_pages:
                    logger.info(f"{consecutive_empty_pages} empty pages in a row, moving on")
                    break
                
                # Construct search URL with filters
                search_url = (
                    f"https://www.linkedin.com/jobs/search/?keywords={keyword}"
                    f"&location={location}&start={start}&f_TPR=r{time_filter}&f_WT=1%2C1%2C3"
                )
                
                logger.info(f"Visiting: {search_url}")
                
                # Navigate to search results page
                try:
                    self.page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
                except Exception as e:
                    logger.warning(f"Navigation failed: {e}")
                    consecutive_empty_pages += 1
                    start += 25
                    continue
                
                # Check for no results message
                no_results = self._check_no_results()
                if no_results:
                    logger.info("No matching jobs found")
                    break
                
                # Check for visible job cards directly before attempting to scroll (if applicable)
                try:
                    initial_job_cards = self.page.locator(".job-card-container--clickable")
                    initial_count = initial_job_cards.count()
                    if initial_count > 0:
                        # Reset empty page counter immediately if we see cards
                        consecutive_empty_pages = 0
                    else:
                        logger.warning("No job cards found before scrolling")
                except Exception as e:
                    logger.debug(f"Error checking initial cards: {e}")
                
                # Scroll to load all job cards
                if not self._scroll_job_list():
                    logger.warning("Scrolling failed, skipping page")
                    consecutive_empty_pages += 1
                    start += 25
                    continue
                
                # Process job cards
                try:
                    job_cards = self.page.locator(".job-card-container--clickable")
                    total_cards = job_cards.count()
                    
                    if total_cards == 0:
                        logger.warning("No job cards found")
                        consecutive_empty_pages += 1
                        start += 25
                        continue
                        
                    # Reset empty page counter if we found cards
                    consecutive_empty_pages = 0
                    
                    # Get job IDs and titles for pre-filtering
                    job_data = self._collect_job_card_data(job_cards, total_cards)
                    
                    # Filter out irrelevant jobs and already processed ones
                    filtered_jobs = self._filter_job_cards(job_data, keyword)
                    
                    if not filtered_jobs:
                        logger.info(f"No matching jobs found for '{keyword}'")
                        consecutive_empty_pages += 1
                        start += 25
                        continue
                        
                    logger.info(f"Found {len(filtered_jobs)} matching jobs")
                    
                    # Apply max count limit if needed
                    if max_count is not None:
                        remaining = max_count - len(jobs)
                        if remaining <= 0:
                            break
                        if len(filtered_jobs) > remaining:
                            filtered_jobs = filtered_jobs[:remaining]
                    
                    # Check if using batch processing or sequential processing
                    if self.max_workers > 1 and len(filtered_jobs) > 1:
                        # Process jobs in parallel using batch processing
                        batch_jobs = self._process_job_cards_batch(filtered_jobs, keyword, location)
                        jobs.extend(batch_jobs)
                        progress.update(len(batch_jobs))
                    else:
                        # Process jobs sequentially (original approach)
                        for i, (index, job_id, title) in enumerate(filtered_jobs):
                            job = self._process_job_card(job_cards.nth(index), keyword, location, job_id)
                            if job:
                                jobs.append(job)
                                progress.update(1)
                                
                            # Check if we've reached the max count
                            if max_count is not None and len(jobs) >= max_count:
                                logger.info(f"Reached max job count: {max_count}")
                                return jobs
                            
                except Exception as e:
                    logger.error(f"Error processing job cards: {e}")
                    
                # Move to next page
                start += 25
                
        # After scraping jobs, refresh cookies
        try:
            from browser_utils import BrowserManager
            BrowserManager(None).save_cookies(self.context)
        except Exception as e:
            logger.warning(f"Error saving cookies after scraping: {e}")
            pass
            
        return jobs
    
    def _collect_job_card_data(self, job_cards, total_cards) -> List[tuple]:
        """Collect job ID and title data from each card for pre-filtering."""
        job_data = []
        
        for i in range(total_cards):
            try:
                card = job_cards.nth(i)
                
                # Skip if not visible
                if not card.is_visible(timeout=SHORT_WAIT):
                    continue
                    
                # Extract job ID
                job_id = None
                try:
                    job_id = card.get_attribute("data-job-id")
                    if not job_id:
                        # Try alternative methods to get ID
                        job_id = card.get_attribute("id")
                        if job_id and job_id.startswith("job-card-"):
                            job_id = job_id.replace("job-card-", "")
                except:
                    pass
                
                # Extract title text
                card_text = card.inner_text(timeout=SHORT_WAIT)
                if not card_text:
                    continue
                    
                job_title_lines = card_text.strip().split("\n")
                job_title = re.sub(r"\s+", " ", job_title_lines[0]).strip().lower()
                
                # Add to job data collection
                job_data.append((i, job_id, job_title))
                
            except Exception as e:
                logger.debug(f"Error collecting job card data: {e}")
                
        return job_data
    
    def _filter_job_cards(self, job_data: List[tuple], keyword: str) -> List[tuple]:
        """Filter job cards based on keyword match and duplicate tracking."""
        filtered_jobs = []
        skipped_duplicates = 0
        mismatched_jobs = 0
        
        # Normalize and prepare the keyword for matching
        keyword_lower = keyword.lower()
        # Split into words and ignore common conjunctions/prepositions
        stop_words = {'and', 'or', 'the', 'in', 'for', 'of', 'with', 'a', 'an', 'to', 'at', 'by', 'on'}
        keyword_words = [w for w in re.split(r'[^\w]+', keyword_lower) 
                         if w and w not in stop_words]
        
        # Get the first significant word of the keyword (critical to match)
        first_word = keyword_words[0] if keyword_words else None
        
        logger.debug(f"Keyword '{keyword}' parsed into words: {keyword_words}")
        logger.debug(f"First critical word (must match): '{first_word}'")
        
        for index, job_id, job_title in job_data:
            # Skip previously processed jobs
            if job_id and job_id in self.processed_job_ids:
                logger.debug(f"Skipping already processed job: {job_title}")
                skipped_duplicates += 1
                continue
            
            job_title_lower = job_title.lower()
            
            # Clean up the job title for matching - replace punctuation with spaces
            cleaned_title = re.sub(r'[^\w\s]', ' ', job_title_lower)
            title_words = set(w for w in cleaned_title.split() if w and w not in stop_words)
            
            # RULE 1: First word of keyword MUST be in the title words
            if first_word and first_word not in title_words:
                mismatched_jobs += 1
                logger.debug(f"Job title did not match first word rule: '{job_title}' - missing '{first_word}'")
                continue
            
            # Count how many of the keyword words are in the title words
            matching_words = sum(1 for word in keyword_words if word in title_words)
            
            # RULE 2: Require at least 75% of the significant words to match
            min_match_percentage = 0.75
            required_matches = max(1, round(len(keyword_words) * min_match_percentage))
            
            if matching_words >= required_matches:
                filtered_jobs.append((index, job_id, job_title))
                # Log which words matched for debugging
                matched = [word for word in keyword_words if word in title_words]
                logger.debug(f"Matched job: '{job_title}' with keyword '{keyword}' (Matched {matching_words}/{len(keyword_words)} words: {matched})")
                
                # Add to processed set if we have an ID
                if job_id:
                    with self._lock:
                        self.processed_job_ids.add(job_id)
            else:
                mismatched_jobs += 1
                logger.debug(f"Job title did not match word threshold: '{job_title}' with keyword '{keyword}' (Matched only {matching_words}/{len(keyword_words)} words: {[word for word in keyword_words if word in title_words]})")
        
        if skipped_duplicates > 0:
            logger.info(f"Skipped {skipped_duplicates} duplicate jobs using job IDs")
            
        if mismatched_jobs > 0:
            logger.debug(f"Filtered out {mismatched_jobs} jobs that didn't match keyword '{keyword}'")
            
        return filtered_jobs
    
    def _process_job_cards_batch(self, filtered_jobs: List[tuple], keyword: str, location: str) -> List[Dict[str, Any]]:
        """Process multiple job cards in parallel using thread pool."""
        # Create additional pages for parallel processing
        batch_size = min(len(filtered_jobs), self.max_workers)
        logger.info(f"Processing {len(filtered_jobs)} jobs in batches using {batch_size} workers")
        
        # Create additional browser contexts for parallel processing
        contexts_and_pages = [(self.context, self.page)]  # Start with the main context and page
        
        for _ in range(1, batch_size):
            try:
                # Create new context and page
                context = self.context.browser.new_context()
                page = context.new_page()
                contexts_and_pages.append((context, page))
            except Exception as e:
                logger.warning(f"Error creating additional browser context: {e}")
                break
        
        batch_jobs = []
        
        with ThreadPoolExecutor(max_workers=len(contexts_and_pages)) as executor:
            # Divide jobs among workers
            futures = []
            
            for i, (index, job_id, job_title) in enumerate(filtered_jobs):
                # Choose which context/page to use (round-robin)
                context, page = contexts_and_pages[i % len(contexts_and_pages)]
                
                # Submit job to thread pool
                if i < len(contexts_and_pages):
                    # First batch: submit immediately
                    future = executor.submit(
                        self._process_job_in_new_tab, 
                        page, context, job_id, job_title, keyword, location
                    )
                    futures.append(future)
                else:
                    # Wait for any future to complete before submitting more
                    # This keeps the number of simultaneous jobs limited
                    done, futures = self._wait_for_any_future(futures)
                    for f in done:
                        result = f.result()
                        if result:
                            batch_jobs.append(result)
                    
                    # Submit new job
                    future = executor.submit(
                        self._process_job_in_new_tab, 
                        page, context, job_id, job_title, keyword, location
                    )
                    futures.append(future)
            
            # Wait for remaining futures to complete
            for future in futures:
                try:
                    result = future.result()
                    if result:
                        batch_jobs.append(result)
                except Exception as e:
                    logger.error(f"Error in job processing future: {e}")
        
        # Close additional contexts (but not the main one)
        for context, _ in contexts_and_pages[1:]:
            try:
                context.close()
            except:
                pass
                
        return batch_jobs
    
    def _wait_for_any_future(self, futures):
        """Wait for any future to complete and return results."""
        import concurrent.futures
        done, not_done = concurrent.futures.wait(
            futures, 
            return_when=concurrent.futures.FIRST_COMPLETED
        )
        return done, list(not_done)
    
    def _process_job_in_new_tab(self, page: Page, context: BrowserContext, 
                               job_id: str, job_title: str, 
                               keyword: str, location: str) -> Optional[Dict[str, Any]]:
        """Process a job in a separate page/tab."""
        try:
            # Construct direct job URL if we have the ID
            if job_id:
                job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
                try:
                    # Navigate to job page
                    page.goto(job_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
                    page.wait_for_timeout(SHORT_WAIT)
                    
                    # Extract job details
                    extractor = JobDetailsExtractor()  # Create new extractor for thread safety
                    job = extractor.extract(page, location, keyword)
                    
                    # Make sure job URL is correct
                    job["Job URL"] = job_url
                    
                    # Add this job to all_jobs list immediately
                    global all_jobs
                    with self._lock:
                        all_jobs.append(job)
                    
                    logger.info(f"Batch extracted job: {job['Job Title']} at {job['Company Name']}")
                    return job
                    
                except Exception as e:
                    logger.warning(f"Error processing job {job_id} in new tab: {e}")
                    return None
            else:
                logger.debug(f"Cannot process job in new tab - no job ID available for: {job_title}")
                return None
                
        except Exception as e:
            logger.error(f"Error in job tab processing: {e}")
            return None
    
    def _check_no_results(self) -> bool:
        """Check if the page shows a 'no results' message."""
        try:
            body_text = self.page.inner_text("body", timeout=SHORT_WAIT).lower()
            no_results_phrases = [
                "no matching jobs found", 
                "try different filters", 
                "search again",
                "couldn't find any jobs",
                "no jobs to show",
                "no results found"
            ]
            
            for phrase in no_results_phrases:
                if phrase in body_text:
                    return True
                    
            return False
        except Exception:
            return False
    
    def _scroll_job_list(self, min_cards: int = 25, max_scrolls: int = 15, delay: int = 1) -> bool:
        """Scroll the job list panel to load more jobs."""
        try:
            # Take a screenshot for debugging
            try:
                if not os.path.exists("screenshots"):
                    os.makedirs("screenshots")
                screenshot_path = os.path.join("screenshots", f"scroll_debug_{int(time.time())}.png")
                self.page.screenshot(path=screenshot_path)
                logger.debug(f"Saved debug screenshot to {screenshot_path}")
            except Exception as e:
                logger.debug(f"Failed to save debug screenshot: {e}")
                
            # Check if we're on the job search page
            current_url = self.page.url
            logger.debug(f"Current URL before scrolling: {current_url}")
            
            # Try a basic visibility check for the jobs list
            try:
                job_cards = self.page.locator(".job-card-container--clickable")
                initial_count = job_cards.count()
                logger.info(f"Initial job cards count: {initial_count}")
            except Exception as e:
                logger.warning(f"Error checking job card visibility: {e}")
            
            # Use dynamic detection to find the scrollable container - silently
            scroll_selector = self.page.evaluate("""
                () => {
                    // First priority: Any div containing job cards with overflow
                    const all = Array.from(document.querySelectorAll("div"));
                    for (let el of all) {
                        if (el.scrollHeight > el.clientHeight && el.querySelector('.job-card-container--clickable')) {
                            const cls = el.getAttribute("class");
                            if (cls) {
                                const firstClass = cls.split(" ")[0].replace(/[^a-zA-Z0-9_-]/g, "");
                                return `div[class*="${firstClass}"]`;
                            }
                        }
                    }
                    
                    // Second priority: Any scrollable parent of job cards
                    const jobCards = document.querySelector('.job-card-container--clickable');
                    if (jobCards) {
                        let parent = jobCards.parentElement;
                        while (parent && parent.tagName !== 'BODY') {
                            const style = window.getComputedStyle(parent);
                            if (style.overflow === 'auto' || style.overflow === 'scroll' || 
                                style.overflowY === 'auto' || style.overflowY === 'scroll') {
                                const cls = parent.getAttribute("class");
                                if (cls) {
                                    return parent.tagName.toLowerCase() + '.' + cls.split(' ')[0];
                                } else {
                                    return parent.tagName.toLowerCase();
                                }
                            }
                            parent = parent.parentElement;
                        }
                    }
                    
                    // Last resort: Use body as scroller
                    return 'body';
                }
            """)
            
            if not scroll_selector:
                scroll_selector = "body"  # Fallback to body
                
            last_card_count = -1
            stagnant_scrolls = 0
            max_stagnant_scrolls = 2
            
            # Continue scrolling until we've scrolled max_scrolls times
            # or the card count stops increasing for max_stagnant_scrolls attempts
            for i in range(max_scrolls):
                # Perform smooth scroll in smaller steps
                for _ in range(5):
                    self.page.evaluate("""
                        (selector) => {
                            const el = document.querySelector(selector);
                            if (el) {
                                if (el === document.body) {
                                    window.scrollBy(0, 300); 
                                } else {
                                    el.scrollBy(0, 300);
                                }
                            }
                        }
                    """, scroll_selector)
                    self.page.wait_for_timeout(200)
                    
                self.page.wait_for_timeout(delay * 1000)
                
                # Check job cards count
                job_cards = self.page.locator(".job-card-container--clickable")
                total_cards = job_cards.count()
                
                # We can stop early if we've reached the minimum desired card count
                # but we'll continue scrolling to try to load as many as possible
                if total_cards >= min_cards and stagnant_scrolls >= max_stagnant_scrolls:
                    break
                    
                # Check if we're still loading new cards
                if total_cards == last_card_count:
                    stagnant_scrolls += 1
                    if stagnant_scrolls >= max_stagnant_scrolls:
                        # No new cards after multiple scrolls, probably reached the end
                        break
                else:
                    stagnant_scrolls = 0
                    last_card_count = total_cards
                    
            # Final check for job cards
            job_cards = self.page.locator(".job-card-container--clickable")
            final_count = job_cards.count()
            
            if final_count > 0:
                logger.info(f"Finished scrolling. Found total {final_count} job cards")
                return True
            else:
                logger.warning("No job cards found after scrolling")
                return False
                
        except Exception as e:
            logger.warning(f"Error scrolling job list: {e}")
            return False
    
    def _process_job_card(self, card, keyword: str, location: str, job_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Process a single job card."""
        try:
            if not card.is_visible(timeout=SHORT_WAIT):
                logger.debug("Card not visible, skipping")
                return None
                
            # Get job title from card
            try:
                card_text = card.inner_text(timeout=SHORT_WAIT)
                if not card_text:
                    logger.debug("Card has no text, skipping")
                    return None
                    
                job_title_lines = card_text.strip().split("\n")
                job_title = re.sub(r"\s+", " ", job_title_lines[0]).strip().lower()
                
                # We already checked keyword match during filtering, no need to check again
                #logger.info(f"Clicking job card: '{job_title}'")
                
                # Click the card to open job details
                card.click()
                self.page.wait_for_timeout(SHORT_WAIT)
                
                # Extract job details
                job = self.job_details_extractor.extract(self.page, location, keyword)
                
                # Track this job as processed if we have an ID
                if job_id:
                    with self._lock:
                        self.processed_job_ids.add(job_id)
                        
                # Add this job to all_jobs list immediately
                global all_jobs
                with self._lock:
                    all_jobs.append(job)
                        
                logger.info(f"Extracted job: {job['Job Title']} at {job['Company Name']}")
                return job
                
            except Exception as e:
                logger.warning(f"Error extracting card text: {e}")
                return None
                
        except Exception as e:
            logger.warning(f"Error processing job card: {e}")
            return None
            
    def test_keyword_matching(self, keyword: str, job_titles: List[str]) -> Dict[str, bool]:
        """
        Test keyword matching against a list of job titles without scraping.
        Useful for debugging and validating matching logic.
        
        Args:
            keyword: The keyword to test
            job_titles: A list of job titles to test against
            
        Returns:
            A dictionary mapping job titles to match results (True/False)
        """
        # Create mock job data with dummy IDs
        job_data = [(i, f"dummy_id_{i}", title) for i, title in enumerate(job_titles)]
        
        # Use the filter method with debug logging enabled
        import logging
        original_level = logger.level
        logger.setLevel(logging.INFO)  # Ensure debug logs are visible
        
        # Get the filtered jobs
        filtered_jobs = self._filter_job_cards(job_data, keyword)
        
        # Reset logger level
        logger.setLevel(original_level)
        
        # Create result dictionary
        matched_indices = {index for index, _, _ in filtered_jobs}
        results = {title: i in matched_indices for i, title in enumerate(job_titles)}
        
        # Print summary
        matched = [title for title, matched in results.items() if matched]
        not_matched = [title for title, matched in results.items() if not matched]
        
        logger.info(f"\n{'='*50}")
        logger.info(f"KEYWORD MATCH TEST: '{keyword}'")
        logger.info(f"{'='*50}")
        logger.info(f"Total job titles: {len(job_titles)}")
        logger.info(f"Matched: {len(matched)} ({len(matched)/len(job_titles)*100:.1f}%)")
        logger.info(f"Not matched: {len(not_matched)} ({len(not_matched)/len(job_titles)*100:.1f}%)")
        
        if matched:
            logger.info(f"\nMATCHED TITLES:")
            for i, title in enumerate(matched, 1):
                logger.info(f"  {i}. {title}")
                
        if not_matched:
            logger.info(f"\nNOT MATCHED TITLES:")
            for i, title in enumerate(not_matched, 1):
                logger.info(f"  {i}. {title}")
                
        logger.info(f"{'='*50}\n")
        
        return results