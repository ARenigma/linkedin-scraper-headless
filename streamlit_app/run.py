#!/usr/bin/env python3
"""
Entry point script for the LinkedIn Job Scraper Streamlit app.
"""
import os
import subprocess
import streamlit.web.cli as stcli
import sys

def run_streamlit():
    """Run the Streamlit app."""
    # Make sure the current directory is in the path
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    
    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    
    # Check if Playwright is installed
    try:
        subprocess.run(["playwright", "--version"], 
                       check=True, 
                       stdout=subprocess.PIPE, 
                       stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Installing Playwright...")
        subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
    
    # Run the app
    sys.argv = ["streamlit", "run", "app.py", "--browser.serverAddress=0.0.0.0", "--server.enableCORS=false"]
    sys.exit(stcli.main())

if __name__ == "__main__":
    run_streamlit() 