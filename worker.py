# worker.py

import os
import requests
import shutil
import uuid
from redis import Redis
from rq import Queue, Connection, SimpleWorker
from dotenv import load_dotenv

from app.services.ocr_llm import OCRService
from app.services.sheets import SheetsService
from app.models import Receipt

# --- Configuration & Service Initialization ---
load_dotenv()
print("Worker: Loading configuration and initializing services...")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
REDIS_URL = os.getenv("REDIS_URL")

ocr_service = OCRService(api_key=GEMINI_API_KEY)
sheets_service = SheetsService(credentials_json_string=GOOGLE_SHEETS_CREDENTIALS_JSON)
print("Worker: Services initialized.")

# --- The Actual Job Function ---
def process_receipt_job(image_url: str, voice_note: str | None):
    """
    The background job that does the heavy lifting.
    1. Downloads the image from GCS.
    2. Calls Gemini to parse it.
    3. Saves the data to Google Sheets.
    """
    temp_dir = "temp_worker_files"
    os.makedirs(temp_dir, exist_ok=True)
    # Give the temp file a unique name
    local_filename = os.path.join(temp_dir, f"{uuid.uuid4()}.jpg")

    try:
        print(f"WORKER: Starting job for image URL: {image_url}")
        
        # 1. Download the image from Google Cloud Storage
        print(f"WORKER: Downloading image from {image_url}...")
        with requests.get(image_url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
        print(f"WORKER: Image downloaded to {local_filename}")

        # 2. Call the OCR service with the local file path
        receipt_data = ocr_service.parse_image(local_filename)
        if not receipt_data:
            raise Exception("Failed to parse receipt data from image.")

        # 3. Add the supplementary data
        receipt_data.image_url = image_url
        if voice_note:
            receipt_data.voice_note = voice_note

        # 4. Call the Sheets service to save everything
        sheets_service.append_receipt(receipt=receipt_data, sheet_url=GOOGLE_SHEET_URL)
        
        print(f"WORKER: Successfully processed and saved receipt for job.")

    except Exception as e:
        print(f"WORKER: Job failed for image {image_url}: {e}")
    finally:
        # 5. Clean up the downloaded file
        if os.path.exists(local_filename):
            os.remove(local_filename)

# This part is for running the worker directly if needed, Render uses the `rq worker` command.
if __name__ == '__main__':
    listen = ['default']
    redis_conn = Redis.from_url(REDIS_URL)
    with Connection(redis_conn):
        worker = SimpleWorker(queues=listen)
        worker.work()