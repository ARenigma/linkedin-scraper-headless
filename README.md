# LinkedIn Job Scraper (Headless Version)

A modular, object-oriented LinkedIn job scraper built with Python and Playwright, optimized for headless operation.

## Features

- Runs in headless mode by default (browser invisible)
- Scrape LinkedIn job listings based on keywords and locations
- Modular, object-oriented architecture for maintainability
- Anti-detection techniques to avoid blocking
- Full error handling and recovery
- State persistence with resume functionality
- Progress visualization with tqdm
- Auto-saving of results
- Easily configurable through config.py
- Parallel job processing with multi-threading
- Optimized selectors for resilient data extraction

## Prerequisites

- Python 3.8+
- LinkedIn account credentials

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install playwright pandas tqdm structlog
playwright install chromium
```

3. Set environment variables:
```bash
export LINKEDIN_USERNAME="your_email@example.com"
export LINKEDIN_PASSWORD="your_password"
```

## Project Structure

The scraper uses a modular design with clear separation of concerns:

- `config.py` - Configuration settings and constants
- `browser_utils.py` - Browser management and connection handling
- `linkedin_auth.py` - LinkedIn authentication and session management
- `job_details.py` - Job details extraction functionality with optimized selectors
- `job_scraper.py` - Core job search and scraping logic with batch processing
- `state_manager.py` - State persistence and resume handling
- `main.py` - Main entry point orchestrating the scraping process

## Performance Optimizations

### Optimized Selectors
- Multiple selectors for each data point to handle LinkedIn's UI variations
- Faster element detection with unified selector strategies
- Resilient to UI changes with hierarchical fallbacks

### Batch Processing
- Parallel job detail extraction using multiple browser contexts
- Configurable number of worker threads (1-5)
- Efficient job deduplication using job IDs
- Smart thread pooling to maximize performance while minimizing resource usage

### Headless Mode Optimizations
- Anti-detection techniques to avoid Playwright/Selenium detection
- Custom user agent configuration
- Browser fingerprint modifications
- Automated screenshot capturing for debugging
- Security challenge detection

## Usage

### Command-line Arguments

The scraper supports various command-line arguments for configuration:

```bash
python main.py [OPTIONS]
```

Options:
- `--headed`: Run in headed mode (browser visible) instead of headless
- `--username USERNAME`: LinkedIn username (overrides environment variable)
- `--password PASSWORD`: LinkedIn password (overrides environment variable)
- `--days DAYS`: Number of days to filter jobs (default: 1)
- `--jobs JOBS`: Maximum number of jobs to scrape per keyword+location combo
- `--workers WORKERS`: Number of parallel workers (1-5, default: 1)

Examples:
```bash
# Run in default headless mode
python main.py

# Run in headed mode for debugging
python main.py --headed

# Run with specific job age filter and worker count
python main.py --days 7 --workers 3

# Run with specific credentials
python main.py --username your@email.com --password yourpassword
```

### Interactive Prompts

After starting the scraper, you'll be prompted to specify:
- Number of days to look back for jobs (1-30)
- Number of jobs to scrape per keyword-location combination (leave blank for all)
- Number of parallel workers (1-5, default=1)

## Headless vs. Headed Mode

This version is optimized for headless operation, but also supports headed mode:

### Headless Mode (default)
- Runs without a visible browser window
- Better performance and resource usage
- Works well for environments without a display (servers, CI/CD)
- Uses anti-detection techniques to avoid being blocked

### Headed Mode
- Shows the browser window during scraping
- Allows for visual debugging and monitoring
- Required for solving CAPTCHA or security challenges
- Helpful for debugging extraction issues

**Note:** If you encounter security challenges in headless mode, the scraper will detect this and suggest switching to headed mode.

## Customization

Edit `config.py` to modify:
- Keywords to search for
- Locations to search in
- Timeout values
- Logging settings
- Output paths
- Browser options and anti-detection settings

## Output

Jobs are saved to Excel files in the `output/YYYY-MM-DD/` directory with timestamps. A successful full run will append `_COMPLETE` to the filename.

## Batch Processing Performance

The parallel processing capability can significantly improve performance:
- 1 worker: Baseline performance (sequential processing)
- 2 workers: ~1.7x speed improvement
- 3 workers: ~2.2x speed improvement  
- 4 workers: ~2.5x speed improvement
- 5 workers: ~2.7x speed improvement

Note: Performance gains may vary based on your system resources and network conditions. Using too many workers might cause rate limiting from LinkedIn's servers.

## Error Handling

The scraper includes comprehensive error handling:
- Browser connection recovery
- Session validation
- Security challenge detection
- Graceful termination with state saving
- Retry mechanisms for transient failures
- Thread-safe job tracking
- Automatic screenshot capture for debugging

## License

MIT

## Disclaimer

This tool is for educational purposes only. Use responsibly and in accordance with LinkedIn's terms of service. 