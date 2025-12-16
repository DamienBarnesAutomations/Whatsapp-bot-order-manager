# conversation_handler.py

from datetime import datetime, timedelta
import logging
import re
# Import the Sheets saving function. This requires google_sheets_drive.py 
# to be present and successfully initialized.
from services.google_services import save_order_data 

logging.basicConfig(level=logging.INFO)

# --- CAKE CONFIGURATION AND RULES ---
# Defines valid flavor/size combinations and their supported layer counts
CAKE_CONFIG = {
    # FLAVOR: {SIZE: [VALID_LAYERS]}
    "chocolate": {
        "small (6-inch)": [2, 3],
        "medium (8-inch)": [2, 3, 4],
        "large (10-inch)": [3, 4, 5]
    },
    "vanilla": {
        "small (6-inch)": [2, 3],
        "medium (8-inch)": [2, 3, 4],
        "large (10-inch)": [3, 4]
    },
    "red velvet": {
        "medium (8-inch)": [3, 4],
        "large (10-inch)": [3, 4, 5]
    },
    "lemon": {
        "small (6-inch)": [2],
        "medium (8-inch)": [2, 3]
    },
}

# Lists derived from config for simpler validation checks
VALID_FLAVORS = list(CAKE_CONFIG.keys()) 
VALID_SIZES = sorted(list(set(s for config in CAKE_CONFIG.values() for s in config.keys())))
VALID_YES_NO = ['yes', 'y', 'no', 'n']

# --- FLOW AND STATE MAPS ---

FLOW_MAP = {
    'START': {
        'question': 'Welcome to the Cake Bot! I can help you place an order. What is the date of the event? (Please reply with DD/MM/YYYY)',
        'data_key': None,
        'next': 'ASK_DATE',
    },
    'ASK_DATE': {
        'question': 'What is the date of the event? (Please reply with DD/MM/YYYY)',
        'data_key': 'event_date',
        'next': 'ASK_CUSTOM_PICTURE',
    },
    'ASK_CUSTOM_PICTURE': {
        'question': 'Do you have a picture of the custom cake you would like? (Yes/No)',
        'data_key': 'has_picture',
        'next_if': {
            # NOTE: We temporarily skip the image upload step and go straight to flavor
            'yes': 'ASK_FLAVOR',
            'no': 'ASK_FLAVOR',
        },
    },
    # 'ASK_IMAGE_UPLOAD': { 
    #     'question': 'Please upload the picture now!',
    #     'data_key': 'image_url', # Stored later via whatsapp_handler/google_sheets_drive
    #     'next': 'ASK_FLAVOR',
    # },
    'ASK_FLAVOR': {
        'question': f'What flavor would you like? We offer: {", ".join(VALID_FLAVORS).title()}.',
        'data_key': 'cake_flavor',
        'next': 'ASK_SIZE',
    },
    'ASK_SIZE': {
        'question': f'What size cake? We offer: {", ".join(VALID_SIZES).title()}.',
        'data_key': 'cake_size',
        'next': 'ASK_LAYERS',
    },
    'ASK_LAYERS': {
        'question': 'How many layers would you like? (A number)',
        'data_key': 'num_layers',
        'next': 'ASK_TIERS',
    },
    'ASK_TIERS': {
        'question': 'How many tiers (levels) will the cake have? (A number)',
        'data_key': 'num_tiers',
        'next': 'ASK_COLOR',
    },
    'ASK_COLOR': {
        'question': 'What is the primary color of the cake?',
        'data_key': 'cake_color',
        'next': 'ASK_THEME',
    },
    'ASK_THEME': {
        'question': 'What is the theme or general description (e.g., Star Wars, Floral, Simple)?',
        'data_key': 'cake_theme',
        'next': 'ASK_INDOORS',
    },
    'ASK_INDOORS': {
        'question': 'Will the cake be displayed indoors? (Yes/No)',
        'data_key': 'venue_indoors',
        'next': 'ASK_AC',
    },
    'ASK_AC': {
        'question': 'Does the venue have air conditioning? (Critical for stability - Yes/No)',
        'data_key': 'venue_ac',
        'next': 'SUMMARY',
    },
}

# Mapping of technical data keys to human-readable display names for the final summary
DISPLAY_KEY_MAP = {
    'event_date': 'Event Date',
    'cake_flavor': 'Cake Flavor',
    'cake_size': 'Cake Size',
    'num_layers': 'Number of Layers',
    'num_tiers': 'Number of Tiers',
    'cake_color': 'Primary Color',
    'cake_theme': 'Theme/Description',
    'venue_indoors': 'Venue Indoors?',
    'venue_ac': 'Venue with A/C?',
    'has_picture': 'Picture Sent?',
}

# --- STATE STORAGE ---
# Global dictionary to hold user state: {phone_number: {'step': 'STEP_NAME', 'data': {...}}}
user_states = {}

# --- VALIDATION LOGIC ---

