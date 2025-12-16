# validation/validator.py

from datetime import datetime, timedelta
# Import the configuration data
from config.cake_config import (
    FLOW_MAP, VALID_YES_NO, VALID_FLAVORS, VALID_LAYERS, LAYER_SIZE_CONSTRAINTS
)

def validate_input(user_id, current_step, incoming_message, user_states):
    """
    Validates the user's input based on the current step's requirements and business rules.
    Returns (is_valid: bool, feedback_message: str)
    
    NOTE: user_states must be passed explicitly now to access previous answers.
    """
    message = incoming_message.strip().lower()
    
    # --- Date Validation ---
    if current_step == 'ASK_DATE':
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
        # Retrieve state data using the passed user_states dictionary
        user_data = user_states.get(user_id, {}).get('data', {})
        try:
            chosen_layers = int(user_data.get('num_layers'))
        except (ValueError, TypeError):
            return False, "Error: Please tell me the number of layers before choosing a size."

        valid_sizes_for_layers = LAYER_SIZE_CONSTRAINTS.get(chosen_layers, [])
        
        if message in valid_sizes_for_layers:
            return True, None
        
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