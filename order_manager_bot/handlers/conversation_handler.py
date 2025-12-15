from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)

# --- Conversation State Storage ---
# Stores the current state and collected data for each user
# Format: {user_id: {'step': 'STEP_KEY', 'data': {...}}}
user_states = {}

# --- Flow Definitions ---

# Defines the sequence of questions and the data key for the answer
FLOW_MAP = {
    'ASK_DATE': {'question': "What is the date of the event? (Please reply with DD/MM/YYYY)", 'data_key': 'event_date'},
    'ASK_CUSTOM_PICTURE': {'question': "Do you have a picture of the custom cake you would like? (Reply Yes or No)", 'data_key': 'has_picture'},
    'ASK_THEME': {'question': "Do you have a theme in mind? (e.g., Star Wars, Floral, etc.)", 'data_key': 'cake_theme'},
    'ASK_FLAVOR': {'question': "What flavor cake would you like?", 'data_key': 'cake_flavor'},
    'ASK_SIZE': {'question': "What size cake would you like?", 'data_key': 'cake_size'},
    'ASK_LAYERS': {'question': "How many layers?", 'data_key': 'num_layers'},
    'ASK_TIERS': {'question': "How many tiers?", 'data_key': 'num_tiers'},
    'ASK_COLOR': {'question': "What colour would you like it to be?", 'data_key': 'cake_color'},
    'ASK_INDOORS': {'question': "Is the venue indoors? (Reply Yes or No)", 'data_key': 'venue_indoors'},
    'ASK_AC': {'question': "Does the venue have A/C? (Reply Yes or No)", 'data_key': 'venue_ac'},
}

# --- Core Logic Functions ---

def _get_next_step(user_id, incoming_message):
    """Determines the next step based on the current step and the user's input."""
    state = user_states.get(user_id, {'step': 'START', 'data': {}})
    current_step = state['step']
    
    # Check for keywords to reset the flow
    if incoming_message.lower() in ["reset", "start over"]:
        user_states[user_id] = {'step': 'START', 'data': {}}
        return 'ASK_DATE', "Okay, let's start over! " + FLOW_MAP['ASK_DATE']['question']

    if current_step == 'START':
        # Initialize state and move to the first question
        user_states[user_id] = {'step': 'ASK_DATE', 'data': {}}
        return 'ASK_DATE', FLOW_MAP['ASK_DATE']['question']

    # --- Standard State Progression & Data Collection ---
    
    # 1. Collect and store data for the current step
    data_key = FLOW_MAP.get(current_step, {}).get('data_key')
    if data_key:
        user_states[user_id]['data'][data_key] = incoming_message

    # 2. Determine the NEXT step based on current step and conditions

    if current_step == 'ASK_DATE':
        # Custom logic: Check if the date is more than 5 days away
        try:
            event_date = datetime.strptime(incoming_message, '%d/%m/%Y')
            days_until_event = (event_date - datetime.now()).days
            
            user_states[user_id]['data']['days_until_event'] = days_until_event
            
            if days_until_event > 5:
                # Conditional flow: If >5 days, ask about custom picture
                return 'ASK_CUSTOM_PICTURE', FLOW_MAP['ASK_CUSTOM_PICTURE']['question']
            else:
                # Bypass custom cake questions, move directly to flavor
                return 'ASK_FLAVOR', "Since your event is soon, we'll skip the custom design questions for now. " + FLOW_MAP['ASK_FLAVOR']['question']
        except ValueError:
            # Handle invalid date format
            return 'ASK_DATE', "I couldn't understand that date. Please use the format DD/MM/YYYY. " + FLOW_MAP['ASK_DATE']['question']
    
    elif current_step == 'ASK_CUSTOM_PICTURE':
        # Conditional flow based on picture availability
        if incoming_message.lower() == 'no':
            return 'ASK_THEME', FLOW_MAP['ASK_THEME']['question']
        else: # Assuming 'Yes' or any other input means they have a picture/can describe it
            return 'ASK_FLAVOR', FLOW_MAP['ASK_FLAVOR']['question']

    # --- Linear Flow Progression ---
    elif current_step == 'ASK_THEME':
        return 'ASK_FLAVOR', FLOW_MAP['ASK_FLAVOR']['question']
    elif current_step == 'ASK_FLAVOR':
        return 'ASK_SIZE', FLOW_MAP['ASK_SIZE']['question']
    elif current_step == 'ASK_SIZE':
        return 'ASK_LAYERS', FLOW_MAP['ASK_LAYERS']['question']
    elif current_step == 'ASK_LAYERS':
        return 'ASK_TIERS', FLOW_MAP['ASK_TIERS']['question']
    elif current_step == 'ASK_TIERS':
        return 'ASK_COLOR', FLOW_MAP['ASK_COLOR']['question']
    elif current_step == 'ASK_COLOR':
        return 'ASK_INDOORS', FLOW_MAP['ASK_INDOORS']['question']
    elif current_step == 'ASK_INDOORS':
        return 'ASK_AC', FLOW_MAP['ASK_AC']['question']

    # --- Completion Step ---
    elif current_step == 'ASK_AC':
        # The final answer has been collected, now move to COMPLETE state
        return 'COMPLETE', _generate_summary_response(user_id)
        
    return 'ASK_DATE', "Sorry, I lost track. Let's restart. " + FLOW_MAP['ASK_DATE']['question'] # Default fallback


def _generate_summary_response(user_id):
    """Generates a final summary message and clears the state."""
    final_data = user_states[user_id]['data']
    
    # Clear state for next conversation
    user_states[user_id] = {'step': 'COMPLETE', 'data': final_data}
    
    # Format the summary message
    summary_list = "\n".join([f"- {key}: {value}" for key, value in final_data.items()])
    
    response = (
        "Thank you! I have all the details for your custom cake order. "
        "Here is the summary of your request:\n\n"
        f"{summary_list}\n\n"
        "A team member will review this and confirm the price shortly."
    )
    return response


def get_conversation_response(user_id, incoming_message):
    """
    Public function called by whatsapp_handler to manage the state and get the reply.
    """
    
    # 1. Determine the next step and the response
    new_step, reply_text = _get_next_step(user_id, incoming_message)
    
    # 2. Update the user's state
    user_states[user_id]['step'] = new_step
    
    logging.info(f"User {user_id} moved to state: {new_step}")
    
    return reply_text