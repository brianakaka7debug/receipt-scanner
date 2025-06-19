# app/services/sheets.py

import gspread
from datetime import datetime
from ..models import Receipt

class SheetsService:
    def __init__(self):
        """
        Authenticates with the Google Sheets API using Application Default Credentials.
        """
        try:
            # gspread will automatically find the credentials from the
            # GOOGLE_APPLICATION_CREDENTIALS environment variable we set in Render.
            self.client = gspread.service_account()
            print("Successfully authenticated with Google Sheets.")
        except Exception as e:
            print(f"Failed to authenticate with Google Sheets: {e}")
            raise

    def _categorize_vendor(self, vendor_name: str) -> str:
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
        try:
            print(f"Opening Google Sheet: {sheet_url}")
            sheet = self.client.open_by_url(sheet_url).sheet1
            
            if not sheet.get_all_records():
                headers = [
                    'Date', 'Vendor', 'Category', 'Total', 'Subtotal', 
                    'Tax', 'Payment Method', 'Voice Note', 'Items',
                    'Receipt #', 'Image URL', 'Timestamp'
                ]
                sheet.append_row(headers)
                print("Added header row to empty sheet.")

            items_str = '; '.join([f"{item.description} ({item.quantity} @ ${item.unit_price:.2f})" for item in receipt.items if item.description and item.quantity and item.unit_price])
            date_str = receipt.date.strftime('%Y-%m-%d') if receipt.date else ''
            row_data = [
                date_str, receipt.vendor_name, self._categorize_vendor(receipt.vendor_name),
                receipt.total, receipt.subtotal, receipt.tax, receipt.payment_method,
                receipt.voice_note, items_str, receipt.receipt_number,
                receipt.image_url, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            sheet.append_row(row_data)
            print("Successfully appended data to Google Sheet.")
            return True
        except Exception as e:
            print(f"An error occurred while writing to Google Sheets: {e}")
            return False