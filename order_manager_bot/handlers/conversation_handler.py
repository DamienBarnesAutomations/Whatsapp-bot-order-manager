# conversation_handler.py

import logging
# Import necessary data from the config file
from config.cake_config import FLOW_MAP, DISPLAY_KEY_MAP, LAYER_SIZE_CONSTRAINTS

# Import the validation function
from validation.validator import validate_input

# Import the Google Services (Sheets) functions
from services.google_services import save_order_data 

logging.basicConfig(level=logging.INFO)

# --- STATE STORAGE ---
# Global dictionary to hold user state: {phone_number: {'step': 'STEP_NAME', 'data': {...}}}
user_states = {}

# --- CORE FUNCTIONS ---

def _generate_summary_response(user_id):
    """Generates a final summary message and returns the text for review."""
    final_data = user_states[user_id]['data']
    
    summary_lines = ["\n🎂 **Order Summary** 🎂\n"]
    
    for data_key, display_name in DISPLAY_KEY_MAP.items():
        value = final_data.get(data_key)
        
        if value is not None:
            summary_lines.append(f" *{display_name}:* {value}")
            
    final_message = "\n".join(summary_lines)
    
    return final_message

def _final_save_and_end(user_id):
    """Saves the data and generates the final closing message."""
    final_data = user_states[user_id]['data']
    final_data['user_id'] = user_id 

    # FINAL SAVE: Call the Google Sheets function
    save_order_data(final_data) 
    
    closing_message = "\n✅ Thank you! Your confirmed order details have been saved, and we will contact you shortly with a quote."
    
    # Clear state for next conversation
    user_states[user_id] = {'step': 'COMPLETE', 'data': final_data}
    
    return closing_message

def _get_next_step(user_id, incoming_message):
    """Determines the next step based on the current step and the user's input."""
    state = user_states.get(user_id, {'step': 'START', 'data': {}})
    current_step = state['step']
    
    # Implement 'restart' keyword
    if incoming_message.lower().strip() == 'restart':
        user_states[user_id] = {'step': 'START', 'data': {}}
        return 'START', FLOW_MAP['START']['question'] + "\n" + FLOW_MAP['ASK_DATE']['question']


    if current_step == 'START':
        user_states[user_id] = {'step': 'ASK_DATE', 'data': {}}
        return 'ASK_DATE', FLOW_MAP['START']['question'] + "\n" + FLOW_MAP['ASK_DATE']['question']
        
    # --- VALIDATION CHECK (Now calls the external function) ---
    # NOTE: user_states must be passed to the validator
    is_valid, feedback = validate_input(user_id, current_step, incoming_message, user_states)

    if not is_valid:
        return current_step, f"🛑 **Validation Error:** {feedback} Please try again: {FLOW_MAP[current_step]['question']}"

    # --- 1. Collect and store data (ONLY if input is valid) ---
    data_key = FLOW_MAP.get(current_step, {}).get('data_key')
    if data_key:
        user_states[user_id]['data'][data_key] = incoming_message

    # --- 2. Determine the NEXT step ---
    next_step = FLOW_MAP[current_step].get('next')
    
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


    # --- Dynamic Question Generation ---

    # Dynamic Question for ASK_SIZE
    if next_step == 'ASK_SIZE':
        # Safely fetch the chosen layer count
        try:
            chosen_layers = int(user_states[user_id]['data'].get('num_layers'))
        except (ValueError, TypeError):
            return next_step, "Error: Could not determine layers. Please try typing 'Restart'."

        # Get the valid size options for those layers
        size_options = LAYER_SIZE_CONSTRAINTS.get(chosen_layers, [])
        options_text = ", ".join(size_options).replace('quarter sheet', '**quarter sheet**').replace('half sheet', '**half sheet**')

        dynamic_question = (
            f"You selected **{chosen_layers} layers**. "
            f"What size cake would you like? For {chosen_layers} layers, we offer: \n"
            f"👉 {options_text}.\n\nPlease reply with one of the options (e.g., 10 or quarter sheet)."
        )
        
        user_states[user_id]['step'] = next_step
        return next_step, dynamic_question


    # Confirmation Step: Generate summary and ask for confirmation
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


def get_response(user_id, incoming_message):
    """The main entry point for the handler."""
    next_step, response_text = _get_next_step(user_id, incoming_message)
    return response_text