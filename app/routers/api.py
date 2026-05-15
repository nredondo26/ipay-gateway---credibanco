import json
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth import get_current_store
from app.database import get_db
from app.models import Store, Transaction
from app.schemas import StoreResponse, TransactionResponse
from app.services.ipay_client import IPayClient

router = APIRouter(prefix="/api", tags=["API iPay Gateway"])


def mask_pan(pan: str) -> str:
    if len(pan) >= 8:
        return pan[:6] + "*" * (len(pan) - 8) + pan[-4:]
    return pan


def log_transaction(
    db: Session,
    store_id: int,
    service: str,
    request_data: dict,
    response_data: dict,
    status: str = "pending",
) -> Transaction:
    txn = Transaction(
        store_id=store_id,
        service=service,
        order_id=response_data.get("orderId"),
        merchant_order_number=request_data.get("orderNumber")
        or request_data.get("merchantOrderNumber"),
        amount=Decimal(str(request_data.get("amount", 0)))
        if request_data.get("amount")
        else None,
        currency="COP",
        status=status,
        error_code=str(response_data.get("errorCode", "")),
        error_message=response_data.get("errorMessage"),
        request_data=json.dumps(request_data, default=str),
        response_data=json.dumps(response_data, default=str),
    )
    if "orderStatus" in response_data:
        txn.order_status = str(response_data["orderStatus"])
    if "actionCode" in response_data:
        txn.action_code = str(response_data["actionCode"])
    if "authCode" in response_data:
        txn.auth_code = str(response_data["authCode"])
    if request_data.get("$PAN"):
        txn.card_mask = mask_pan(request_data["$PAN"])
    elif request_data.get("pan"):
        txn.card_mask = mask_pan(request_data["pan"])

    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


class RegisterOrderRequest(BaseModel):
    order_number: str
    amount: int
    return_url: str
    fail_url: Optional[str] = None
    language: str = "es"
    email: Optional[str] = None
    description: Optional[str] = None
    json_params: Optional[dict] = None
    airline: Optional[dict] = None
    agency: Optional[dict] = None


class OrderStatusRequest(BaseModel):
    order_id: Optional[str] = None
    merchant_order_number: Optional[str] = None


class RefundRequest(BaseModel):
    order_id: str
    amount: int
    merchant_order_number: Optional[str] = None


class PaymentOrderRequest(BaseModel):
    md_order: str
    pan: str
    cvc: str
    year: str
    month: str
    cardholder_name: str
    email: Optional[str] = None


class VerifyCardRequest(BaseModel):
    pan: str
    cvc: str
    expiry: str


class PSEStatusRequest(BaseModel):
    order_id: str


@router.get("/stores/me", response_model=StoreResponse, summary="Obtener tienda autenticada")
async def get_my_store(current_store: Store = Depends(get_current_store)):
    return current_store


@router.get("/stores", response_model=list[StoreResponse], summary="Listar todas las tiendas")
async def list_stores(db: Session = Depends(get_db)):
    return db.query(Store).all()


