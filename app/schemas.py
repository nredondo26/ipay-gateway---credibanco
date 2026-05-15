from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class StoreCreate(BaseModel):
    name: str
    description: Optional[str] = None
    api_username: str
    api_password: str
    terminal_code: Optional[str] = None
    commerce_code: Optional[str] = None
    operator_user: Optional[str] = None
    environment: str = "test"
    mcc_type: str = "normal"
    callback_url: Optional[str] = None
    fail_callback_url: Optional[str] = None


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    api_username: Optional[str] = None
    api_password: Optional[str] = None
    terminal_code: Optional[str] = None
    commerce_code: Optional[str] = None
    operator_user: Optional[str] = None
    environment: Optional[str] = None
    mcc_type: Optional[str] = None
    callback_url: Optional[str] = None
    fail_callback_url: Optional[str] = None
    is_active: Optional[bool] = None


class StoreResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    api_username: str
    terminal_code: Optional[str] = None
    commerce_code: Optional[str] = None
    operator_user: Optional[str] = None
    environment: str
    mcc_type: str
    callback_url: Optional[str] = None
    fail_callback_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RegisterOrderRequest(BaseModel):
    store_id: int
    order_number: str
    amount: int
    return_url: str
    currency: str = "COP"
    fail_url: Optional[str] = None
    description: Optional[str] = None
    language: str = "es"
    page_view: Optional[str] = None
    client_id: Optional[str] = None
    session_timeout: Optional[int] = None
    expiration_date: Optional[str] = None
    email: Optional[str] = None
    json_params: Optional[dict] = None


class RefundRequest(BaseModel):
    store_id: int
    order_id: str
    amount: int
    merchant_order_number: Optional[str] = None


class PaymentOrderRequest(BaseModel):
    store_id: int
    md_order: str
    pan: str
    cvc: str
    year: str
    month: str
    cardholder_name: str
    language: str = "es"
    ip: Optional[str] = None
    email: Optional[str] = None
    installments: Optional[int] = None


class VerifyCardRequest(BaseModel):
    store_id: int
    pan: str
    cvc: str
    expiry: str


class OrderStatusRequest(BaseModel):
    store_id: int
    order_id: Optional[str] = None
    merchant_order_number: Optional[str] = None


class PSEStatusRequest(BaseModel):
    store_id: int
    order_id: str


class TransactionResponse(BaseModel):
    id: int
    store_id: int
    service: str
    order_id: Optional[str] = None
    merchant_order_number: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: str
    status: str
    order_status: Optional[str] = None
    action_code: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    card_mask: Optional[str] = None
    auth_code: Optional[str] = None
    payment_method: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
