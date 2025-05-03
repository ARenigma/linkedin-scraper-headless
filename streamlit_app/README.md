# LinkedIn Job Scraper - Streamlit App

A Streamlit web application for LinkedIn job scraping that can be hosted on Hugging Face Spaces.

## Features

- **User-friendly interface** to configure and run the LinkedIn job scraper
- **Headless browser automation** using Playwright
- **Multi-threaded scraping** for improved performance
- **Real-time status updates** and progress tracking
- **Results preview** with downloadable Excel exports

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/linkedin-scraper-streamlit.git
cd linkedin-scraper-streamlit
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the Streamlit app:
```bash
streamlit run app.py
```

2. Open your browser and navigate to the URL shown in the terminal (usually http://localhost:8501)

3. Enter your LinkedIn credentials and search parameters in the sidebar

4. Click "Start Scraping" to begin

5. Monitor progress and download results when complete

## Deployment on Hugging Face Spaces

This app can be easily deployed on [Hugging Face Spaces](https://huggingface.co/spaces):

1. Fork this repository to your GitHub account

2. Create a new Space on Hugging Face with the Streamlit SDK

3. Connect your GitHub repository to the Space

4. Configure the space to use the requirements.txt file for dependencies

5. You may need to add the following to your space's configuration:
```yaml
build:
  dependencies:
    - playwright
    - chromium
```

6. Deploy the app and wait for the build to complete

## Security Notes

- LinkedIn credentials are only used for authentication and are not stored anywhere
- When hosting on Hugging Face, ensure your space is set to private if you're using the app with your own credentials
- Excessive scraping may lead to LinkedIn rate-limiting or blocking your account

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [Streamlit](https://streamlit.io)
- Browser automation powered by [Playwright](https://playwright.dev) 