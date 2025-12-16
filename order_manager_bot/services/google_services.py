import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime
import io
import logging
import os

logging.basicConfig(level=logging.INFO)

# --- Configuration ---
# Note the SCOPES now includes both Sheets and Drive access
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")


gc = None
sheets_service = None
drive_service = None
worksheet = None

# --- Initialization Function ---
def initialize_google_apis():
    """Authenticates and initializes gspread for Sheets and googleapiclient for Drive."""
    global gc, sheets_service, drive_service, worksheet
    
    try:
        # 1. Authenticate with the Service Account JSON file
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        logging.info("Creditentials %s", creds)

        # 2. Initialize gspread (for Sheets)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open(SPREADSHEET_ID)
        worksheet = spreadsheet.sheet1 
        logging.info("Google Sheets API (gspread) initialized successfully.")
        
        # 3. Initialize Drive API Client (for image uploads)
        drive_service = build('drive', 'v3', credentials=creds)
        logging.info("Google Drive API initialized successfully.")
        
    except Exception as e:
        logging.error(f"Failed to initialize Google APIs. Check credentials.json and sharing permissions: {e}")
        # Set all global variables to None to indicate failure
        gc = None 
        worksheet = None
        drive_service = None

# Run initialization once on startup
initialize_google_apis()


# --- Sheets Core Function ---
def save_order_data(data):
    """
    Saves a completed order dictionary to the Google Sheet.
    :param data: The dictionary of order details (from user_states['data']).
    """
    if worksheet is None:
        logging.error("Cannot save data: Google Sheets not initialized.")
        return

    try:
        # Define the header keys in the required order (matching your Sheet columns)
        HEADERS = [
            'user_id', 'event_date', 'cake_flavor', 'cake_size', 'num_layers', 
            'num_tiers', 'cake_color', 'venue_indoors', 'venue_ac', 
            'has_picture', 'cake_theme', 'image_url'
        ]

        # Prepare the row data
        row_data = [datetime.now().strftime('%Y-%m-%d %H:%M:%S')] # Timestamp (Column A)
        
        for key in HEADERS:
            # Append the data, using a default empty string if the key doesn't exist (e.g., theme is optional)
            row_data.append(data.get(key, ''))
            
        # Append the new row to the sheet
        worksheet.append_row(row_data, value_input_option='USER_ENTERED')
        logging.info("Order data successfully appended to Google Sheet.")
        
    except Exception as e:
        logging.error(f"Error appending data to Google Sheet: {e}")


# --- Drive Core Function (Placeholder for now) ---
def upload_and_get_image_url(image_data, file_name, mime_type):
    """
    Placeholder: Uploads the image file to Google Drive and returns the shareable URL.
    We will finalize this function in the next step.
    """
    logging.warning("Drive upload function is currently a placeholder.")
    return "DRIVE_UPLOAD_PENDING_URL"