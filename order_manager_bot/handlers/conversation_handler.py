# conversation_handler.py

import logging
from datetime import datetime
import time # Used for unique filename generation
import requests # Used to fetch image data from the provided URL (e.g., WhatsApp media URL)

# Import necessary data from the config file
from config.cake_config import FLOW_MAP, DISPLAY_KEY_MAP, LAYER_SIZE_CONSTRAINTS

# Import the validation function
from validation.validator import validate_input

# NEW IMPORT: Now importing the Drive upload function
from services.google_services import save_order_data, create_calendar_event, upload_and_get_image_url 

# --- STATE STORAGE ---
user_states = {}

# --- NEW: Image Handling Utility ---

def _handle_media_upload(user_id, media_context):
    """
    Handles fetching media from a temporary URL and uploading it to Google Drive.
    
    :param media_context: A dictionary containing media info (e.g., {'url': ..., 'mime_type': ...})
    :return: The Google Drive URL or None.
    """
    if not media_context or not media_context.get('url'):
        logging.warning(f"User {user_id} was at ASK_IMAGE_UPLOAD but no media context was provided.")
        return None

    media_url = media_context['url']
    mime_type = media_context.get('mime_type', 'image/jpeg')
    
    # 1. Fetch the image content from the media service (requires appropriate headers/auth for the source)
    try:
        # NOTE: You MUST replace this 'requests.get' with your actual media fetching logic, 
        # which often requires passing platform-specific authentication headers.
        response = requests.get(media_url, stream=True)
        response.raise_for_status()
        image_data = response.content
    except Exception as e:
        logging.error(f"Failed to fetch image from URL {media_url}: {e}")
        return None
        
    # 2. Generate a unique filename
    extension = mime_type.split('/')[-1].replace('jpeg', 'jpg')
    file_name = f"{user_id}_{int(time.time())}.{extension}"
    
    # 3. Upload to Google Drive
    drive_url = upload_and_get_image_url(image_data, file_name, mime_type)
    
    return drive_url


# --- CORE FUNCTIONS (Rest of file) ---

def _generate_summary_response(user_id):
    # ... (No change) ...
    final_data = user_states[user_id]['data']
    
    summary_lines = ["\n🎂 **Order Summary** 🎂\n"]
    
    for data_key, display_name in DISPLAY_KEY_MAP.items():
        value = final_data.get(data_key)
        
        if value is not None:
            # Check for image_url to show a nice link in the summary
            if data_key == 'image_url' and value and value != 'N/A':
                 summary_lines.append(f"*{display_name}:* [View Image]({value})")
            else:
                 summary_lines.append(f"*{display_name}:* {value}")
            
    final_message = "\n".join(summary_lines)
    
    return final_message


def _final_save_and_end(user_id):
    """Saves the data, creates the calendar event, and generates the final closing message."""
    final_data = user_states[user_id]['data']
    final_data['user_id'] = user_id 
    
    calendar_success = False

    # 1. Create Calendar Event 
    try:
        create_calendar_event(final_data)
        calendar_success = True
    except Exception as e:
        logging.error(f"Failed to create calendar event: {e}")
        calendar_success = False

    # 2. Save Order Data (Sheets)
    save_order_data(final_data) 
    
    # 3. Generate closing message
    closing_message = "\n✅ Thank you! Your confirmed order details have been saved, and we will contact you shortly with a quote."
    
    if calendar_success:
        closing_message += "\n📅 A new event has been added to your Google Calendar for the event date."
    else:
        closing_message += "\n⚠️ Warning: Failed to automatically create the calendar event. Please check your calendar manually."
    
    # Clear state for next conversation
    user_states[user_id] = {'step': 'COMPLETE', 'data': final_data}
    
    return closing_message


