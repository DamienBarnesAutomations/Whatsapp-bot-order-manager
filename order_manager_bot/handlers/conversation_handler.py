# conversation_handler.py

from datetime import datetime, timedelta
import logging
import re
# Import the Sheets saving function. This requires google_sheets_drive.py 
# to be present and successfully initialized.
from services.google_services import save_order_data 

logging.basicConfig(level=logging.INFO)

# --- CAKE CONFIGURATION AND RULES ---
# Defines valid flavors and layer/size constraints.
CAKE_CONFIG = {
    # Full list of available flavors
    "vanilla bean": {},
    "carrot": {},
    "lemon": {},
    "coconut": {},
    "marble": {},
    "chocolate": {},
    "strawberry": {},
    "cookies and cream": {},
    "red velvet": {},
    "banana bread": {},
    "caribbean fruit/ rum": {},
    "butter pecan": {},
    "white chocolate sponge": {},
    "pineapple sponge": {},
}

# Defines which sizes are available for a given number of layers.
# Note: Sizes are listed with their layer count to make selection explicit for the user.
LAYER_SIZE_CONSTRAINTS = {
    1: ['6-inch 1 layer', '8-inch 1 layer', '9-inch 1 layer', '10-inch 1 layer', '12-inch 1 layer', 'quarter sheet 1 layer', 'half sheet 1 layer'],
    2: ['6-inch 2 layers', '8-inch 2 layers', '9-inch 2 layers', '10-inch 2 layers', '12-inch 2 layers', 'quarter sheet 2 layers', 'half sheet 2 layers'],
    3: ['6-inch 3 layers', '8-inch 3 layers'],
}
VALID_LAYERS = list(LAYER_SIZE_CONSTRAINTS.keys())

# Lists derived from config for simpler validation checks
VALID_FLAVORS = list(CAKE_CONFIG.keys()) 
VALID_SIZES = sorted(list(size for sizes in LAYER_SIZE_CONSTRAINTS.values() for size in sizes))
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
            # Skipping image upload step for now, but recording the answer
            'yes': 'ASK_FLAVOR',
            'no': 'ASK_FLAVOR',
        },
    },
    # Image upload step skipped until Google Drive API is implemented.
    'ASK_FLAVOR': {
        'question': f'What flavor would you like? We offer: {", ".join([f.title() for f in VALID_FLAVORS])}.',
        'data_key': 'cake_flavor',
        'next': 'ASK_LAYERS',
    },
    'ASK_LAYERS': {
        'question': f'How many layers would you like? We support: {", ".join(map(str, VALID_LAYERS))} layers.',
        'data_key': 'num_layers',
        'next': 'ASK_SIZE',
    },
    'ASK_SIZE': {
        'question': 'What size cake would you like? Please reply with one of the available options based on your layer choice (e.g., 8-inch 2 layers, quarter sheet 1 layer).',
        'data_key': 'cake_size',
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
    'num_layers': 'Number of Layers',
    'cake_size': 'Cake Size',
    'num_tiers': 'Number of Tiers',
    'cake_color': 'Primary Color',
    'cake_theme': 'Theme/Description',
    'venue_indoors': 'Venue Indoors?',
    'venue_ac': 'Venue with A/C?',
    'has_picture': 'Picture Sent?',
}

# --- STATE STORAGE ---
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

    # --- Flavor Validation (List/Lookup) ---
    if current_step == 'ASK_FLAVOR':
        if message in VALID_FLAVORS: 
            return True, None
        return False, f"Sorry, we only offer these flavors: {', '.join([f.title() for f in VALID_FLAVORS])}. Please choose one."
        
    # --- Numeric Validation (Layers) ---
    if current_step == 'ASK_LAYERS':
        try:
            requested_layers = int(incoming_message)
            if requested_layers in VALID_LAYERS:
                return True, None
            return False, f"We only support {', '.join(map(str, VALID_LAYERS))} layers. Please choose one of those numbers."
        except ValueError:
            return False, "Please enter a valid number for layers (e.g., 2)."

    # --- Combined Validation: SIZE (Must match previously selected layers) ---
    if current_step == 'ASK_SIZE':
        # 1. Fetch the previously chosen number of layers
        user_data = user_states.get(user_id, {}).get('data', {})
        try:
            chosen_layers = int(user_data.get('num_layers'))
        except (ValueError, TypeError):
            # Should not happen if flow is followed, but as a safety check
            return False, "Error: Please tell me the number of layers before choosing a size."

        # 2. Get the list of valid sizes for those layers
        valid_sizes_for_layers = LAYER_SIZE_CONSTRAINTS.get(chosen_layers, [])
        
        # 3. Check if the user's input matches an available size
        if message in [s.lower() for s in valid_sizes_for_layers]:
            return True, None
        
        # 4. If invalid, provide a helpful error showing valid options
        return False, (
            f"The size you entered is not available for {chosen_layers} layers. "
            f"Please choose from these options: {', '.join(valid_sizes_for_layers)}."
        )


    # --- Numeric Validation (Tiers) ---
    if current_step == 'ASK_TIERS': 
        try:
            number = int(incoming_message)
            if 1 <= number <= 5: 
                return True, None
            return False, "Please enter a single digit number between 1 and 5 for the number of tiers."
        except ValueError:
            return False, "Please enter a valid number (e.g., 2)."
            
        
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
    
    # CRITICAL FIX: Ensure the user_id is saved into the data dictionary
    final_data['user_id'] = user_id 

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
    
    if incoming_message.lower().strip() == 'reset':
        user_states[user_id] = {'step': 'START', 'data': {}}
        return 'START', FLOW_MAP['START']['question']

    if current_step == 'START':
        user_states[user_id] = {'step': 'ASK_DATE', 'data': {}}
        return 'ASK_DATE', FLOW_MAP['ASK_DATE']['question']
        
    # --- VALIDATION CHECK ---
    is_valid, feedback = _validate_input(user_id, current_step, incoming_message)

    if not is_valid:
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

    return 'COMPLETE', "I'm sorry, I've lost my place. Please type 'reset' to start over."


def get_response(user_id, incoming_message):
    """The main entry point for the handler."""
    next_step, response_text = _get_next_step(user_id, incoming_message)
    return response_text