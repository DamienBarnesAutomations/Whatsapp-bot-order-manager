# conversation_handler.py

from datetime import datetime, timedelta
import logging
# RENAME: Changing import path to the requested format
from services.google_services import save_order_data 

logging.basicConfig(level=logging.INFO)

# --- CAKE CONFIGURATION AND RULES ---
# Defines valid flavors and layer/size constraints.
CAKE_CONFIG = {
    # Full list of available flavors (kept for list check)
    "vanilla bean": {}, "carrot": {}, "lemon": {}, "coconut": {},
    "marble": {}, "chocolate": {}, "strawberry": {}, "cookies and cream": {},
    "red velvet": {}, "banana bread": {}, "caribbean fruit/ rum": {}, 
    "butter pecan": {}, "white chocolate sponge": {}, "pineapple sponge": {},
}

# Defines which sizes are available for a given number of layers.
# Sizes are now simplified to just the inch number or the sheet type.
LAYER_SIZE_CONSTRAINTS = {
    1: ['6', '8', '9', '10', '12', 'quarter sheet', 'half sheet'],
    2: ['6', '8', '9', '10', '12', 'quarter sheet', 'half sheet'],
    3: ['6', '8'],
}
VALID_LAYERS = list(LAYER_SIZE_CONSTRAINTS.keys())

# Lists derived from config for simpler validation checks
VALID_FLAVORS = list(CAKE_CONFIG.keys()) 
VALID_YES_NO = ['yes', 'y', 'no', 'n']

# --- FLOW AND STATE MAPS ---

FLOW_MAP = {
    'START': {
        # CHANGE 1: New Welcome Message & Restart Info
        'question': 'Welcome to the Cake Bot! I can help you place a custom cake order. We will walk through the required details step-by-step.\n\nType **Restart** at any time to begin the conversation over.\n\nWhat is the date of the event? (Please reply with DD/MM/YYYY)',
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
            'yes': 'ASK_FLAVOR',
            'no': 'ASK_FLAVOR',
        },
    },
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
        # Simplified size input: only expects number (6, 8, etc.) or sheet type (quarter sheet, half sheet)
        'question': 'What size cake? Please enter the size in inches (e.g., **8** or **10**), or type **quarter sheet** or **half sheet**.',
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
        'next': 'ASK_CONFIRMATION', # CHANGE 2: New step before SUMMARY
    },
    'ASK_CONFIRMATION': {
        'question': 'Please review the summary above. Is this information correct and ready to save? (Yes/No)',
        'data_key': None,
        'next_if': {
            'yes': 'SUMMARY',
            'no': 'START', # If No, start over
        },
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
        # ... (date validation logic remains the same) ...
        try:
            event_date = datetime.strptime(incoming_message, '%d/%m/%Y')
            if event_date < datetime.now() - timedelta(hours=24): 
                return False, "That date is in the past! Please provide a future date (DD/MM/YYYY)."
            return True, None
        except ValueError:
            return False, "I couldn't understand that date format. Please reply with **DD/MM/YYYY** (e.g., 25/12/2026)."

    # --- Binary Validation (Yes/No) ---
    if current_step in ['ASK_CUSTOM_PICTURE', 'ASK_INDOORS', 'ASK_AC', 'ASK_CONFIRMATION']:
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

    # --- Combined Validation: SIZE (Simplified Input) ---
    if current_step == 'ASK_SIZE':
        user_data = user_states.get(user_id, {}).get('data', {})
        try:
            chosen_layers = int(user_data.get('num_layers'))
        except (ValueError, TypeError):
            return False, "Error: Please tell me the number of layers before choosing a size."

        valid_sizes_for_layers = LAYER_SIZE_CONSTRAINTS.get(chosen_layers, [])
        
        # Check if the user's input (number or sheet type) is valid
        if message in valid_sizes_for_layers:
            return True, None
        
        # Provide a helpful error showing valid options based on layers
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

    return True, None

# --- STATE MANAGEMENT CORE ---

def _generate_summary_response(user_id):
    """Generates a final summary message and returns the text for review."""
    final_data = user_states[user_id]['data']
    
    # --- Generate Human-Friendly Summary ---
    summary_lines = ["\n🎂 **Order Summary** 🎂\n"]
    
    for data_key, display_name in DISPLAY_KEY_MAP.items():
        value = final_data.get(data_key)
        
        if value is not None:
            summary_lines.append(f"*{display_name}:* {value}")
            
    final_message = "\n".join(summary_lines)
    
    # Do NOT clear state yet, as we need confirmation!
    return final_message

def _final_save_and_end(user_id):
    """Saves the data and generates the final closing message."""
    final_data = user_states[user_id]['data']
    final_data['user_id'] = user_id 

    # FINAL SAVE: Call the Google Sheets function
    save_order_data(final_data) 
    
    # Generate final closing message
    closing_message = "\n✅ Thank you! Your confirmed order details have been saved, and we will contact you shortly with a quote."
    
    # Clear state for next conversation
    user_states[user_id] = {'step': 'COMPLETE', 'data': final_data}
    
    return closing_message

def _get_next_step(user_id, incoming_message):
    """Determines the next step based on the current step and the user's input."""
    state = user_states.get(user_id, {'step': 'START', 'data': {}})
    current_step = state['step']
    
    # CHANGE 1: Implement 'restart' keyword
    if incoming_message.lower().strip() == 'restart':
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
    
    # Check for conditional branching (ASK_CUSTOM_PICTURE and ASK_CONFIRMATION)
    if 'next_if' in FLOW_MAP[current_step]:
        branch = FLOW_MAP[current_step]['next_if']
        key = incoming_message.lower().strip()
        
        if key in ['y', 'yes']:
            key = 'yes'
        elif key in ['n', 'no']:
            key = 'no'

        next_step = branch.get(key, next_step) 
        
        # Special case: If confirmation fails, handle the restart message
        if next_step == 'START' and current_step == 'ASK_CONFIRMATION':
            user_states[user_id] = {'step': 'START', 'data': {}}
            return 'START', "Order canceled. Starting over:\n" + FLOW_MAP['START']['question']


    # Check if we need to generate a summary for the user to review
    if next_step == 'ASK_CONFIRMATION':
        # Generate summary first, then ask confirmation question
        summary_text = _generate_summary_response(user_id)
        
        user_states[user_id]['step'] = 'ASK_CONFIRMATION'
        return 'ASK_CONFIRMATION', summary_text + "\n" + FLOW_MAP['ASK_CONFIRMATION']['question']
    
    # Check if the final save needs to happen
    if next_step == 'SUMMARY':
        # This is the point of no return: save and generate the closing message
        return 'SUMMARY', _final_save_and_end(user_id)
    
    if next_step:
        user_states[user_id]['step'] = next_step
        return next_step, FLOW_MAP[next_step]['question']

    return 'COMPLETE', "I'm sorry, I've lost my place. Please type 'restart' to begin over."


def get_response(user_id, incoming_message):
    """The main entry point for the handler."""
    next_step, response_text = _get_next_step(user_id, incoming_message)
    return response_text