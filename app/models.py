# app/models.py

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None


class Receipt(BaseModel):
    # --- Core Fields from Phase 1 ---
    vendor_name: str
    total: float
    date: Optional[datetime] = None

    vendor_address: Optional[str] = None
    receipt_number: Optional[str] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    payment_method: Optional[str] = None
    items: List[LineItem] = []

    # --- Fields for Phase 2 & 3 ---
    voice_note: Optional[str] = None
    batch_id: Optional[str] = None
    created_at: datetime = datetime.now()
    image_url: Optional[str] = None      # <--- NEW: To store the GCS image link
    
    item_summary: Optional[str] = None
    primary_category: Optional[str] = None
    actionable_flag: bool = False