from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json
import os
import requests
import dotenv
import re
from config import logger

# Load environment variables
dotenv.load_dotenv()

# Google Drive Folder ID (where to upload)
FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "1N2DJlGgDpjTKV4SizuLqo4oxGKOxe5yO")

# Path to the service account file
SERVICE_ACCOUNT_FILE = "service-account.json"

def find_or_create_folder(drive_service, name, parent_id):
    """
    Find a folder in Google Drive or create it if it doesn't exist.
    
    Args:
        drive_service: The Google Drive service instance
        name: Name of the folder to find/create
        parent_id: ID of the parent folder
        
    Returns:
        str: The folder ID
    """
    # Check if folder already exists
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    
    if results.get('files'):
        # Folder exists, return its ID
        return results.get('files')[0].get('id')
    else:
        # Create folder
        folder_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = drive_service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        return folder.get('id')

def create_folder_path(drive_service, path_parts, parent_id=None):
    """
    Create a folder path in Google Drive, creating each folder if it doesn't exist.
    
    Args:
        drive_service: The Google Drive service instance
        path_parts: List of folder names in order
        parent_id: ID of the starting parent folder
        
    Returns:
        str: The ID of the deepest folder
    """
    current_parent = parent_id or FOLDER_ID
    
    for folder_name in path_parts:
        if folder_name:  # Skip empty folder names
            current_parent = find_or_create_folder(drive_service, folder_name, current_parent)
    
    return current_parent

def upload_to_drive(file_path):
    """
    Upload a file to Google Drive following the same folder structure as the local file.
    Supports both Excel files and CSV files.
    Sends a Telegram alert on success or failure.
    
    Args:
        file_path: Path to the file to upload
        
    Returns:
        str: The Google Drive link to the uploaded file, or None if upload failed
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"❌ File not found: {file_path}")
            notify_telegram(f"❌ *Upload failed:* File not found:\n`{file_path}`")
            return None

        # Check if the service account file exists
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            logger.error(f"❌ Service account file not found: {SERVICE_ACCOUNT_FILE}")
            notify_telegram(f"❌ *Upload failed:* Service account file not found.")
            return None
        
        try:
            # Load credentials from the service account file directly
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=["https://www.googleapis.com/auth/drive"]
            )
            drive_service = build("drive", "v3", credentials=creds)
            logger.info("Authentication with Google Drive successful")
        except Exception as e:
            logger.error(f"❌ Failed to authenticate with Google Drive: {e}")
            notify_telegram(f"❌ *Upload failed:* Google Drive authentication error:\n`{e}`")
            return None

        # Determine mime type based on file extension
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.xlsx':
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            target_mime_type = "application/vnd.google-apps.spreadsheet"
        elif file_extension == '.csv':
            mime_type = "text/csv"
            target_mime_type = "application/vnd.google-apps.spreadsheet"
        else:
            # For other file types, upload as is
            mime_type = "application/octet-stream"
            target_mime_type = None
            
        # Create folder structure in Google Drive
        # Extract relative path from full path (assuming it's in OUTPUT_FOLDER)
        from config import OUTPUT_FOLDER
        rel_path = os.path.dirname(file_path)
        
        # Check if the file is in the output folder
        if OUTPUT_FOLDER in rel_path:
            # Extract the path relative to the output folder
            rel_path = rel_path.split(OUTPUT_FOLDER)[-1].strip(os.sep)
            
            # Split the relative path into parts
            path_parts = rel_path.split(os.sep) if rel_path else []
            
            # Create folder structure and get the parent folder ID
            parent_id = create_folder_path(drive_service, path_parts)
        else:
            # If not in output folder, use root folder
            parent_id = FOLDER_ID

        # Prepare metadata
        file_metadata = {
            "name": os.path.basename(file_path),
            "parents": [parent_id]
        }
        
        # Set target mimetype for conversion to Google formats
        if target_mime_type:
            file_metadata["mimeType"] = target_mime_type
            
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

        # Upload
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,webViewLink"
        ).execute()

        drive_link = file.get("webViewLink")
        logger.info(f"✅ File uploaded to Drive: {drive_link}")

        # Telegram success notification
        notify_telegram(f"✅ *LinkedIn Scraper (Headless): Upload successful!*\n\n`{os.path.basename(file_path)}`\n[📄 Open in Drive]({drive_link})")
        
        return drive_link

    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        notify_telegram(f"❌ *LinkedIn Scraper (Headless): Upload to Google Drive failed!*\n\nError:\n`{str(e)}`")
        return None

def upload_screenshot_to_drive(image_path, drive_folder_id=None):
    """
    Upload a PNG screenshot to Google Drive.
    
    Args:
        image_path: Path to the screenshot file
        drive_folder_id: Optional folder ID to upload to (defaults to FOLDER_ID)
        
    Returns:
        str: The Google Drive link to the uploaded screenshot, or None if upload failed
    """
    try:
        if not os.path.exists(image_path):
            logger.error(f"❌ Screenshot not found: {image_path}")
            return None

        # Check if the service account file exists
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            logger.error(f"❌ Service account file not found: {SERVICE_ACCOUNT_FILE}")
            return None
        
        try:
            # Load credentials from the service account file directly
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=["https://www.googleapis.com/auth/drive"]
            )
            drive_service = build("drive", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"❌ Failed to authenticate with Google Drive: {e}")
            return None
            
        # If no specific folder ID, create folder structure based on image path
        if not drive_folder_id:
            from config import SCREENSHOT_FOLDER
            rel_path = os.path.dirname(image_path)
            
            # Check if in screenshots folder
            if SCREENSHOT_FOLDER in rel_path:
                rel_path = rel_path.split(SCREENSHOT_FOLDER)[-1].strip(os.sep)
                path_parts = rel_path.split(os.sep) if rel_path else []
                
                # Create folder named "screenshots" at root level
                screenshots_folder_id = find_or_create_folder(drive_service, SCREENSHOT_FOLDER, FOLDER_ID)
                
                # Create the rest of the folder structure
                parent_id = create_folder_path(drive_service, path_parts, screenshots_folder_id)
            else:
                parent_id = FOLDER_ID
        else:
            parent_id = drive_folder_id

        file_metadata = {
            "name": os.path.basename(image_path),
            "parents": [parent_id]
        }

        media = MediaFileUpload(image_path, mimetype="image/png")

        uploaded = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,webViewLink"
        ).execute()

        logger.info(f"📤 Screenshot uploaded: {uploaded['webViewLink']}")
        return uploaded["webViewLink"]

    except Exception as e:
        logger.error(f"❌ Failed to upload screenshot: {e}")
        return None

def notify_telegram(message):
    """
    Send a notification message to Telegram.
    
    Args:
        message: The message to send
        
    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    try:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            logger.warning("⚠️ Telegram credentials not set. Skipping alert.")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        r = requests.post(url, json=payload)
        if r.status_code == 200:
            logger.info("📨 Telegram alert sent.")
            return True
        else:
            logger.warning(f"⚠️ Failed to send Telegram alert: {r.text}")
            return False

    except Exception as e:
        logger.error(f"❌ Telegram notification error: {e}")
        return False 