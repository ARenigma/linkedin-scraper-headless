import dotenv
import os
import logging
import structlog
import sys
import argparse
from datetime import datetime

# Always load from the same .env file regardless of working directory
dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Parse command-line arguments
parser = argparse.ArgumentParser(description="LinkedIn Job Scraper (Headless)")
parser.add_argument("--username", type=str, help="LinkedIn username")
parser.add_argument("--password", type=str, help="LinkedIn password")
parser.add_argument("--days", type=int, default=1, help="Number of days to filter jobs (default: 1)")
parser.add_argument("--jobs", type=int, help="Maximum number of jobs to scrape per keyword+location combo")
parser.add_argument("--workers", type=int, default=1, help="Number of parallel workers (1-5, default: 1)")
args = parser.parse_args()

# File and folder paths
LOG_FOLDER = "logs"
RESUME_FILE = "resume_state.json"
SCREENSHOT_FOLDER = "screenshots"
OUTPUT_FOLDER = "output"

# Create necessary folders
for folder in [LOG_FOLDER, SCREENSHOT_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Logging setup
log_file = os.path.join(LOG_FOLDER, f"linkedin_scraper_{datetime.now().strftime('%d%m%Y_%H%M%S')}.log")

logging.basicConfig(
    format="%(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_file, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.dev.set_exc_info,
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Credentials
USERNAME = args.username or os.getenv("LINKEDIN_USERNAME")
PASSWORD = args.password or os.getenv("LINKEDIN_PASSWORD")

# Search parameters
FILTER_KEYWORDS = [
    "Python developer", "PHP DEVELOPER", "LARAVEL", "DJANGO", 
    "qa engineer", "SDET", "node developer", "java developer", 
    "flutter", "iOS developer", "react", "full stack", 
    "frontend", "backend"
]
LOCATIONS = ["Gurugram", "Bengaluru"]

# Timing settings
DEFAULT_TIMEOUT = 20000  # 20 seconds
DEFAULT_WAIT = 5000      # 5 seconds
SHORT_WAIT = 3000        # 3 seconds
DEFAULT_TIME_FILTER = 86400 * args.days  # Convert days to seconds
DEFAULT_JOB_COUNT = args.jobs  # Default to None (unlimited) or command line value
RESUME_TIMEOUT = 15      # 15 seconds
MAX_RETRIES = 3          # Max retry attempts
MAX_WORKERS = args.workers or 1  # Default to 1 worker

# Browser options for avoiding detection
BROWSER_OPTIONS = {
    "headless": True,
    "args": [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-web-security",
        "--window-size=1920,1080",
        "--disable-features=IsolateOrigins,site-per-process",
    ],
    "ignore_default_args": ["--enable-automation"],
}

# User agent for browser context
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"