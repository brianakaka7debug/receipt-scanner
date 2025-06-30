# worker.py

import os
import requests
import shutil
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

from app.services.ocr_llm import OCRService
from app.services.sheets import SheetsService
from app.services.storage_service import StorageService
from app.models import Receipt

# --- Configuration & Service Initialization ---
load_dotenv()
print("Worker: Loading configuration and initializing services...")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")

ocr_service = OCRService(api_key=GEMINI_API_KEY)
sheets_service = SheetsService(credentials_json_string=GOOGLE_SHEETS_CREDENTIALS_JSON)
storage_service = StorageService(credentials_json_string=GOOGLE_SHEETS_CREDENTIALS_JSON, bucket_name=GCS_BUCKET_NAME)
print("Worker: Services initialized.")

# --- FastAPI Application for the Worker ---
app = FastAPI(title="Receipt Processor Worker")

class TaskPayload(BaseModel):
    image_url: str
    voice_note: str | None = None

@app.post("/process-receipt")
async def process_receipt_task(payload: TaskPayload):
    """
    This endpoint is called by Google Cloud Tasks to process a receipt.
    """
    temp_dir = "temp_worker_files"
    os.makedirs(temp_dir, exist_ok=True)
    local_filename = os.path.join(temp_dir, f"{uuid.uuid4()}.jpg")

    try:
        print(f"WORKER: Starting job for image URL: {payload.image_url}")
        
        with requests.get(payload.image_url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
        
        receipt_data = ocr_service.parse_image(local_filename)
        if not receipt_data:
            raise Exception("Failed to parse receipt data from image.")

        receipt_data.image_url = payload.image_url
        if payload.voice_note:
            receipt_data.voice_note = payload.voice_note

        sheets_service.append_receipt(receipt=receipt_data, sheet_url=GOOGLE_SHEET_URL)
        print(f"WORKER: Successfully processed and saved receipt for job.")
        return {"status": "success"}

    except Exception as e:
        print(f"WORKER: Job failed for image {payload.image_url}: {e}")
        # We raise an HTTPException to signal to Cloud Tasks that the task failed
        # and should be retried.
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(local_filename):
            os.remove(local_filename)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Worker is running."}