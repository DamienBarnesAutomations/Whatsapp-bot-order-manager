import os
import logging
from handlers.whatsapp_handler import process_whatsapp_message

# Set up basic logging
logging.basicConfig(level=logging.INFO)

# --- Webhook Verification Logic ---
def verify_webhook(args):
    """Verifies the webhook subscription with Meta."""
    VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
    
    mode = args.get('hub.mode')
    token = args.get('hub.verify_token')
    challenge = args.get('hub.challenge')
    
    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logging.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            return "Verification failed", 403
    return "Verification required", 400

# --- Incoming Message Routing ---
def handle_message(data):
    """Parses incoming JSON data and routes to the correct platform handler."""
    try:
        if data.get("entry") and data["entry"][0].get("changes"):
            change = data["entry"][0]["changes"][0]
            
            if change["field"] == "messages" and change.get("value"):
                # Pass the WhatsApp payload to the specific handler
                process_whatsapp_message(change["value"])
            
    except Exception as e:
        logging.error(f"Error handling message payload: {e}")