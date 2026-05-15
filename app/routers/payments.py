import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Store, Transaction
from app.services.ipay_client import IPayClient

router = APIRouter(prefix="/payments", tags=["payments"])
templates = Jinja2Templates(directory="app/templates")


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
        merchant_order_number=request_data.get("orderNumber") or request_data.get("merchantOrderNumber"),
        amount=Decimal(str(request_data.get("amount", 0))) if request_data.get("amount") else None,
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


def get_store_or_404(store_id: int, db: Session) -> Store:
    store = db.query(Store).filter(Store.id == store_id, Store.is_active == True).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found or inactive")
    return store


@router.get("/register/{store_id}", response_class=HTMLResponse)
async def register_form(store_id: int, request: Request, db: Session = Depends(get_db)):
    store = get_store_or_404(store_id, db)
    client = IPayClient(store)
    taxes = client.get_active_taxes()
    return templates.TemplateResponse("payments/register.html", {
        "request": request,
        "store": store,
        "taxes": taxes,
    })


@router.post("/register", response_class=HTMLResponse)
async def register_order(
    request: Request,
    store_id: int = Form(...),
    order_number: str = Form(...),
    amount: int = Form(...),
    return_url: str = Form(...),
    fail_url: str = Form(""),
    language: str = Form("es"),
    email: str = Form(""),
    iva_amount: int = Form(0),
    iac_amount: int = Form(0),
    tips_amount: int = Form(0),
    airtax_amount: int = Form(0),
    airline_code: str = Form(""),
    airline_name: str = Form(""),
    commerce_code: str = Form(""),
    airline_amount: int = Form(0),
    airline_installments: int = Form(0),
    airline_iva: int = Form(0),
    airline_airtax: int = Form(0),
    airline_id: str = Form(""),
    agency_amount: int = Form(0),
    agency_installments: int = Form(0),
    agency_iva: int = Form(0),
    db: Session = Depends(get_db),
):
    store = get_store_or_404(store_id, db)
    client = IPayClient(store)
    mcc = store.mcc_type

    form_data = {
        "iva_amount": iva_amount,
        "iac_amount": iac_amount,
        "tips_amount": tips_amount,
        "airtax_amount": airtax_amount,
        "airline_code": airline_code,
        "airline_name": airline_name,
        "commerce_code": commerce_code,
    }

    json_params = client._build_json_params(mcc, form_data)

    req_data = {
        "orderNumber": order_number,
        "amount": amount,
        "returnUrl": return_url,
        "language": language,
    }

    airline_obj = None
    agency_obj = None

    if mcc == "travel_agency":
        airline_obj = {
            "amount": str(airline_amount),
            "installments": str(airline_installments),
            "ivaAmount": str(airline_iva),
            "airlineId": airline_id,
        }
        if airline_airtax:
            airline_obj["airTaxAmount"] = str(airline_airtax)

        agency_obj = {
            "amount": str(agency_amount),
            "installments": str(agency_installments),
            "ivaAmount": str(agency_iva),
        }
        req_data["airline"] = airline_obj
        req_data["agency"] = agency_obj

    if email:
        req_data["email"] = email
    if fail_url:
        req_data["failUrl"] = fail_url

    resp = await client.register_order(
        order_number=order_number,
        amount=amount,
        return_url=return_url,
        fail_url=fail_url or None,
        language=language,
        email=email or None,
        json_params=json_params if json_params else None,
        airline=airline_obj,
        agency=agency_obj,
    )

    status = "error" if resp.get("errorCode") != 0 else "success"
    txn = log_transaction(db, store_id, "register_order", req_data, resp, status)

    return templates.TemplateResponse("payments/result.html", {
        "request": request,
        "store": store,
        "transaction": txn,
        "response": resp,
        "service": "Registro de Pedido",
    })


@router.get("/status/{store_id}", response_class=HTMLResponse)
async def status_form(store_id: int, request: Request, db: Session = Depends(get_db)):
    store = get_store_or_404(store_id, db)
    return templates.TemplateResponse("payments/status.html", {
        "request": request,
        "store": store,
    })


@router.post("/status", response_class=HTMLResponse)
async def order_status(
    request: Request,
    store_id: int = Form(...),
    order_id: str = Form(""),
    merchant_order_number: str = Form(""),
    db: Session = Depends(get_db),
):
    store = get_store_or_404(store_id, db)
    client = IPayClient(store)

    req_data = {}
    if order_id:
        req_data["order_id"] = order_id
    if merchant_order_number:
        req_data["merchant_order_number"] = merchant_order_number

    resp = await client.get_order_status(**req_data)

    status = "error" if resp.get("errorCode") != 0 else "success"
    txn = log_transaction(db, store_id, "get_order_status", req_data, resp, status)

    return templates.TemplateResponse("payments/result.html", {
        "request": request,
        "store": store,
        "transaction": txn,
        "response": resp,
        "service": "Consulta de Estado",
    })


