import json
import uvicorn
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Store, Transaction
from app.routers import stores, payments, webhook, transactions, auth, api
from app.services.ipay_client import IPayClient

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="iPay Gateway - Integrador CredibanCo",
    description="API REST para integración con iPay de CredibanCo. "
    "Autenticación mediante JWT usando las credenciales (api_username/api_password) de cada tienda.\n\n"
    "1. Haz clic en **Authorize** e ingresa el **api_username** y **api_password** de una tienda.\n"
    "2. Swagger obtendrá automáticamente un token JWT.\n"
    "3. Los endpoints protegidos usarán ese token en el header `Authorization: Bearer <token>`.",
    version="2.0.0",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "defaultModelsExpandDepth": -1,
    },
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(stores.router)
app.include_router(payments.router)
app.include_router(webhook.router)
app.include_router(transactions.router)
app.include_router(auth.router)
app.include_router(api.router)

templates = Jinja2Templates(directory="app/templates")


@app.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    stores_list = db.query(Store).all()
    store_count = len(stores_list)
    txn_count = db.query(Transaction).count()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_txns = db.query(Transaction).filter(Transaction.created_at >= today_start)
    today_count = today_txns.count()
    today_approved = today_txns.filter(Transaction.status == "success").count()
    today_amount = db.query(func.sum(Transaction.amount)).filter(
        Transaction.created_at >= today_start,
        Transaction.status == "success"
    ).scalar() or 0

    return templates.TemplateResponse("index.html", {
        "request": request,
        "stores": stores_list,
        "store_count": store_count,
        "txn_count": txn_count,
        "today_count": today_count,
        "today_approved": today_approved,
        "today_amount": float(today_amount),
        "recent_txns": db.query(Transaction).order_by(Transaction.id.desc()).limit(10).all(),
        "mcc_types": IPayClient.get_mcc_types(),
    })


@app.get("/stores/{store_id}")
async def store_pos(store_id: int, request: Request, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        return RedirectResponse(url="/stores")

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    store_txns = db.query(Transaction).filter(Transaction.store_id == store_id)
    today_txns = store_txns.filter(Transaction.created_at >= today_start)

    stats = {
        "today_count": today_txns.count(),
        "today_approved": today_txns.filter(Transaction.status == "success").count(),
        "today_amount": float(db.query(func.sum(Transaction.amount)).filter(
            Transaction.store_id == store_id,
            Transaction.created_at >= today_start,
            Transaction.status == "success"
        ).scalar() or 0),
        "total_count": store_txns.count(),
    }

    recent = store_txns.order_by(Transaction.id.desc()).limit(20).all()

    raw = getattr(store, "tax_exceptions", "[]")
    try:
        store_tax_exceptions = json.loads(raw) if isinstance(raw, str) else list(raw)
    except (json.JSONDecodeError, TypeError):
        store_tax_exceptions = []

    tax_checkboxes_map = {
        mt["id"]: IPayClient.get_mcc_tax_checkboxes(mt["id"])
        for mt in IPayClient.get_mcc_types()
    }

    return templates.TemplateResponse("stores/pos.html", {
        "request": request,
        "store": store,
        "stats": stats,
        "recent_payments": recent,
        "environments": IPayClient.get_environments(),
        "mcc_types": IPayClient.get_mcc_types(),
        "tax_checkboxes_map": tax_checkboxes_map,
        "store_tax_exceptions": store_tax_exceptions,
    })


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/css/style.css")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
