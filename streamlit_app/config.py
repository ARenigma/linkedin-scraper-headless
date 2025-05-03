"""
Configuration settings for the LinkedIn Job Scraper Streamlit App.
"""
import os
import structlog

# Logging setup
logger = structlog.get_logger()

# Default scraper settings
DEFAULT_TIME_FILTER = 24 * 60 * 60  # 24 hours in seconds
DEFAULT_JOB_COUNT = None
MAX_RETRIES = 3
HEADLESS = True
MAX_WORKERS = 1

# Output directory
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# State management
STATE_FILE = "resume_state.json"

# App configuration
APP_TITLE = "LinkedIn Job Scraper"
APP_DESCRIPTION = "A tool to scrape job listings from LinkedIn based on keywords and locations." 