# app/services/sheets.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime
from ..models import Receipt

class SheetsService:
    def __init__(self, credentials_json_string: str):
        """
        Authenticates with the Google Sheets API using credentials
        passed directly as a JSON string.
        """
        try:
            creds_dict = json.loads(credentials_json_string)
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self.client = gspread.authorize(creds)
            print("Successfully authenticated with Google Sheets.")
        except Exception as e:
            print(f"Failed to authenticate with Google Sheets: {e}")
            raise

    def _categorize_vendor(self, vendor_name: str) -> str:
        """
        A simple but powerful auto-categorization function based on keywords.
        This was a great suggestion from the Claude feedback.
        """
        # This can be expanded with more categories and keywords
        categories = {
            'Groceries': ['walmart', 'kroger', 'whole foods', 'safeway', 'costco'],
            'Restaurants': ['mcdonalds', 'starbucks', 'subway', 'taco bell', 'chipotle'],
            'Gas/Fuel': ['shell', 'exxon', 'chevron', 'bp', '76'],
            'Shopping': ['amazon', 'target', 'best buy', 'home depot'],
        }
        
        vendor_lower = vendor_name.lower()
        for category, keywords in categories.items():
            if any(keyword in vendor_lower for keyword in keywords):
                return category
        return 'Other'

    def append_receipt(self, receipt: Receipt, sheet_url: str):
        """
        Appends a new row to the specified Google Sheet with the receipt data.
        """
        try:
            print(f"Opening Google Sheet: {sheet_url}")
            sheet = self.client.open_by_url(sheet_url).sheet1
            
            # Check if the sheet is empty and add our new, expanded headers
            if not sheet.get_all_records():
                headers = [
                    'Date', 'Vendor', 'Category', 'Total', 'Subtotal', 
                    'Tax', 'Payment Method', 'Voice Note', 'Items',
                    'Receipt #', 'Image URL', 'Timestamp'
                ]
                sheet.append_row(headers)
                print("Added header row to empty sheet.")

            # Flatten the list of line items into a single, readable string
            items_str = '; '.join([f"{item.description} ({item.quantity} @ ${item.unit_price:.2f})" for item in receipt.items if item.description and item.quantity and item.unit_price])
            
            # Safely format the date, allowing for it to be None
            date_str = receipt.date.strftime('%Y-%m-%d') if receipt.date else ''
            
            # Prepare the row data in the correct order
            row_data = [
                date_str,
                receipt.vendor_name,
                self._categorize_vendor(receipt.vendor_name),
                receipt.total,
                receipt.subtotal,
                receipt.tax,
                receipt.payment_method,
                receipt.voice_note,
                items_str,
                receipt.receipt_number,
                receipt.image_url,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            print("Appending new row to sheet...")
            sheet.append_row(row_data)
            print("Successfully appended data to Google Sheet.")
            return True

        except Exception as e:
            print(f"An error occurred while writing to Google Sheets: {e}")
            return False