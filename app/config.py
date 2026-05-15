from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./ipay_gateway.db"
    secret_key: str = "cambiar-esta-clave-en-produccion"
    admin_user: str = "admin"
    admin_password: str = "admin123"

    class Config:
        env_file = ".env"


settings = Settings()
