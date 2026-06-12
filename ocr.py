import os
import logging
from PIL import Image
import pytesseract
import requests
from io import BytesIO

logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self):
        self.temp_dir = "temp_ocr"
        os.makedirs(self.temp_dir, exist_ok=True)
    
    async def extract_from_photo(self, photo_file):
        try:
            temp_path = os.path.join(self.temp_dir, f"ocr_{os.urandom(4).hex()}.jpg")
            await photo_file.download_to_drive(temp_path)
            img = Image.open(temp_path)
            text = pytesseract.image_to_string(img, lang='ara+eng')
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return text.strip() if text.strip() else None
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return None
    
    async def extract_from_url(self, url):
        try:
            response = requests.get(url, timeout=10)
            img = Image.open(BytesIO(response.content))
            text = pytesseract.image_to_string(img, lang='ara+eng')
            return text.strip() if text.strip() else None
        except Exception as e:
            logger.error(f"OCR URL error: {e}")
            return None
