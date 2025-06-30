# app/main.py

import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Security, Form
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from datetime import datetime

# NOTE: We are no longer importing Redis, RQ, or the worker function
from .models import Receipt
from .services.ocr_llm import OCRService
from .services.sheets import SheetsService
from .services.storage_service import StorageService
from google.cloud import tasks_v2
import json

# --- Configuration ---
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_QUEUE_LOCATION = os.getenv("GCP_QUEUE_LOCATION")
GCP_QUEUE_NAME = os.getenv("GCP_QUEUE_NAME")
WORKER_URL = os.getenv("WORKER_URL") # e.g., https://your-worker-service.onrender.com/process-receipt

# --- Security ---
api_key_header = APIKeyHeader(name="X-API-Key")
def get_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key

# --- Service Initialization ---
# We now need to initialize all three services again, just like before
ocr_service = OCRService(api_key=GEMINI_API_KEY)
sheets_service = SheetsService(credentials_json_string=GOOGLE_SHEETS_CREDENTIALS_JSON)
storage_service = StorageService(credentials_json_string=GOOGLE_SHEETS_CREDENTIALS_JSON, bucket_name=GCS_BUCKET_NAME)
tasks_client = tasks_v2.CloudTasksClient()

# --- FastAPI Application ---
app = FastAPI(title="Receipt Scanner API")

# We go back to using the original UploadResponse model
class UploadResponse(BaseModel):
    message: str
    task_name: str

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Welcome to the Receipt Scanner API!"}

@app.post("/upload", response_model=UploadResponse)
async def upload_receipt(
    image: UploadFile = File(...),
    voice_note: str = Form(None),
    api_key: str = Depends(get_api_key)
):
    """
    This endpoint uploads the file to GCS and then creates a Google Cloud Task
    for asynchronous processing.
    """
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{image.filename}")

    try:
        # 1. Save file locally
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        
        # 2. Upload to GCS
        blob_name = f"receipts/{datetime.now().year}/{os.path.basename(temp_file_path)}"
        image_url = storage_service.upload_file(
            source_file_path=temp_file_path,
            destination_blob_name=blob_name
        )
        if not image_url:
            raise HTTPException(status_code=500, detail="Failed to upload image to Cloud Storage.")

        # 3. Create a task in Google Cloud Tasks
        task_payload = {"image_url": image_url, "voice_note": voice_note}
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": WORKER_URL,
                "headers": {"Content-type": "application/json"},
                "body": json.dumps(task_payload).encode(),
            }
        }
        parent = tasks_client.queue_path(GCP_PROJECT_ID, GCP_QUEUE_LOCATION, GCP_QUEUE_NAME)
        created_task = tasks_client.create_task(parent=parent, task=task)

        # 4. Return the task name
        return UploadResponse(
            message="Receipt processing task created successfully.",
            task_name=created_task.name
        )
    except Exception as e:
        # Any error in the process will be caught here and logged by Render
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        # 5. Clean up the temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)