@router.get("/refund/{store_id}", response_class=HTMLResponse)
async def refund_form(store_id: int, request: Request, db: Session = Depends(get_db)):
    store = get_store_or_404(store_id, db)
    return templates.TemplateResponse("payments/refund.html", {
        "request": request,
        "store": store,
    })


@router.post("/refund", response_class=HTMLResponse)
async def refund_order(
    request: Request,
    store_id: int = Form(...),
    order_id: str = Form(...),
    amount: int = Form(...),
    merchant_order_number: str = Form(""),
    db: Session = Depends(get_db),
):
    store = get_store_or_404(store_id, db)
    client = IPayClient(store)

    req_data = {"order_id": order_id, "amount": amount}
    if merchant_order_number:
        req_data["merchant_order_number"] = merchant_order_number

    resp = await client.refund(**req_data)

    status = "error" if resp.get("errorCode") != 0 else "success"
    txn = log_transaction(db, store_id, "refund", req_data, resp, status)

    return templates.TemplateResponse("payments/result.html", {
        "request": request,
        "store": store,
        "transaction": txn,
        "response": resp,
        "service": "Anulación de Pago",
    })


@router.get("/payment-order/{store_id}", response_class=HTMLResponse)
async def payment_order_form(store_id: int, request: Request, db: Session = Depends(get_db)):
    store = get_store_or_404(store_id, db)
    return templates.TemplateResponse("payments/payment_order.html", {
        "request": request,
        "store": store,
    })


@router.post("/payment-order", response_class=HTMLResponse)
async def payment_order(
    request: Request,
    store_id: int = Form(...),
    md_order: str = Form(...),
    pan: str = Form(...),
    cvc: str = Form(...),
    year: str = Form(...),
    month: str = Form(...),
    cardholder_name: str = Form(...),
    email: str = Form(""),
    db: Session = Depends(get_db),
):
    store = get_store_or_404(store_id, db)
    client = IPayClient(store)

    req_data = {
        "md_order": md_order,
        "pan": pan,
        "cvc": cvc,
        "year": year,
        "month": month,
        "cardholder_name": cardholder_name,
        "email": email,
    }

    if store.mcc_type == "travel_agency":
        resp = await client.payment_order_mcc4722(
            order_id=md_order,
            pan=pan,
            cvc=cvc,
            year=year,
            month=month,
            cardholder_name=cardholder_name,
            email=email or None,
        )
    else:
        resp = await client.payment_order(
            md_order=md_order,
            pan=pan,
            cvc=cvc,
            year=year,
            month=month,
            cardholder_name=cardholder_name,
            email=email or None,
        )

    status = "error" if resp.get("errorCode") != 0 else "success"
    txn = log_transaction(db, store_id, "payment_order", req_data, resp, status)

    return templates.TemplateResponse("payments/result.html", {
        "request": request,
        "store": store,
        "transaction": txn,
        "response": resp,
        "service": "Pago con Tarjeta",
    })


@router.post("/pse-status", response_class=HTMLResponse)
async def pse_status(
    request: Request,
    store_id: int = Form(...),
    order_id: str = Form(...),
    db: Session = Depends(get_db),
):
    store = get_store_or_404(store_id, db)
    client = IPayClient(store)
    req_data = {"order_id": order_id}
    resp = await client.pse_order_status(order_id=order_id)
    status = "success" if resp.get("transactionStatus") == "OK" else "error"
    txn = log_transaction(db, store_id, "pse_status", req_data, resp, status)
    return templates.TemplateResponse("payments/result.html", {
        "request": request,
        "store": store,
        "transaction": txn,
        "response": resp,
        "service": "Consulta PSE",
    })


@router.get("/verify-card/{store_id}", response_class=HTMLResponse)
async def verify_card_form(store_id: int, request: Request, db: Session = Depends(get_db)):
    store = get_store_or_404(store_id, db)
    return templates.TemplateResponse("payments/verify_card.html", {
        "request": request,
        "store": store,
    })


@router.post("/verify-card", response_class=HTMLResponse)
async def verify_card(
    request: Request,
    store_id: int = Form(...),
    pan: str = Form(...),
    cvc: str = Form(...),
    expiry: str = Form(...),
    db: Session = Depends(get_db),
):
    store = get_store_or_404(store_id, db)
    client = IPayClient(store)

    req_data = {"pan": pan, "cvc": cvc, "expiry": expiry}
    resp = await client.verify_card(**req_data)

    status = "error" if resp.get("errorCode") != 0 else "success"
    txn = log_transaction(db, store_id, "verify_card", req_data, resp, status)

    return templates.TemplateResponse("payments/result.html", {
        "request": request,
        "store": store,
        "transaction": txn,
        "response": resp,
        "service": "Verificación de Tarjeta",
    })
