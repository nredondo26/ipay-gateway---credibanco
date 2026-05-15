# iPay Gateway — Integrador CredibanCo

> Pasarela de pagos REST para integración con **iPay de CredibanCo** (Colombia).  
> Interfaz web tipo POS virtual + API REST documentada con **Swagger/OpenAPI** y autenticación **JWT**.

---

## Tecnologías

| Capa | Tecnología |
|------|-----------|
| **Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11+) |
| **ORM** | SQLAlchemy 2.0 |
| **Base de datos** | SQLite (intercambiable por PostgreSQL/MySQL vía `database_url`) |
| **Frontend** | Jinja2 Templates + Bootstrap 5 + tema claro/oscuro |
| **Cliente HTTP** | httpx (async) |
| **Autenticación API** | JWT con `python-jose` + `OAuth2PasswordBearer` |
| **Documentación API** | Swagger UI (`/docs`) + ReDoc (`/redoc`) |
| **Servidor** | Uvicorn con recarga automática |

---

## Instalación

```bash
# Clonar
git clone https://github.com/nredondo26/ipay-gateway---credibanco.git
cd ipay-gateway

# Entorno virtual
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate  # Linux/Mac

# Dependencias
pip install -r requirements.txt
```

## Configuración

Variables de entorno (archivo `.env` en la raíz):

```env
DATABASE_URL=sqlite:///./ipay_gateway.db
SECRET_KEY=cambiar-esta-clave-en-produccion
```

## Ejecución

```bash
python main.py
```

Servidor en **http://localhost:8000**

| Recurso | URL |
|---------|-----|
| Interfaz web (dashboard) | `http://localhost:8000/` |
| Documentación Swagger | `http://localhost:8000/docs` |
| Documentación ReDoc | `http://localhost:8000/redoc` |
| Esquema OpenAPI | `http://localhost:8000/openapi.json` |

---

## Estructura del Proyecto

```
ipay-gateway/
├── main.py                  # Punto de entrada FastAPI
├── requirements.txt
├── .env                     # Configuración (no versionado)
├── ipay_gateway.db          # Base de datos SQLite
│
├── app/
│   ├── __init__.py
│   ├── config.py            # Configuración vía pydantic-settings
│   ├── database.py          # Engine y sesión SQLAlchemy
│   ├── models.py            # Modelos Store y Transaction
│   ├── schemas.py           # Esquemas Pydantic
│   ├── auth.py              # JWT: creación y verificación de tokens
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── ipay_client.py   # Cliente async para API iPay CredibanCo
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py          # POST /api/auth/token (login JWT)
│   │   ├── api.py           # API REST protegida con JWT
│   │   ├── stores.py        # CRUD de tiendas (vista web)
│   │   ├── payments.py      # Operaciones de pago (vista web)
│   │   ├── transactions.py  # Consulta de transacciones (vista web)
│   │   └── webhook.py       # Callback de iPay
│   │
│   ├── static/
│   │   └── css/
│   │       └── style.css    # Estilos tema claro/oscuro
│   │
│   └── templates/
│       ├── base.html        # Layout principal con navegación
│       ├── index.html       # Dashboard
│       ├── stores/          # CRUD y POS virtual
│       ├── payments/        # Formularios de pago
│       └── transactions/    # Listado y detalle
│
└── tests/
    └── test_ipay_sandbox.py
```

---

## Autenticación JWT (API REST)

La API REST bajo `/api/` está protegida con **JWT Bearer tokens**.

### Obtener token

```
POST /api/auth/token
Content-Type: application/x-www-form-urlencoded

username={api_username}&password={api_password}
```

Usa las mismas credenciales configuradas en cada tienda (`api_username` / `api_password`).

Respuesta:

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "store_id": 1,
  "store_name": "Mi Tienda"
}
```

### Usar token

Incluir en el header de cada petición:

```
Authorization: Bearer eyJhbGciOi...
```

### Desde Swagger UI

1. Abrir `http://localhost:8000/docs`
2. Click **Authorize**
3. Ingresar `api_username` y `api_password` de una tienda
4. Swagger obtendrá y gestionará el token automáticamente

---

## API REST — Endpoints

### Autenticación

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/auth/token` | Iniciar sesión y obtener JWT |

### Tiendas

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/stores/me` | Tienda autenticada |
| GET | `/api/stores` | Listar todas las tiendas |
| GET | `/api/stores/{id}` | Detalle de tienda |

### Pagos

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/payments/register` | Registrar pedido de pago (`register.do`) |
| POST | `/api/payments/status` | Consultar estado de pedido |
| POST | `/api/payments/refund` | Anular o reembolsar pago |
| POST | `/api/payments/payment-order` | Procesar pago con tarjeta |
| POST | `/api/payments/verify-card` | Verificar tarjeta |
| POST | `/api/payments/pse-status` | Consultar estado PSE |

### Transacciones

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/transactions` | Listar transacciones (filtrable, paginado) |
| GET | `/api/transactions/{id}` | Detalle de transacción |

---

## Webhook (Callback iPay)

iPay notifica cambios de estado vía GET a:

```
POST /webhook/callback?mdOrder=...&operation=...&status=...
```

La aplicación actualiza automáticamente la transacción correspondiente.

Callback global único:  
`http://localhost:8000/webhook/callback`

---

## Modelo de Datos

### Store (Tienda)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer (PK) | |
| `name` | String(255) | Nombre del comercio |
| `api_username` | String(50) | Usuario API iPay |
| `api_password` | String(50) | Contraseña API iPay |
| `terminal_code` | String(20) | Código de terminal |
| `commerce_code` | String(20) | Código de comercio |
| `environment` | String(10) | `test` o `production` |
| `mcc_type` | String(20) | `normal`, `restaurant`, `airline`, `travel_agency` |
| `is_active` | Boolean | Si la tienda está activa |

### Transaction (Transacción)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Integer (PK) | |
| `store_id` | FK → stores | Tienda asociada |
| `service` | String(50) | Tipo de operación |
| `order_id` | String(40) | ID de orden iPay |
| `amount` | Numeric(12,2) | Monto en pesos colombianos |
| `status` | String(20) | `pending`, `success`, `error` |
| `card_mask` | String(20) | PAN enmascarado |
| `request_data` | Text (JSON) | Datos enviados |
| `response_data` | Text (JSON) | Datos recibidos |

---

## Licencia

CredibanCo proporciona este manual a sus clientes para que puedan integrar sus soluciones de pago.  
Este proyecto busca acelerar esa integración, ofreciendo una interfaz lista para probar y consumir los servicios iPay de CredibanCo de forma rápida y sencilla.
