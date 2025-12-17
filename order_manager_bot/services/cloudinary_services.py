# services/cloudy_services.py

import os
import logging
import io
# Import the Cloudinary library (You will need to install this: pip install cloudinary)
import cloudinary
import cloudinary.uploader
import cloudinary.api 

# --- CONFIGURATION ---
# Load credentials from environment variables (recommended practice)
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")
CLOUDINARY_FOLDER = os.environ.get("CLOUDINARY_FOLDER")

# Folder in Cloudinary where images will be stored


# Initialize Cloudinary configuration once
if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )
    logging.info("Cloudinary configuration loaded successfully.")
else:
    logging.error("Cloudinary credentials are NOT set. Image uploads will fail.")

# --- CORE UPLOAD FUNCTION ---

def upload_image_to_cloudinary(image_data, public_id):
    """
    Uploads image data (binary content) to Cloudinary.
    
    :param image_data: The binary content of the image (from requests.content).
    :param public_id: A unique name for the file (e.g., user_id_timestamp).
    :return: The secure URL of the uploaded image, or None on failure.
    """
    try:
        # Use io.BytesIO to treat the binary data as a file-like object
        file_obj = io.BytesIO(image_data)
        
        # Upload the file
        upload_result = cloudinary.uploader.upload(
            file_obj,
            folder=CLOUDINARY_FOLDER,
            public_id=public_id,
            resource_type="auto"
        )
        
        # Cloudinary returns the permanent secure URL upon success
        secure_url = upload_result.get('secure_url')
        
        if secure_url:
            logging.info(f"Image uploaded to Cloudinary. URL: {secure_url}")
            return secure_url
        else:
            logging.error(f"Cloudinary upload failed: Missing secure_url in response. Result: {upload_result}")
            return None

    except cloudinary.exceptions.Error as e:
        logging.error(f"Cloudinary API Error during upload: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during Cloudinary upload: {e}")
        return None