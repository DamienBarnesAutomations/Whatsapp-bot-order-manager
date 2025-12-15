import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import logging

# Set up logging for better visibility in Render logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
GRAPH_API_URL = os.environ.get("GRAPH_API_URL")

app = Flask(__name__)

# --- Core Reply Function ---

def send_whatsapp_message(to_number, message_body):
    """Sends a simple text message back to the user."""
    
    if not PHONE_NUMBER_ID:
        logger.error("Error: PHONE_NUMBER_ID is not set.")
        return False
        
    url = f"{GRAPH_API_URL}/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "body": message_body
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        logger.info("Message sent successfully: %s", response.json())
        return True
    except requests.exceptions.RequestException as e:
        error_details = response.text if 'response' in locals() else "No response body."
        logger.error("Request Error: %s. Details: %s", e, error_details)
        return False


# --- Webhook Routes ---

@app.route("/", methods=["GET"])
def hello_world():
    """Simple health check route."""
    return "WhatsApp Bot is running!"

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """
    Meta Webhook Verification (GET request).
    Called by Meta when you set up the webhook URL.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            logger.warning("Verification token mismatch.")
            return jsonify({"status": "error", "message": "Verification token mismatch"}), 403
    
    logger.warning("Missing required webhook parameters.")
    return jsonify({"status": "error", "message": "Missing required parameters"}), 400

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """
    Handle incoming WhatsApp messages (POST request).
    This is the main message processing endpoint.
    """
    data = request.get_json()
    
    # Optional: Log the incoming payload for debugging
    # logger.debug("Incoming Webhook Data: %s", data) 

    try:
        # Check if the payload contains a message
        value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value")
        messages = value.get("messages", [])
        
        if messages:
            
            # Extract relevant information
            message_data = messages[0]
            from_number = message_data["from"] # The user's WhatsApp ID
            message_type = message_data.get("type")
            
            # Simple text message handling
            if message_type == "text":
                text_body = message_data["text"]["body"]
                logger.info("Received message from %s: %s", from_number, text_body)

                # --- The simple reply logic for Step 1 ---
                reply_message = f"Hello! You said: '{text_body}'. I'm your appointment bot. Let's start the process!"
                send_whatsapp_message(from_number, reply_message)
                
            # Handle other message types (e.g., location, image) by ignoring them for now
            else:
                logger.info("Received non-text message of type: %s. Ignoring.", message_type)
            
            # Acknowledge receipt to Meta's API
            return jsonify({"status": "ok"}), 200

        # Acknowledge status notifications (delivered, read)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        # Catch any parsing errors and still return 200 to Meta to avoid re-sends.
        logger.error("Error processing webhook: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 200 
