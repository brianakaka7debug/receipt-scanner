# app/services/storage_service.py

from google.cloud import storage
from datetime import datetime

class StorageService:
    def __init__(self, bucket_name: str):
        """
        Initializes the Storage Service client using Application Default Credentials.
        """
        try:
            self.client = storage.Client()
            self.bucket_name = bucket_name
            self.bucket = self.client.get_bucket(bucket_name)
            print(f"Successfully connected to GCS bucket: {bucket_name}")
        except Exception as e:
            print(f"Failed to connect to GCS: {e}")
            raise

    def upload_file(self, source_file_path: str, destination_blob_name: str) -> str:
        try:
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_filename(source_file_path)
            blob.make_public()
            return blob.public_url
        except Exception as e:
            print(f"An error occurred during file upload to GCS: {e}")
            raise