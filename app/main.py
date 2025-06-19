# app/main.py

import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Security, Form
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from datetime import datetime
from redis import Redis
from rq import Queue

# --- IMPORTANT: We now import the job function from our worker file ---
from worker import process_receipt_job

# --- Configuration & Security (remains the same) ---
from dotenv import load_dotenv
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
REDIS_URL = os.getenv("REDIS_URL")

api_key_header = APIKeyHeader(name="X-API-Key")
def get_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key

# --- Service Initialization ---
# The main app ONLY needs the Storage Service for the initial upload.
# The OCR and Sheets services are now only used by the worker.
from .services.storage_service import StorageService
storage_service = StorageService(bucket_name=GCS_BUCKET_NAME)

# --- Redis Queue Connection ---
print("Web App: Connecting to Redis...")
redis_conn = Redis.from_url(REDIS_URL)
q = Queue(name="default", connection=redis_conn)
print("Web App: Redis connection successful.")

# --- FastAPI Application ---
app = FastAPI(title="Receipt Scanner API")

# A new, simpler response model for when we enqueue a job
class EnqueueResponse(BaseModel):
    message: str
    job_id: str

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Welcome to the Receipt Scanner API!"}

@app.post("/upload", response_model=EnqueueResponse)
async def upload_receipt(
    image: UploadFile = File(...),
    voice_note: str = Form(None),
    api_key: str = Depends(get_api_key)
):
    """
    This endpoint is now a fast "cashier". It uploads the image to GCS,
    then creates a background job for processing and returns immediately.
    """
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{image.filename}")

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # 1. Upload to GCS
        blob_name = f"receipts/{datetime.now().year}/{os.path.basename(temp_file_path)}"
        image_url = storage_service.upload_file(
            source_file_path=temp_file_path,
            destination_blob_name=blob_name
        )
        if not image_url:
            raise HTTPException(status_code=500, detail="Failed to upload image to Cloud Storage.")

        # 2. Enqueue the job for the worker
        print(f"Enqueuing job for image: {image_url}")
        job = q.enqueue(
            process_receipt_job,  # The function to run
            image_url,            # The first argument to the function
            voice_note            # The second argument
        )
        print(f"Job enqueued with ID: {job.get_id()}")

        # 3. Return an immediate response
        return EnqueueResponse(
            message="Receipt accepted for processing.",
            job_id=job.get_id()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)