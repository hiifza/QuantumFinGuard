from datetime import datetime

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    external_ref: str | None = None
    customer_id: str
    merchant_id: str
    merchant_category: str | None = None
    amount: float = Field(gt=0)
    currency: str = "USD"
    timestamp: datetime
    device_type: str | None = None
    card_type: str | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    source_dataset: str | None = None


class TransactionOut(BaseModel):
    id: str
    external_ref: str | None
    customer_id: str
    merchant_id: str
    merchant_category: str | None
    amount: float
    currency: str
    timestamp: datetime
    device_type: str | None
    card_type: str | None
    country: str | None
    record_hash: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int
