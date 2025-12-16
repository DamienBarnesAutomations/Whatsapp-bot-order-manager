import os
import logging
import requests
import json # Import json for cleaner logging of API responses
from handlers.conversation_handler import get_response

# Configuration
GRAPH_API_URL = "https://graph.facebook.com/v19.0"
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
# Note: Ensure you have your centralized logging configuration set up 
# elsewhere (e.g., app.py) as discussed previously.

# --- Utility Function: Fetch Media Details from WhatsApp ---

def get_media_url_and_mime(media_id):
    """
    Fetches the temporary media URL and MIME type from the WhatsApp Cloud API.
    
    :param media_id: The ID of the media file provided in the incoming webhook.
    :return: A dictionary with 'url' and 'mime_type', or None on failure.
    """
    if not WHATSAPP_TOKEN:
        logging.error("Missing WhatsApp token for media request.")
        return None

    url = f"{GRAPH_API_URL}/{media_id}"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        media_info = response.json()
        
        # WhatsApp returns a temporary 'url' and 'mime_type' here
        return {
            "url": media_info.get("url"),
            "mime_type": media_info.get("mime_type"),
        }
    except requests.exceptions.HTTPError as err:
        logging.error(f"Media fetch API Error (Status: {response.status_code}): {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during media URL fetch: {e}")
        
    return None


# --- Core Function: Sending Messages ---

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
        response.raise_for_status()
        # Logging success is useful for tracking outgoing messages
        logging.info(f"Message sent successfully to {to_number}. Response: {response.status_code}")
    except requests.exceptions.HTTPError as err:
        logging.error(f"Request Error: {err}. Details: {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Network or request setup error: {e}")


# --- Core Function: Processing Incoming Webhook ---

def process_whatsapp_message(value):
    """
    Extracts message data (text or media) and routes it to the conversation handler.
    
    :param value: The 'value' dictionary from the WhatsApp webhook payload.
    """
    
    if "messages" not in value:
        logging.warning("Webhook value does not contain 'messages'. Ignoring.")
        return
        
    message_data = value["messages"][0]
    sender_phone = message_data.get("from")
    message_type = message_data.get("type")
    
    if not sender_phone:
        logging.error("Could not determine sender phone number.")
        return

    incoming_text = ""
    media_context = None
    
    # 1. Handle Text Messages
    if message_type == "text":
        incoming_text = message_data["text"]["body"]
        logging.info(f"Received TEXT from {sender_phone}: {incoming_text}")
        
    # 2. Handle Image Messages (or media generally)
    elif message_type == "image":
        # Extract the caption as the incoming_text (if present)
        incoming_text = message_data.get("caption", "").strip()
        media_id = message_data["image"]["id"]
        
        logging.info(f"Received IMAGE from {sender_phone}. Media ID: {media_id}")

        # Fetch the temporary URL and MIME type using the WhatsApp Media API
        media_context = get_media_url_and_mime(media_id)
        
        if not media_context or not media_context.get('url'):
            logging.error(f"Failed to retrieve media URL for ID {media_id}. Cannot proceed with upload.")
            send_whatsapp_message(sender_phone, 
                                  "⚠️ I received your message but couldn't get the image link from WhatsApp. Please try sending the image again.")
            return

        logging.info(f"Retrieved media URL for upload: {media_context['url']}")

    # 3. Handle Unsupported Types
    else:
        logging.info(f"Received unsupported message type ({message_type}) from {sender_phone}.")
        send_whatsapp_message(sender_phone, 
                              "I currently only process text messages and single image files for your custom order. Please reply with text or an image.")
        return
        
    # 4. Get the reply from the conversation logic (passing media context if available)
    # The conversation handler checks the current state and decides what to do with the media/text.
    reply_text = get_response(
        user_id=sender_phone, 
        incoming_message=incoming_text, 
        media_context=media_context # Pass None for text, or the dict for media
    )
    
    # 5. Send the final reply back
    if reply_text:
        send_whatsapp_message(sender_phone, reply_text)