def _validate_input(user_id, current_step, incoming_message):
    """
    Validates the user's input based on the current step's requirements and business rules.
    Returns (is_valid: bool, feedback_message: str)
    """
    message = incoming_message.strip().lower()
    
    # --- Date Validation (Specific Format and Future Check) ---
    if current_step == 'ASK_DATE':
        try:
            event_date = datetime.strptime(incoming_message, '%d/%m/%Y')
            if event_date < datetime.now() - timedelta(hours=24): 
                return False, "That date is in the past! Please provide a future date (DD/MM/YYYY)."
            return True, None
        except ValueError:
            return False, "I couldn't understand that date format. Please reply with **DD/MM/YYYY** (e.g., 25/12/2026)."

    # --- Binary Validation (Yes/No) ---
    if current_step in ['ASK_CUSTOM_PICTURE', 'ASK_INDOORS', 'ASK_AC']:
        if message in VALID_YES_NO:
            return True, None
        return False, "Please reply with a simple **Yes** or **No**."

    # --- Flavor and Size Validation (List/Lookup) ---
    if current_step == 'ASK_FLAVOR':
        if message in VALID_FLAVORS: 
            return True, None
        return False, f"Sorry, we only offer these flavors: {', '.join(VALID_FLAVORS).title()}. Please choose one."
        
    if current_step == 'ASK_SIZE':
        if message in VALID_SIZES:
            return True, None
        return False, f"Sorry, we only offer these sizes: {', '.join(VALID_SIZES).title()}. Please choose one."

    # --- Numeric Validation (Tiers) ---
    if current_step == 'ASK_TIERS': 
        try:
            number = int(incoming_message)
            if 1 <= number <= 5: 
                return True, None
            return False, "Please enter a single digit number between 1 and 5 for the number of tiers."
        except ValueError:
            return False, "Please enter a valid number (e.g., 2)."
            
    # --- COMBINED VALIDATION: LAYERS (Business Logic) ---
    if current_step == 'ASK_LAYERS':
        try:
            requested_layers = int(incoming_message)
        except ValueError:
            return False, "Please enter a valid number for layers (e.g., 3)."

        user_data = user_states.get(user_id, {}).get('data', {})
        chosen_flavor = user_data.get('cake_flavor', '').lower()
        chosen_size = user_data.get('cake_size', '').lower()

        valid_layers = CAKE_CONFIG.get(chosen_flavor, {}).get(chosen_size)

        if valid_layers is None:
            return False, "Error: I could not validate that flavor/size combination. Please try again from the start."
            
        if requested_layers not in valid_layers:
            return False, (
                f"Sorry, a {chosen_size} cake in {chosen_flavor.title()} only supports "
                f"**{', '.join(map(str, valid_layers))}** layers. Please choose one of those numbers."
            )
            
        return True, None
        
    # --- Length/Contextual Validation (Theme and Color) ---
    if current_step in ['ASK_THEME', 'ASK_COLOR']:
        if len(message) < 2: 
            return False, "Please provide a more descriptive answer (at least 2 characters)."

    # If no specific rule applied, assume valid
    return True, None

# --- STATE MANAGEMENT CORE ---

def _generate_summary_response(user_id):
    """Generates a final summary message, saves data, and clears the state."""
    final_data = user_states[user_id]['data']
    final_data['user_id'] = user_id 
    logging.info("Final Data: %s", final_data)
    # Save the data to Google Sheets
    save_order_data(final_data) 
    
    # --- Generate Human-Friendly Summary ---
    summary_lines = ["\n🎂 **Order Summary** 🎂\n"]
    
    for data_key, display_name in DISPLAY_KEY_MAP.items():
        value = final_data.get(data_key)
        
        if value is not None:
            summary_lines.append(f"*{display_name}:* {value}")
            
    # Add a closing message
    summary_lines.append("\n✅ Thank you! Your order details have been saved, and we will contact you shortly with a quote.")
    
    final_message = "\n".join(summary_lines)
    
    # Clear state for next conversation
    user_states[user_id] = {'step': 'COMPLETE', 'data': final_data}
    
    return final_message

def _get_next_step(user_id, incoming_message):
    """Determines the next step based on the current step and the user's input."""
    state = user_states.get(user_id, {'step': 'START', 'data': {}})
    current_step = state['step']
    
    # Allow user to reset at any point
    if incoming_message.lower().strip() == 'reset':
        user_states[user_id] = {'step': 'START', 'data': {}}
        return 'START', FLOW_MAP['START']['question']

    if current_step == 'START':
        user_states[user_id] = {'step': 'ASK_DATE', 'data': {}}
        return 'ASK_DATE', FLOW_MAP['ASK_DATE']['question']
        
    # --- VALIDATION CHECK (Runs on every step after START) ---
    is_valid, feedback = _validate_input(user_id, current_step, incoming_message)

    if not is_valid:
        # Stay on the current step and send feedback
        return current_step, f"🛑 **Validation Error:** {feedback} Please try again: {FLOW_MAP[current_step]['question']}"

    # --- 1. Collect and store data (ONLY if input is valid) ---
    data_key = FLOW_MAP.get(current_step, {}).get('data_key')
    if data_key:
        user_states[user_id]['data'][data_key] = incoming_message

    # --- 2. Determine the NEXT step ---
    next_step = FLOW_MAP[current_step].get('next')
    
    # Check for conditional branching (ASK_CUSTOM_PICTURE only for now)
    if 'next_if' in FLOW_MAP[current_step]:
        branch = FLOW_MAP[current_step]['next_if']
        key = incoming_message.lower().strip()
        
        if key in ['y', 'yes']:
            key = 'yes'
        elif key in ['n', 'no']:
            key = 'no'

        next_step = branch.get(key, next_step) 

    if next_step == 'SUMMARY':
        return 'SUMMARY', _generate_summary_response(user_id)
    
    if next_step:
        user_states[user_id]['step'] = next_step
        return next_step, FLOW_MAP[next_step]['question']

    # Default fallback
    return 'COMPLETE', "I'm sorry, I've lost my place. Please type 'reset' to start over."


def get_response(user_id, incoming_message):
    """The main entry point for the handler."""
    next_step, response_text = _get_next_step(user_id, incoming_message)
    return response_text