@router.get("/stores/{store_id}", response_model=StoreResponse, summary="Obtener tienda por ID")
async def get_store(store_id: int, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.post("/payments/register", summary="Registrar pedido de pago (register.do)")
async def api_register_order(
    req: RegisterOrderRequest,
    current_store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    client = IPayClient(current_store)

    resp = await client.register_order(
        order_number=req.order_number,
        amount=req.amount,
        return_url=req.return_url,
        fail_url=req.fail_url,
        language=req.language,
        email=req.email or None,
        description=req.description,
        json_params=req.json_params,
        airline=req.airline,
        agency=req.agency,
    )

    status = "error" if resp.get("errorCode") != 0 else "success"
    req_data = req.model_dump(exclude_none=True)
    txn = log_transaction(db, current_store.id, "register_order", req_data, resp, status)

    return {
        "transaction_id": txn.id,
        "service": "register_order",
        "status": status,
        "response": resp,
    }


@router.post("/payments/status", summary="Consultar estado de pedido (getOrderStatusExtended.do)")
async def api_order_status(
    req: OrderStatusRequest,
    current_store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    client = IPayClient(current_store)

    kwargs = {}
    if req.order_id:
        kwargs["order_id"] = req.order_id
    if req.merchant_order_number:
        kwargs["merchant_order_number"] = req.merchant_order_number

    resp = await client.get_order_status(**kwargs)

    status = "error" if resp.get("errorCode") != 0 else "success"
    req_data = req.model_dump(exclude_none=True)
    txn = log_transaction(db, current_store.id, "get_order_status", req_data, resp, status)

    return {
        "transaction_id": txn.id,
        "service": "get_order_status",
        "status": status,
        "response": resp,
    }


@router.post("/payments/refund", summary="Anular/reembolsar pago (refund.do)")
async def api_refund(
    req: RefundRequest,
    current_store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    client = IPayClient(current_store)

    resp = await client.refund(
        order_id=req.order_id,
        amount=req.amount,
        merchant_order_number=req.merchant_order_number,
    )

    status = "error" if resp.get("errorCode") != 0 else "success"
    req_data = req.model_dump(exclude_none=True)
    txn = log_transaction(db, current_store.id, "refund", req_data, resp, status)

    return {
        "transaction_id": txn.id,
        "service": "refund",
        "status": status,
        "response": resp,
    }


@router.post("/payments/payment-order", summary="Procesar pago con tarjeta (paymentorder.do)")
async def api_payment_order(
    req: PaymentOrderRequest,
    current_store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    client = IPayClient(current_store)

    if current_store.mcc_type == "travel_agency":
        resp = await client.payment_order_mcc4722(
            order_id=req.md_order,
            pan=req.pan,
            cvc=req.cvc,
            year=req.year,
            month=req.month,
            cardholder_name=req.cardholder_name,
            email=req.email or None,
        )
    else:
        resp = await client.payment_order(
            md_order=req.md_order,
            pan=req.pan,
            cvc=req.cvc,
            year=req.year,
            month=req.month,
            cardholder_name=req.cardholder_name,
            email=req.email or None,
        )

    status = "error" if resp.get("errorCode") != 0 else "success"
    req_data = req.model_dump(exclude_none=True)
    txn = log_transaction(db, current_store.id, "payment_order", req_data, resp, status)

    return {
        "transaction_id": txn.id,
        "service": "payment_order",
        "status": status,
        "response": resp,
    }


@router.post("/payments/verify-card", summary="Verificar tarjeta (verifyCard.do)")
async def api_verify_card(
    req: VerifyCardRequest,
    current_store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    client = IPayClient(current_store)

    resp = await client.verify_card(pan=req.pan, cvc=req.cvc, expiry=req.expiry)

    status = "error" if resp.get("errorCode") != 0 else "success"
    req_data = req.model_dump(exclude_none=True)
    txn = log_transaction(db, current_store.id, "verify_card", req_data, resp, status)

    return {
        "transaction_id": txn.id,
        "service": "verify_card",
        "status": status,
        "response": resp,
    }


@router.post("/payments/pse-status", summary="Consultar estado PSE")
async def api_pse_status(
    req: PSEStatusRequest,
    current_store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    client = IPayClient(current_store)

    resp = await client.pse_order_status(order_id=req.order_id)

    status = "success" if resp.get("transactionStatus") == "OK" else "error"
    req_data = req.model_dump(exclude_none=True)
    txn = log_transaction(db, current_store.id, "pse_status", req_data, resp, status)

    return {
        "transaction_id": txn.id,
        "service": "pse_status",
        "status": status,
        "response": resp,
    }


@router.get("/transactions", response_model=list[TransactionResponse], summary="Listar transacciones")
async def api_transaction_list(
    store_id: int = Query(None, description="Filtrar por tienda (solo admin)"),
    status: str = Query(None, description="Filtrar por estado (success/error/pending)"),
    service: str = Query(None, description="Filtrar por servicio"),
    q: str = Query(None, description="Buscar por order_id, card_mask, auth_code"),
    date_from: str = Query(None, description="Desde fecha (YYYY-MM-DD)"),
    date_to: str = Query(None, description="Hasta fecha (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(50, ge=1, le=200, description="Resultados por página"),
    current_store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).join(Store)

    if store_id:
        query = query.filter(Transaction.store_id == store_id)
    else:
        query = query.filter(Transaction.store_id == current_store.id)

    if status:
        query = query.filter(Transaction.status == status)
    if service:
        query = query.filter(Transaction.service == service)
    if q:
        query = query.filter(
            Transaction.order_id.ilike(f"%{q}%")
            | Transaction.merchant_order_number.ilike(f"%{q}%")
            | Transaction.card_mask.ilike(f"%{q}%")
            | Transaction.auth_code.ilike(f"%{q}%")
        )
    if date_from:
        query = query.filter(Transaction.created_at >= date_from)
    if date_to:
        query = query.filter(Transaction.created_at <= date_to + " 23:59:59")

    return query.order_by(desc(Transaction.id)).offset((page - 1) * per_page).limit(per_page).all()


@router.get(
    "/transactions/{txn_id}",
    response_model=TransactionResponse,
    summary="Obtener detalle de transacción",
)
async def api_transaction_detail(
    txn_id: int,
    current_store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    txn = (
        db.query(Transaction)
        .filter(
            Transaction.id == txn_id,
            Transaction.store_id == current_store.id,
        )
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn
