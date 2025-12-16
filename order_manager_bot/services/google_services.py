# services/google_services.py

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime
import io
import logging
import os

# --- Configuration (using environment variables from your code) ---
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar'
]

CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID") # Used for image upload
CALENDAR_ID = os.environ.get("CALENDAR_ID") # Used for calendar creation

gc = None
sheets_service = None # Not strictly needed if using gspread, but kept for consistency
drive_service = None
calendar_service = None # NEW: Global variable for Calendar service
worksheet = None

# --- Initialization Function ---
def initialize_google_apis():
    """Authenticates and initializes all required Google API clients."""
    global gc, sheets_service, drive_service, calendar_service, worksheet
    
    try:
        # 1. Authenticate with the Service Account JSON file
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        logging.info("Credentials initialized.")

        # 2. Initialize gspread (for Sheets data entry)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.sheet1 
        logging.info("Google Sheets API (gspread) initialized successfully.")
        
        # 3. Initialize Drive API Client (for image uploads)
        drive_service = build('drive', 'v3', credentials=creds)
        logging.info("Google Drive API initialized successfully.")
        
        # 4. Initialize Calendar API Client (for event creation)
        calendar_service = build('calendar', 'v3', credentials=creds)
        logging.info("Google Calendar API initialized successfully.")
        
    except Exception as e:
        logging.error(f"FATAL: Failed to initialize Google APIs. Error: {e}")
        gc = None 
        worksheet = None
        drive_service = None
        calendar_service = None

# Run initialization once on startup
initialize_google_apis()


# --- Sheets Core Function (No change needed here) ---
def save_order_data(data):
    """
    Saves a completed order dictionary to the Google Sheet.
    """
    if worksheet is None:
        logging.error("Cannot save data: Google Sheets not initialized.")
        return False

    try:
        # Define the header keys in the required order (matching your Sheet columns)
        # Assuming the first column is the timestamp (added below)
        HEADERS = [
            'user_id', 'event_date', 'cake_flavor', 'cake_size', 'num_layers', 
            'num_tiers', 'cake_color', 'venue_indoors', 'venue_ac', 
            'has_picture', 'cake_theme', 'image_url'
        ]

        # Prepare the row data
        row_data = [datetime.now().strftime('%Y-%m-%d %H:%M:%S')] # Timestamp (Column A)
        
        for key in HEADERS:
            # Append the data, ensuring 'image_url' is included if set
            row_data.append(data.get(key, ''))
            
        worksheet.append_row(row_data, value_input_option='USER_ENTERED')
        logging.info("Order data successfully appended to Google Sheet.")
        return True
        
    except Exception as e:
        logging.error(f"Error appending data to Google Sheet: {e}")
        return False


# --- Drive Core Function (FULLY IMPLEMENTED) ---
def upload_and_get_image_url(image_data, file_name, mime_type):
    """
    Uploads the image file (binary data) to Google Drive and returns the shareable URL.
    :param image_data: Binary content of the image (e.g., from requests.get().content)
    :param file_name: The desired filename in Drive (e.g., user_id-timestamp.jpg)
    :param mime_type: The MIME type of the file (e.g., image/jpeg)
    :return: The shareable web view link, or None on failure.
    """
    if drive_service is None or DRIVE_FOLDER_ID is None:
        logging.error("Cannot upload image: Google Drive or FOLDER_ID not initialized.")
        return None

    try:
        # 1. Prepare the file metadata
        file_metadata = {
            'name': file_name,
            'parents': [DRIVE_FOLDER_ID]
        }
        
        # 2. Convert binary data to a file-like object
        media = MediaIoBaseUpload(io.BytesIO(image_data), 
                                  mimetype=mime_type, 
                                  chunksize=1024*1024, 
                                  resumable=True)
        
        # 3. Upload the file
        file = drive_service.files().create(body=file_metadata,
                                            media_body=media,
                                            fields='id, webViewLink, parents').execute()
        
        file_id = file.get('id')
        logging.info(f"File uploaded successfully. ID: {file_id}")
        
        # 4. Set permission to 'anyone' to make it publicly viewable (optional but common for bots)
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        web_view_link = file.get('webViewLink')
        logging.info(f"Permission set to public. URL: {web_view_link}")
        return web_view_link

    except Exception as e:
        logging.error(f"Error uploading file to Google Drive: {e}")
        return None


# --- Calendar Core Function (FULLY IMPLEMENTED) ---
def create_calendar_event(data):
    """
    Creates an all-day event in the configured Google Calendar.
    """
    if calendar_service is None or CALENDAR_ID is None:
        logging.error("Calendar service or CALENDAR_ID not initialized. Cannot create event.")
        raise ConnectionError("Calendar service connection failed.")

    try:
        date_str = data.get('event_date') # Format: DD/MM/YYYY
        event_date_obj = datetime.strptime(date_str, '%d/%m/%Y')
        
        # Extract data for event details
        flavor = data.get('cake_flavor', 'Custom')
        size = data.get('cake_size', 'Unknown Size')
        theme = data.get('cake_theme', 'Unknown Theme')
        user_id = data.get('user_id', 'Unknown Customer')
        
        event_title = (
            f"CAKE ORDER: {flavor.title()} ({size}) - {theme}"
        )
        
        event_description = (
            f"Customer Phone: {user_id}\n"
            f"Flavor: {flavor.title()}\n"
            f"Size/Layers: {size} ({data.get('num_layers')} layers)\n"
            f"Tiers: {data.get('num_tiers')}\n"
            f"Primary Color: {data.get('cake_color')}\n"
            f"Theme: {theme}\n"
            f"Venue Indoors: {data.get('venue_indoors')}, A/C: {data.get('venue_ac')}\n"
            f"Picture Sent: {data.get('has_picture')}\n"
            f"Image URL: {data.get('image_url', 'N/A')}\n"
            f"--- Generated by Cake Bot ---"
        )
        
        date_api_format = event_date_obj.strftime('%Y-%m-%d')
        
        event = {
            'summary': event_title,
            'description': event_description,
            'start': {'date': date_api_format},
            'end': {'date': date_api_format},
            'reminders': {'useDefault': True},
        }
        
        # Insert the Event via API Call
        calendar_service.events().insert(
            calendarId=CALENDAR_ID, 
            body=event
        ).execute()
        
        logging.info(f"Calendar event created successfully for: {event_title}")
        return True

    except Exception as e:
        logging.error(f"Error creating calendar event for {user_id}: {e}")
        raise # Re-raise to be caught by conversation_handler