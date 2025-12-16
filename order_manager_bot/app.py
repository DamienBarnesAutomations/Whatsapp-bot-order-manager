import os
from flask import Flask, request, jsonify
from handlers.message_handler import handle_message, verify_webhook
import logging
from services.google_services import initialize_google_apis

# --- Configuration ---
# Your Flask app instance is still named 'app'
app = Flask(__name__) 

logging.getLogger().setLevel(logging.INFO)

# --- Routes ---
initialize_google_apis()

# 1. Webhook Verification (GET)
@app.route('/webhook', methods=['GET'])
def webhook_get():
    return verify_webhook(request.args)

# 2. Incoming Messages (POST)
@app.route('/webhook', methods=['POST'])
def webhook_post():
    data = request.get_json()
    if data and 'object' in data and data['object'] == 'whatsapp_business_account':
        handle_message(data)
    
    # Always return a 200 OK to Meta quickly to avoid retries
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    # Gunicorn handles this in production, but needed for local testing
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080))