def _get_next_step(user_id, incoming_message, media_context=None):
    """Determines the next step based on the current step, user's input, and media context."""
    state = user_states.get(user_id, {'step': 'START', 'data': {}})
    current_step = state['step']
    
    # Implement 'restart' keyword
    if incoming_message.lower().strip() == 'restart':
        user_states[user_id] = {'step': 'START', 'data': {}}
        return 'START', FLOW_MAP['START']['question'] + "\n" + FLOW_MAP['ASK_DATE']['question']


    if current_step == 'START':
        user_states[user_id] = {'step': 'ASK_DATE', 'data': {}}
        return 'ASK_DATE', FLOW_MAP['START']['question'] + "\n" + FLOW_MAP['ASK_DATE']['question']
        
    # --- VALIDATION CHECK ---
    is_valid, feedback = validate_input(user_id, current_step, incoming_message, user_states)

    if not is_valid:
        return current_step, f"🛑 **Validation Error:** {feedback} Please try again: {FLOW_MAP[current_step]['question']}"

    # --- Special Handling for ASK_IMAGE_UPLOAD ---
    if current_step == 'ASK_IMAGE_UPLOAD':
        drive_url = _handle_media_upload(user_id, media_context)
        
        # NOTE: The validation above always returns True, so we must rely on drive_url
        if drive_url:
            user_states[user_id]['data']['image_url'] = drive_url
            user_states[user_id]['step'] = 'ASK_FLAVOR' # Proceed to the next step
            # Return the next question
            return 'ASK_FLAVOR', "Thank you! I've saved the image. " + FLOW_MAP['ASK_FLAVOR']['question']
        else:
            # If upload fails or no media was detected
            user_states[user_id]['data']['image_url'] = 'Upload Failed'
            # Give the user a chance to try again, or skip
            return current_step, "⚠️ I couldn't process that image. Please ensure you send it as a single picture file, or type **Skip** to move to the next question."

    
    # --- 1. Collect and store data (ONLY if input is valid AND not ASK_IMAGE_UPLOAD) ---
    data_key = FLOW_MAP.get(current_step, {}).get('data_key')
    if data_key:
        user_states[user_id]['data'][data_key] = incoming_message

    # --- 2. Determine the NEXT step ---
    next_step = FLOW_MAP[current_step].get('next')
    
    # Handle skip command during image upload step
    if current_step == 'ASK_IMAGE_UPLOAD' and incoming_message.lower().strip() == 'skip':
        user_states[user_id]['data']['image_url'] = 'N/A'
        next_step = 'ASK_FLAVOR'
        
    # Check for conditional branching
    if 'next_if' in FLOW_MAP[current_step]:
        branch = FLOW_MAP[current_step]['next_if']
        key = incoming_message.lower().strip()
        
        if key in ['y', 'yes']: key = 'yes'
        elif key in ['n', 'no']: key = 'no'

        next_step = branch.get(key, next_step) 
        
        # Confirmation denied: send the restart message
        if next_step == 'START' and current_step == 'ASK_CONFIRMATION':
            user_states[user_id] = {'step': 'START', 'data': {}}
            return 'START', "Order canceled. Starting over:\n" + FLOW_MAP['START']['question']


    # --- Dynamic Question Generation (ASK_SIZE and ASK_CONFIRMATION logic remains the same) ---
    if next_step == 'ASK_SIZE':
        # ... (ASK_SIZE logic remains the same) ...
        try:
            chosen_layers = int(user_states[user_id]['data'].get('num_layers'))
        except (ValueError, TypeError):
            return next_step, "Error: Could not determine layers. Please try typing 'Restart'."

        size_options = LAYER_SIZE_CONSTRAINTS.get(chosen_layers, [])
        options_text = ", ".join(size_options).replace('quarter sheet', '**quarter sheet**').replace('half sheet', '**half sheet**')

        dynamic_question = (
            f"You selected **{chosen_layers} layers**. "
            f"What size cake would you like? For {chosen_layers} layers, we offer: \n"
            f"👉 {options_text}.\n\nPlease reply with one of the options (e.g., 10 or quarter sheet)."
        )
        
        user_states[user_id]['step'] = next_step
        return next_step, dynamic_question

    if next_step == 'ASK_CONFIRMATION':
        summary_text = _generate_summary_response(user_id)
        
        user_states[user_id]['step'] = 'ASK_CONFIRMATION'
        return 'ASK_CONFIRMATION', summary_text + "\n\n" + FLOW_MAP['ASK_CONFIRMATION']['question']
    
    # Final Save Step: Confirmation was "Yes"
    if next_step == 'SUMMARY':
        return 'SUMMARY', _final_save_and_end(user_id)
    
    if next_step:
        user_states[user_id]['step'] = next_step
        return next_step, FLOW_MAP[next_step]['question']

    return 'COMPLETE', "I'm sorry, I've lost my place. Please type 'restart' to begin over."


def get_response(user_id, incoming_message, media_context=None):
    """The main entry point for the handler."""
    # NOTE: The signature must be updated to accept media_context
    next_step, response_text = _get_next_step(user_id, incoming_message, media_context)
    return response_text