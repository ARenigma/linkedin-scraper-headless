#!/usr/bin/env python3
"""
Test script to upload an existing file to Google Drive
"""

import os
import json
import dotenv
from upload_to_drive import upload_to_drive
from config import logger

def debug_json_cleaning():
    """Debug and clean the JSON string from the environment"""
    # Load environment variables
    dotenv.load_dotenv()
    
    # Get the GDRIVE_KEY_JSON
    gdrive_key_json = os.getenv("GDRIVE_KEY_JSON")
    if not gdrive_key_json:
        print("GDRIVE_KEY_JSON environment variable not set")
        return None
    
    print(f"JSON Length: {len(gdrive_key_json)}")
    print(f"Character at position 161: ASCII {ord(gdrive_key_json[161])}")
    
    # Try various cleaning approaches
    
    # Method 1: Replace literal \n with actual newlines
    cleaned_json1 = gdrive_key_json.replace('\\n', '\n')
    
    # Method 2: Remove ALL control characters (only keep printable characters)
    cleaned_json2 = ''.join(c for c in gdrive_key_json if c >= ' ')
    
    # Method 3: Replace line breaks and tabs with spaces
    cleaned_json3 = gdrive_key_json.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    
    # Method 4: Extreme cleaning - strip all non-alphanumeric characters except for essential JSON syntax
    import re
    cleaned_json4 = re.sub(r'[^\x20-\x7E]', '', gdrive_key_json)
    
    # Try parsing each version
    methods = [
        ("Original", gdrive_key_json),
        ("Method 1: Replace \\n", cleaned_json1),
        ("Method 2: Remove control chars", cleaned_json2),
        ("Method 3: Replace breaks with spaces", cleaned_json3),
        ("Method 4: Regex cleaning", cleaned_json4)
    ]
    
    for name, json_str in methods:
        try:
            data = json.loads(json_str)
            print(f"✅ {name} - Successfully parsed JSON")
            return json_str
        except json.JSONDecodeError as e:
            print(f"❌ {name} - Failed: {e}")
    
    return None

def main():
    # First try to debug and clean the JSON
    print("==== Debugging JSON parsing ====")
    clean_json = debug_json_cleaning()
    
    if not clean_json:
        print("Could not clean JSON. Please fix your GDRIVE_KEY_JSON in .env")
        return
    
    print("\n==== Testing file upload ====")
    # Path to the file from the logs
    file_path = os.path.join("output", "2025-05-05", "linkedin_jobs_05-05-2025_0203_COMPLETE.xlsx")
    
    # Check if file exists
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        print(f"File not found: {file_path}")
        print("Listing files in the output directory:")
        
        # List files in output to help find the correct file
        for root, dirs, files in os.walk("output"):
            for file in files:
                if file.endswith(".xlsx"):
                    print(f"Found: {os.path.join(root, file)}")
        return
    
    print(f"Uploading file: {file_path}")
    
    # Try to upload the file
    drive_link = upload_to_drive(file_path)
    
    if drive_link:
        print(f"✅ Success! File uploaded to: {drive_link}")
    else:
        print("❌ Upload failed. Check the logs for details.")

if __name__ == "__main__":
    main() 