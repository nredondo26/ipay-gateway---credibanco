import json

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Store, Transaction
from app.schemas import StoreCreate, StoreUpdate
from app.services.ipay_client import IPayClient

router = APIRouter(prefix="/stores", tags=["stores"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def list_stores(request: Request, db: Session = Depends(get_db)):
    stores = db.query(Store).all()
    return templates.TemplateResponse("stores/list.html", {"request": request, "stores": stores})


@router.get("/{store_id}/edit")
async def edit_store_form(store_id: int, request: Request, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    transactions = db.query(Transaction).filter(Transaction.store_id == store_id).order_by(Transaction.id.desc()).limit(20).all()
    tax_checkboxes_map = {
        mt["id"]: IPayClient.get_mcc_tax_checkboxes(mt["id"])
        for mt in IPayClient.get_mcc_types()
    }
    return templates.TemplateResponse("stores/detail.html", {
        "request": request,
        "store": store,
        "transactions": transactions,
        "environments": IPayClient.get_environments(),
        "mcc_types": IPayClient.get_mcc_types(),
        "tax_checkboxes_map": tax_checkboxes_map,
        "store_tax_exceptions": json.loads(store.tax_exceptions) if store.tax_exceptions else [],
    })


@router.get("/new")
async def new_store_form(request: Request):
    tax_checkboxes_map = {
        mt["id"]: IPayClient.get_mcc_tax_checkboxes(mt["id"])
        for mt in IPayClient.get_mcc_types()
    }
    return templates.TemplateResponse("stores/create.html", {
        "request": request,
        "environments": IPayClient.get_environments(),
        "mcc_types": IPayClient.get_mcc_types(),
        "tax_checkboxes_map": tax_checkboxes_map,
        "store_tax_exceptions": [],
    })


@router.post("/new")
async def create_store(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    api_username: str = Form(...),
    api_password: str = Form(...),
    terminal_code: str = Form(""),
    commerce_code: str = Form(""),
    operator_user: str = Form(""),
    environment: str = Form("test"),
    mcc_type: str = Form("normal"),
    callback_url: str = Form(""),
    fail_callback_url: str = Form(""),
    tax_exceptions: str = Form(""),
    db: Session = Depends(get_db),
):
    parsed_exceptions = []
    if tax_exceptions:
        parsed_exceptions = [k for k in tax_exceptions.split(",") if k]
    store = Store(
        name=name,
        description=description or None,
        api_username=api_username,
        api_password=api_password,
        terminal_code=terminal_code or None,
        commerce_code=commerce_code or None,
        operator_user=operator_user or None,
        environment=environment,
        mcc_type=mcc_type,
        callback_url=callback_url or None,
        fail_callback_url=fail_callback_url or None,
        tax_exceptions=json.dumps(parsed_exceptions),
    )
    db.add(store)
    db.commit()
    return RedirectResponse(url="/stores", status_code=303)


@router.post("/{store_id}/edit")
async def update_store(
    store_id: int,
    name: str = Form(...),
    description: str = Form(""),
    api_username: str = Form(...),
    api_password: str = Form(...),
    terminal_code: str = Form(""),
    commerce_code: str = Form(""),
    operator_user: str = Form(""),
    environment: str = Form("test"),
    mcc_type: str = Form("normal"),
    callback_url: str = Form(""),
    fail_callback_url: str = Form(""),
    is_active: bool = Form(True),
    tax_exceptions: str = Form(""),
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    parsed_exceptions = [k for k in tax_exceptions.split(",") if k] if tax_exceptions else []
    store.name = name
    store.description = description or None
    store.api_username = api_username
    store.api_password = api_password
    store.terminal_code = terminal_code or None
    store.commerce_code = commerce_code or None
    store.operator_user = operator_user or None
    store.environment = environment
    store.mcc_type = mcc_type
    store.callback_url = callback_url or None
    store.fail_callback_url = fail_callback_url or None
    store.is_active = is_active
    store.tax_exceptions = json.dumps(parsed_exceptions)
    db.commit()
    return RedirectResponse(url=f"/stores/{store_id}/edit", status_code=303)


@router.post("/{store_id}/edit-config")
async def update_store_config(
    store_id: int,
    name: str = Form(...),
    api_username: str = Form(...),
    api_password: str = Form(...),
    terminal_code: str = Form(""),
    commerce_code: str = Form(""),
    environment: str = Form("test"),
    mcc_type: str = Form("normal"),
    callback_url: str = Form(""),
    is_active: str = Form("true"),
    tax_exceptions: str = Form(""),
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    parsed_exceptions = [k for k in tax_exceptions.split(",") if k] if tax_exceptions else []
    store.name = name
    store.api_username = api_username
    store.api_password = api_password
    store.terminal_code = terminal_code or None
    store.commerce_code = commerce_code or None
    store.environment = environment
    store.mcc_type = mcc_type
    store.callback_url = callback_url or None
    store.is_active = is_active == "true"
    store.tax_exceptions = json.dumps(parsed_exceptions)
    db.commit()
    return RedirectResponse(url=f"/stores/{store_id}/edit", status_code=303)


@router.post("/{store_id}/delete")
async def delete_store(store_id: int, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    db.delete(store)
    db.commit()
    return RedirectResponse(url="/stores", status_code=303)
