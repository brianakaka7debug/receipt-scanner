# app/main.py

import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Security, Form
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from datetime import datetime

from .models import Receipt
from .services.ocr_llm import OCRService
from .services.sheets import SheetsService
from .services.storage_service import StorageService # <--- NEW import

# --- Configuration ---
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME") # <--- NEW config variable

# --- Security ---
api_key_header = APIKeyHeader(name="X-API-Key")
def get_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key

# --- Service Initialization ---
ocr_service = OCRService(api_key=GEMINI_API_KEY)
sheets_service = SheetsService()
storage_service = StorageService(bucket_name=GCS_BUCKET_NAME)

# --- FastAPI Application ---
app = FastAPI(title="Receipt Scanner API")

class UploadResponse(BaseModel):
    message: str
    receipt_data: Receipt

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Welcome to the Receipt Scanner API!"}

@app.post("/upload", response_model=UploadResponse)
async def upload_receipt(
    image: UploadFile = File(...),
    voice_note: str = Form(None),
    api_key: str = Depends(get_api_key)
):
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    # Give the temporary file a unique name to avoid conflicts
    temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{image.filename}")

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # --- NEW GCS UPLOAD LOGIC ---
        # Create a unique name for the file in the cloud
        blob_name = f"receipts/{datetime.now().year}/{os.path.basename(temp_file_path)}"
        # Upload the file and get its public URL
        image_url = storage_service.upload_file(
            source_file_path=temp_file_path,
            destination_blob_name=blob_name
        )
        if not image_url:
            raise HTTPException(status_code=500, detail="Failed to upload image to Cloud Storage.")

        # Call the OCR service to parse the local image
        receipt_data = ocr_service.parse_image(temp_file_path)
        if not receipt_data:
            raise HTTPException(status_code=500, detail="Failed to parse receipt data from image.")

        # Add the new data to our object
        receipt_data.image_url = image_url
        if voice_note:
            receipt_data.voice_note = voice_note

        # Call the Sheets service to save everything
        sheets_service.append_receipt(receipt=receipt_data, sheet_url=GOOGLE_SHEET_URL)

        return UploadResponse(
            message="Receipt processed and uploaded successfully.",
            receipt_data=receipt_data
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

    finally:
        # Clean up the temporary file from the local server
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)