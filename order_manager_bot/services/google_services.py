# services/google_services.py

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, date
import logging
import os

# --- Configuration (using environment variables from your code) ---
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    # 'https://www.googleapis.com/auth/drive', # <<< REMOVED: No longer using Google Drive API
    'https://www.googleapis.com/auth/calendar'
]

CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
# DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID") # <<< REMOVED: No longer needed
CALENDAR_ID = os.environ.get("CALENDAR_ID")

gc = None
calendar_service = None
worksheet = None
# drive_service = None # <<< REMOVED

# --- Initialization Function ---
def initialize_google_apis():
    """Authenticates and initializes all required Google API clients."""
    global gc, calendar_service, worksheet
    
    try:
        # 1. Authenticate with the Service Account JSON file
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        logging.info("Credentials initialized.")

        # 2. Initialize gspread (for Sheets data entry and reading)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.sheet1 
        logging.info("Google Sheets API (gspread) initialized successfully.")
        
        # 3. Initialize Calendar API Client (for event creation)
        calendar_service = build('calendar', 'v3', credentials=creds)
        logging.info("Google Calendar API initialized successfully.")
        
    except Exception as e:
        logging.error(f"FATAL: Failed to initialize Google APIs. Error: {e}")
        gc = None 
        worksheet = None
        calendar_service = None

# Run initialization once on startup
initialize_google_apis()


# --- Sheets Core Function: Save Data ---
def save_order_data(data):
    """
    Saves a completed order dictionary to the Google Sheet.
    """
    if worksheet is None:
        logging.error("Cannot save data: Google Sheets not initialized.")
        return False

    try:
        # Define the header keys in the required order (matching your Sheet columns)
        # Note: Order is crucial. Timestamp is the first column.
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

# --- Sheets Core Function: Retrieve Future Orders (NEW) ---
def get_future_orders(user_id):
    """
    Retrieves all orders for the given user_id where the event date is today or in the future.
    
    :param user_id: The sender's phone number.
    :return: A list of dictionaries, one for each future order, or an empty list.
    """
    if worksheet is None:
        logging.error("Cannot retrieve data: Google Sheets not initialized.")
        return []
    
    today = date.today()
    future_orders = []
    
    try:
        # Fetch all records as a list of dictionaries (key=header, value=cell content)
        all_records = worksheet.get_all_records()
        
        # NOTE: We assume the column headers in your sheet are exactly: 
        # ['Timestamp', 'user_id', 'event_date', 'cake_flavor', ...]
        
        for order in all_records:
            # 1. Check if the order belongs to the current user
            if str(order.get('user_id')) == str(user_id):
                
                # 2. Check the date
                event_date_str = order.get('event_date')
                try:
                    # Convert DD/MM/YYYY to a datetime.date object
                    event_date_obj = datetime.strptime(event_date_str, '%d/%m/%Y').date()
                    
                    # Check if the date is today or in the future
                    if event_date_obj >= today:
                        # Convert date back to a clean string for display
                        order['event_date'] = event_date_obj.strftime('%d %b %Y')
                        future_orders.append(order)
                        
                except ValueError:
                    logging.warning(f"Skipping order with invalid date format: {event_date_str}")
                    continue
                    
        # Sort orders by date (earliest first)
        future_orders.sort(key=lambda x: datetime.strptime(x['event_date'], '%d %b %Y'))
        
        return future_orders
        
    except Exception as e:
        logging.error(f"Error retrieving orders from Google Sheet: {e}")
        return []


# --- Drive Core Function (REMOVED) ---
# NOTE: The upload_and_get_image_url function is no longer here. 
# The caller (conversation_handler.py) must now use cloudinary_services.py instead.


# --- Calendar Core Function (No change needed here) ---
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