from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.database import get_db
from app.models import Store

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/token", summary="Iniciar sesión y obtener token JWT")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    store = (
        db.query(Store)
        .filter(
            Store.api_username == form_data.username,
            Store.api_password == form_data.password,
            Store.is_active == True,
        )
        .first()
    )
    if not store:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": str(store.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "store_id": store.id,
        "store_name": store.name,
    }
