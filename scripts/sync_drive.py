#!/usr/bin/env python3
"""
E-Sanjeevani ABDM-UP Automated Google Drive Synchronizer & Hot-Reloader
Synchronizes source spreadsheets from an authorized Google Drive folder
into the dashboard's local /data repository on a scheduled basis,
and pings the local webhook to refresh in-memory cache without restarting.
"""

import os
import io
import sys
import logging
import urllib.request
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("/var/log/esanjivani-dashboard/drive_sync.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/etc/abdm/service_account.json")
DRIVE_FOLDER_ID = os.getenv("DRIVE_SOURCE_FOLDER_ID", "YOUR_DRIVE_FOLDER_ID_HERE")
DATA_DIR = os.getenv("DATA_DIR", "/opt/esanjivani-abdmup-dashboard/data")
DASHBOARD_API_URL = os.getenv("DASHBOARD_API_URL", "http://127.0.0.1:8000/api/v1/internal/reload-data")
SYNC_SECRET = os.getenv("SYNC_WEBHOOK_SECRET", "ABDM_UP_HOT_RELOAD_TOKEN_2026")
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

TARGET_FILES = {
    "E-Sanjeevani_Daily_Reporting_UP_Status.csv": os.path.join(DATA_DIR, "E-Sanjeevani_Daily_Reporting_UP_Status.csv"),
    "E-Sanjeevani_Daily_Reporting_District_Wise_Status.csv": os.path.join(DATA_DIR, "E-Sanjeevani_Daily_Reporting_District_Wise_Status.csv")
}

def get_drive_service():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Service account key not found at: {SERVICE_ACCOUNT_FILE}")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

def notify_dashboard_reload():
    logging.info("Triggering in-memory hot reload via webhook...")
    try:
        req = urllib.request.Request(
            DASHBOARD_API_URL,
            data=b"",
            headers={
                "X-Sync-Token": SYNC_SECRET,
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            logging.info(f"Dashboard webhook hot-reload response: {body}")
    except Exception as e:
        logging.warning(f"Could not reach dashboard hot-reload webhook: {e}")

def sync_files():
    logging.info("Initiating Google Drive sync for ABDM-UP E-Sanjeevani datasets...")
    service = get_drive_service()
    
    query = f"'{DRIVE_FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, modifiedTime)"
    ).execute()
    
    items = results.get('files', [])
    if not items:
        logging.warning(f"No files discovered in Drive folder: {DRIVE_FOLDER_ID}")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    updated_any = False

    for item in items:
        file_name = item['name']
        file_id = item['id']
        mime_type = item['mimeType']
        
        matched_target = None
        for target_name, target_path in TARGET_FILES.items():
            if target_name.lower() in file_name.lower():
                matched_target = (target_name, target_path)
                break
                
        if not matched_target:
            continue
            
        target_name, local_path = matched_target
        logging.info(f"Downloading updated file: {file_name} (ID: {file_id}) -> {local_path}")
        
        if mime_type == 'application/vnd.google-apps.spreadsheet':
            request = service.files().export_media(fileId=file_id, mimeType='text/csv')
        else:
            request = service.files().get_media(fileId=file_id)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        temp_path = f"{local_path}.tmp"
        with open(temp_path, "wb") as f:
            f.write(fh.getvalue())
        os.replace(temp_path, local_path)
        logging.info(f"Successfully synced: {target_name}")
        updated_any = True

    logging.info("Google Drive synchronization completed.")
    if updated_any:
        notify_dashboard_reload()

if __name__ == "__main__":
    try:
        sync_files()
    except Exception as e:
        logging.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)
