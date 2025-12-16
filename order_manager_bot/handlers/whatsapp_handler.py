import os
import logging
import requests
from handlers.conversation_handler import get_response

# Configuration
GRAPH_API_URL = "https://graph.facebook.com/v19.0"
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")

def send_whatsapp_message(to_number, text_message):
    """Sends a text message using the WhatsApp Cloud API."""
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        logging.error("Missing WhatsApp token or phone number ID.")
        return

    url = f"{GRAPH_API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text_message},
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
        logging.info(f"Message sent successfully to {to_number}.")
    except requests.exceptions.HTTPError as err:
        logging.error(f"Request Error: {err} for url: {url}. Details: {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Network or request setup error: {e}")


def process_whatsapp_message(value):
    """Extracts message data and routes it to the conversation handler."""
    
    # 1. Identify the sender's phone number
    if "messages" in value:
        message_data = value["messages"][0]
        sender_phone = message_data.get("from")
        
        # 2. Extract the incoming text
        if message_data.get("type") == "text":
            incoming_text = message_data["text"]["body"]
            
            logging.info(f"Received message from {sender_phone}: {incoming_text}")
            
            # 3. Get the reply from the conversation logic
            reply_text = get_response(sender_phone, incoming_text)
            
            # 4. Send the reply back
            if reply_text:
                send_whatsapp_message(sender_phone, reply_text)
        
        else:
            # Handle other message types like media, locations, etc.
            send_whatsapp_message(sender_phone, "I currently only process text messages. Please type your request.")