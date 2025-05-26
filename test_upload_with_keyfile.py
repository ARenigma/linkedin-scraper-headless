#!/usr/bin/env python3
"""
Test script to upload an existing file to Google Drive using the service account file
"""

import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import logger

# Path to the service account file
SERVICE_ACCOUNT_FILE = "service-account.json"
# Google Drive Folder ID (where to upload)
FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "1N2DJlGgDpjTKV4SizuLqo4oxGKOxe5yO")

def upload_to_drive_with_keyfile(file_path):
    """
    Upload a file to Google Drive using the service account file.
    
    Args:
        file_path: Path to the file to upload
        
    Returns:
        str: The Google Drive link to the uploaded file, or None if upload failed
    """
    try:
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return None
            
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            print(f"❌ Service account file not found: {SERVICE_ACCOUNT_FILE}")
            return None
            
        print(f"Using service account file: {SERVICE_ACCOUNT_FILE}")
        
        # Load credentials from the service account file
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        
        # Build the Drive service
        drive_service = build("drive", "v3", credentials=creds)
        print("✅ Successfully authenticated with Google Drive")
        
        # Determine mime type based on file extension
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.xlsx':
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            target_mime_type = "application/vnd.google-apps.spreadsheet"
        elif file_extension == '.csv':
            mime_type = "text/csv"
            target_mime_type = "application/vnd.google-apps.spreadsheet"
        else:
            mime_type = "application/octet-stream"
            target_mime_type = None
            
        # Prepare metadata
        file_metadata = {
            "name": os.path.basename(file_path),
            "parents": [FOLDER_ID]
        }
        
        # Set target mimetype for conversion to Google formats
        if target_mime_type:
            file_metadata["mimeType"] = target_mime_type
            
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        print(f"Uploading file: {file_path}")
        
        # Upload
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,webViewLink"
        ).execute()

        drive_link = file.get("webViewLink")
        print(f"✅ File uploaded to Drive: {drive_link}")
        
        return drive_link

    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None

def main():
    # Path to the file from the logs
    file_path = os.path.join("output", "2025-05-05", "linkedin_jobs_05-05-2025_0203_COMPLETE.xlsx")
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        print("Listing files in the output directory:")
        
        # List files in output to help find the correct file
        for root, dirs, files in os.walk("output"):
            for file in files:
                if file.endswith(".xlsx"):
                    print(f"Found: {os.path.join(root, file)}")
        return
    
    # Try to upload the file
    drive_link = upload_to_drive_with_keyfile(file_path)
    
    if drive_link:
        print(f"✅ Success! File uploaded to: {drive_link}")
    else:
        print("❌ Upload failed. See the error details above.")

if __name__ == "__main__":
    main() 