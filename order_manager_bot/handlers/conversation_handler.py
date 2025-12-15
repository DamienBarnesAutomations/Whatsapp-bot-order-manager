# The Core Logic lives here
# We will use this file to manage user state (what stage of the order they are in)

# A simple dictionary to demonstrate state management (will be replaced by Google Sheets/n8n)
user_states = {}

def get_conversation_response(user_id, incoming_message):
    """
    Manages the conversation flow and generates the appropriate response.
    
    :param user_id: The unique identifier for the user (the phone number).
    :param incoming_message: The text received from the user.
    :return: The generated reply text.
    """
    
    # --- STEP 1: Placeholder Logic (Echo) ---
    # We will replace this with structured flow logic later.
    
    # Normalize input
    message = incoming_message.strip().lower()

    if message == "hello":
        return "Hello! I am your Order Manager Bot. How can I help you today?"
    
    # Default echo response
    return f"I received your message: '{incoming_message}'. I am now moving into conversation flow management!"