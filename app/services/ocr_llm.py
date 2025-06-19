# app/services/ocr_llm.py

import os
import google.generativeai as genai
import cv2 # This is the OpenCV library
from PIL import Image
from datetime import datetime
from ..models import Receipt # Import our Pydantic model

class OCRService:
    def __init__(self, api_key: str):
        """
        Initializes the OCR Service with the Gemini API key.
        """
        self.api_key = api_key
        genai.configure(api_key=self.api_key)
        # We use the Gemini 1.5 Flash model for speed and cost-effectiveness
        self.model = genai.GenerativeModel('gemini-1.5-flash-latest')

    def _preprocess_image(self, image_path: str) -> str:
        """
        Cleans up the image for better OCR accuracy.
        This incorporates the excellent suggestion from the Claude feedback.
        """
        try:
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            
            # Apply adaptive thresholding to get a clean black and white image
            processed_img = cv2.adaptiveThreshold(
                img, 255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Save the cleaned-up image temporarily
            processed_path = image_path.replace('.jpg', '_processed.jpg')
            cv2.imwrite(processed_path, processed_img)
            return processed_path
        except Exception as e:
            print(f"Error during image preprocessing: {e}")
            # If preprocessing fails, we can still try with the original image
            return image_path

    def parse_image(self, image_path: str) -> Receipt:
        """
        Takes the path to an image, preprocesses it, and sends it to Gemini
        with a detailed prompt to extract receipt information.
        """
        print("Preprocessing image...")
        processed_image_path = self._preprocess_image(image_path)
        
        print("Image preprocessed. Preparing to call Gemini...")
        
        # This detailed prompt is inspired by the Claude feedback to ensure
        # we get a structured JSON response.
        prompt = """
        You are an expert receipt parser. Analyze this receipt image and extract its data.
        Your response MUST be a valid JSON object that conforms to the following Pydantic model:

        class LineItem(BaseModel):
            description: str
            quantity: float
            unit_price: float
            total: float

        class Receipt(BaseModel):
            vendor_name: str
            total: float
            date: datetime
            vendor_address: Optional[str] = None
            receipt_number: Optional[str] = None
            subtotal: Optional[float] = None
            tax: Optional[float] = None
            payment_method: Optional[str] = None
            items: List[LineItem] = []

        Extract all fields precisely. The 'date' should be in 'YYYY-MM-DDTHH:MM:SS' format.
        If a field is not visible or applicable, omit it or use null.
        """

        try:
            image_file = Image.open(processed_image_path)
            
            print("Sending request to Gemini...")
            response = self.model.generate_content([prompt, image_file])
            
            # The response from Gemini is often wrapped in markdown (```json ... ```)
            # We need to clean this up before parsing.
            clean_json_response = response.text.strip().replace('```json', '').replace('```', '')
            
            print("Received response from Gemini. Parsing into data model...")
            # Pydantic will automatically parse the JSON and validate it against our model.
            # If the data is invalid or missing required fields, it will raise an error.
            receipt_data = Receipt.model_validate_json(clean_json_response)
            
            return receipt_data

        except Exception as e:
            print(f"An error occurred while parsing with Gemini: {e}")
            # In a real app, we would raise a custom exception here.
            return None
        finally:
            # Clean up the processed image file if it was created
            if processed_image_path != image_path:
                os.remove(processed_image_path)