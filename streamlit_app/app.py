"""
Streamlit app for LinkedIn Job Scraper
"""
import os
import streamlit as st
import pandas as pd
import time
from typing import List, Optional
import base64
from io import BytesIO

from config import APP_TITLE, APP_DESCRIPTION, DEFAULT_JOB_COUNT, OUTPUT_DIR
from models import ScrapeConfig, ScrapingStatus
from scraper import scraper

# Page setup
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply custom CSS
st.markdown("""
<style>
    .main {
        max-width: 1200px;
        padding: 1rem;
    }
    .stProgress > div > div {
        height: 20px;
    }
    .scrape-section {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    h1, h2, h3 {
        margin-top: 0;
    }
    .stButton button {
        width: 100%;
    }
    .stTextInput, .stNumberInput {
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
def get_download_link(file_path: str, link_text: str) -> str:
    """Generate a download link for a file."""
    if not os.path.exists(file_path):
        return ""
    
    with open(file_path, 'rb') as f:
        data = f.read()
    
    b64 = base64.b64encode(data).decode()
    filename = os.path.basename(file_path)
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">{link_text}</a>'
    return href

def get_table_download_link(df: pd.DataFrame, filename: str, link_text: str) -> str:
    """Generate a download link for a DataFrame."""
    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)
    b64 = base64.b64encode(excel_buffer.read()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">{link_text}</a>'
    return href

def validate_input(keywords: str, locations: str, username: str, password: str) -> List[str]:
    """Validate user input and return errors."""
    errors = []
    if not keywords:
        errors.append("Keywords are required")
    if not locations:
        errors.append("Locations are required")
    if not username:
        errors.append("LinkedIn username is required")
    if not password:
        errors.append("LinkedIn password is required")
    return errors

def display_status_info(status: ScrapingStatus) -> None:
    """Display the current scraping status."""
    st.markdown("### Current Status")
    
    # Status indicator
    status_color = {
        "idle": "blue",
        "starting": "blue",
        "running": "green",
        "completed": "green",
        "error": "red",
        "already_running": "orange"
    }.get(status.status, "gray")
    
    st.markdown(f"<span style='color:{status_color};font-weight:bold;font-size:1.2em;'>{status.status.upper()}</span>", unsafe_allow_html=True)
    
    # Progress bar
    if status.status in ["running", "starting"] and status.progress > 0:
        st.progress(status.progress / 100)
    
    # Current operation details
    if status.current_keyword and status.current_location:
        st.markdown(f"**Currently scraping:** '{status.current_keyword}' in '{status.current_location}'")
    
    # Job count
    if status.total_jobs > 0:
        st.markdown(f"**Jobs found so far:** {status.total_jobs}")
    
    # Error message
    if status.error_message:
        st.error(f"Error: {status.error_message}")

def main():
    """Main Streamlit app function."""
    st.title(APP_TITLE)
    st.markdown(APP_DESCRIPTION)
    
    # Sidebar - Configuration
    st.sidebar.header("Scraper Configuration")
    
    # LinkedIn credentials
    st.sidebar.subheader("LinkedIn Credentials")
    linkedin_username = st.sidebar.text_input("LinkedIn Username", key="username", type="default")
    linkedin_password = st.sidebar.text_input("LinkedIn Password", key="password", type="password")
    
    # Search parameters
    st.sidebar.subheader("Search Parameters")
    keywords_input = st.sidebar.text_area("Keywords (one per line)", height=100)
    locations_input = st.sidebar.text_area("Locations (one per line)", height=100)
    
    # Advanced options (collapsible)
    with st.sidebar.expander("Advanced Options"):
        job_count = st.number_input("Maximum jobs per combination", min_value=1, max_value=1000, value=DEFAULT_JOB_COUNT)
        time_filter_days = st.number_input("Time filter (days)", min_value=1, max_value=30, value=1)
        headless = st.checkbox("Run in headless mode", value=True)
        max_workers = st.number_input("Max parallel workers", min_value=1, max_value=5, value=2)
    
    # Parse inputs
    keywords = [k.strip() for k in keywords_input.strip().split("\n") if k.strip()]
    locations = [l.strip() for l in locations_input.strip().split("\n") if l.strip()]
    
    # Main content area - Split into two columns
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # Scraping section
        st.markdown("## Job Scraper")
        with st.container():
            st.markdown("### Start a New Scrape")
            
            # Validate and start scraping
            if st.button("Start Scraping"):
                errors = validate_input(keywords, locations, linkedin_username, linkedin_password)
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    # Create scraping configuration
                    config = ScrapeConfig(
                        keywords=keywords,
                        locations=locations,
                        job_count=job_count,
                        time_filter_days=time_filter_days,
                        username=linkedin_username,
                        password=linkedin_password,
                        headless=headless,
                        max_workers=max_workers
                    )
                    
                    # Start scraping
                    scraper.start_scraping(config)
                    st.success("Scraping started! See the status section for updates.")
        
        # Status section
        status_container = st.container()
        
        # Results section (when available)
        st.markdown("## Results")
        results_container = st.container()
    
    with col2:
        # Instructions section
        with st.expander("Instructions", expanded=True):
            st.markdown("""
            #### How to use this scraper:
            
            1. Enter your LinkedIn credentials in the sidebar
            2. Add keywords to search for (one per line)
            3. Add locations to search in (one per line)
            4. Adjust advanced options if needed
            5. Click "Start Scraping" to begin
            
            The scraper will search for all combinations of keywords and locations.
            Results will be saved automatically as Excel files.
            
            #### Notes:
            
            - The scraper uses a headless browser by default
            - LinkedIn may rate-limit or block your account if you scrape too many jobs
            - Your credentials are not stored or sent anywhere except to LinkedIn
            """)
    
    # Status update loop
    placeholder = st.empty()
    while True:
        # Get current status
        status = scraper.get_status()
        
        # Update status container
        with status_container:
            display_status_info(status)
        
        # Update results container if jobs available
        with results_container:
            jobs = scraper.get_jobs()
            if jobs:
                st.markdown(f"### Found {len(jobs)} Jobs")
                
                # Preview table
                df = pd.DataFrame(jobs)
                essential_columns = ['job_title', 'company_name', 'location', 'date_posted', 'scraped_keyword', 'scraped_location']
                preview_columns = [col for col in essential_columns if col in df.columns]
                
                st.dataframe(df[preview_columns].head(10))
                
                # Download links
                st.markdown("#### Download Results")
                
                # Direct file download
                output_file = scraper.get_output_file()
                if output_file:
                    download_link = get_download_link(output_file, "Download Excel File")
                    st.markdown(download_link, unsafe_allow_html=True)
                
                # Current preview download
                temp_download = get_table_download_link(df, "linkedin_jobs_preview.xlsx", "Download Current Results")
                st.markdown(temp_download, unsafe_allow_html=True)
            
            else:
                st.info("No jobs found yet. Start scraping to see results here.")
        
        # Sleep to avoid excessive updates
        time.sleep(2)
        
        # Break the loop if not in running state
        if status.status not in ["running", "starting"]:
            break

if __name__ == "__main__":
    main() 