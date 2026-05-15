from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Store, Transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def transaction_list(
    request: Request,
    store_id: int = Query(None),
    status: str = Query(None),
    service: str = Query(None),
    q: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    page: int = Query(1),
    db: Session = Depends(get_db),
):
    per_page = 50
    query = db.query(Transaction).join(Store)

    if store_id:
        query = query.filter(Transaction.store_id == store_id)
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

    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    transactions = query.order_by(desc(Transaction.id)).offset((page - 1) * per_page).limit(per_page).all()

    stores = db.query(Store).all()
    services = ["register_order", "get_order_status", "refund", "payment_order", "verify_card", "pse_status"]

    return templates.TemplateResponse("transactions/list.html", {
        "request": request,
        "transactions": transactions,
        "stores": stores,
        "all_stores": db.query(Store).all(),
        "services": services,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "store_id": store_id,
        "status": status,
        "service": service,
        "q": q,
        "date_from": date_from,
        "date_to": date_to,
    })


@router.get("/{txn_id}", response_class=HTMLResponse)
async def transaction_detail(txn_id: int, request: Request, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    store = db.query(Store).filter(Store.id == txn.store_id).first()
    return templates.TemplateResponse("transactions/detail.html", {
        "request": request,
        "txn": txn,
        "store": store,
    })


@router.get("/export/csv")
async def export_csv(
    store_id: int = Query(None),
    status: str = Query(None),
    service: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).join(Store)
    if store_id:
        query = query.filter(Transaction.store_id == store_id)
    if status:
        query = query.filter(Transaction.status == status)
    if service:
        query = query.filter(Transaction.service == service)
    if date_from:
        query = query.filter(Transaction.created_at >= date_from)
    if date_to:
        query = query.filter(Transaction.created_at <= date_to + " 23:59:59")

    transactions = query.order_by(desc(Transaction.id)).all()

    lines = ["id,store,service,order_id,merchant_order,amount,currency,status,order_status,error_code,auth_code,card_mask,created_at"]
    for txn in transactions:
        store_name = db.query(Store.name).filter(Store.id == txn.store_id).scalar() or ""
        lines.append(
            f"{txn.id},{store_name},{txn.service},{txn.order_id or ''},{txn.merchant_order_number or ''},"
            f"{txn.amount or ''},{txn.currency},{txn.status},{txn.order_status or ''},{txn.error_code or ''},"
            f"{txn.auth_code or ''},{txn.card_mask or ''},{txn.created_at}"
        )
    return PlainTextResponse("\n".join(lines), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=transactions.csv"})
