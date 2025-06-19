# app/services/storage_service.py

import json
from google.cloud import storage
from datetime import datetime

class StorageService:
    def __init__(self, credentials_json_string: str, bucket_name: str):
        """
        Initializes the Storage Service client by explicitly loading
        credentials from the provided JSON string.
        """
        try:
            creds_dict = json.loads(credentials_json_string)
            self.client = storage.Client.from_service_account_info(creds_dict)
            self.bucket_name = bucket_name
            self.bucket = self.client.get_bucket(self.bucket_name)
            print(f"Successfully connected to GCS bucket: {self.bucket_name}")
        except Exception as e:
            print(f"Failed to connect to GCS: {e}")
            raise

    def upload_file(self, source_file_path: str, destination_blob_name: str) -> str:
        # This method remains unchanged
        try:
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_filename(source_file_path)
            blob.make_public()
            return blob.public_url
        except Exception as e:
            print(f"An error occurred during file upload to GCS: {e}")
            raise