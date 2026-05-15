import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, String, Text, Boolean, Numeric, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey

from app.database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    api_username: Mapped[str] = mapped_column(String(50), nullable=False)
    api_password: Mapped[str] = mapped_column(String(50), nullable=False)
    terminal_code: Mapped[str] = mapped_column(String(20), nullable=True)
    commerce_code: Mapped[str] = mapped_column(String(20), nullable=True)
    operator_user: Mapped[str] = mapped_column(String(50), nullable=True)
    environment: Mapped[str] = mapped_column(String(10), default="test")
    mcc_type: Mapped[str] = mapped_column(String(20), default="normal")
    callback_url: Mapped[str] = mapped_column(String(512), nullable=True)
    fail_callback_url: Mapped[str] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tax_exceptions: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="store", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    order_id: Mapped[str] = mapped_column(String(40), nullable=True)
    merchant_order_number: Mapped[str] = mapped_column(String(32), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="COP")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    order_status: Mapped[str] = mapped_column(String(10), nullable=True)
    action_code: Mapped[str] = mapped_column(String(10), nullable=True)
    error_code: Mapped[str] = mapped_column(String(10), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    request_data: Mapped[str] = mapped_column(Text, nullable=True)
    response_data: Mapped[str] = mapped_column(Text, nullable=True)
    card_mask: Mapped[str] = mapped_column(String(20), nullable=True)
    auth_code: Mapped[str] = mapped_column(String(6), nullable=True)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    store: Mapped["Store"] = relationship(back_populates="transactions")
