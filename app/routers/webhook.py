import json
import logging

from fastapi import APIRouter, Depends, Request as FastAPIRequest
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Store, Transaction

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/callback")
async def payment_callback(request: FastAPIRequest, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    md_order = params.get("mdOrder")

    if not md_order:
        logger.warning(f"Callback missing mdOrder: {params}")
        return {"error": "missing mdOrder"}

    txn = db.query(Transaction).filter(
        Transaction.order_id == md_order,
    ).order_by(Transaction.id.desc()).first()

    if not txn:
        logger.warning(f"Callback for unknown order {md_order}: {params}")
        return {"error": "transaction not found"}

    store = db.query(Store).filter(Store.id == txn.store_id).first()
    logger.info(f"Callback received for store #{txn.store_id} ({store.name if store else '?'}): {params}")

    operation = params.get("operation")
    status = params.get("status")

    if status == "1":
        txn.status = "success"
        if operation == "deposited":
            txn.order_status = "2"
        elif operation == "refunded":
            txn.order_status = "4"
        elif operation == "reversed":
            txn.order_status = "4"
    elif status == "0":
        txn.status = "error"
    txn.response_data = json.dumps(params, default=str)
    db.commit()

    return {"status": "ok"}
