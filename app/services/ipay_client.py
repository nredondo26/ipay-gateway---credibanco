import json
from typing import Optional

import httpx

BASE_URLS = {
    "test": {
        "normal": "https://ecouat.credibanco.com/payment/rest",
        "proxy": "https://ecouat.credibanco.com/proxy/rest",
        "pse": "https://ecouat.credibanco.com/payment/pse",
    },
    "production": {
        "normal": "https://eco.credibanco.com/payment/rest",
        "proxy": "https://eco.credibanco.com/proxy/rest",
        "pse": "https://eco.credibanco.com/payment/pse",
    },
}


class IPayClient:
    def __init__(self, store):
        self.store = store
        self.env = store.environment
        self.is_mcc4722 = store.mcc_type == "travel_agency"
        base = BASE_URLS[self.env]
        self.rest_url = base["proxy"] if self.is_mcc4722 else base["normal"]
        self.pse_url = base["pse"]

    async def _post(self, endpoint: str, data: dict) -> dict:
        url = f"{self.rest_url}/{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, data=data)
            return resp.json()

    async def _get(self, endpoint: str, params: dict) -> dict:
        url = f"{self.rest_url}/{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            return resp.json()

    def _get_exceptions(self) -> list:
        raw = getattr(self.store, "tax_exceptions", "[]")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
        return list(raw) if isinstance(raw, (list, tuple)) else []

    def _build_json_params(self, mcc_type: str, form_data: dict) -> dict:
        jp = {}
        exc = self._get_exceptions()
        if form_data.get("iva_amount") and "iva_amount" not in exc:
            jp["IVA.amount"] = str(form_data["iva_amount"])
        if mcc_type == "restaurant":
            if form_data.get("iac_amount") and "iac_amount" not in exc:
                jp["IAC.amount"] = str(form_data["iac_amount"])
            if form_data.get("tips_amount") and "tips_amount" not in exc:
                jp["tips.amount"] = str(form_data["tips_amount"])
        if mcc_type in ("airline", "travel_agency"):
            if form_data.get("airtax_amount") and "airtax_amount" not in exc:
                jp["airTax.amount"] = str(form_data["airtax_amount"])
        if mcc_type == "airline":
            if form_data.get("airline_code"):
                jp["airlineCode"] = form_data["airline_code"]
            if form_data.get("airline_name"):
                jp["airlineName"] = form_data["airline_name"]
        if form_data.get("commerce_code"):
            jp["commerceCode"] = form_data["commerce_code"]
        return jp

    async def register_order(
        self,
        order_number: str,
        amount: int,
        return_url: str,
        currency: str = "COP",
        fail_url: Optional[str] = None,
        description: Optional[str] = None,
        language: str = "es",
        page_view: Optional[str] = None,
        client_id: Optional[str] = None,
        session_timeout: Optional[int] = None,
        expiration_date: Optional[str] = None,
        json_params: Optional[dict] = None,
        features: Optional[str] = None,
        email: Optional[str] = None,
        airline: Optional[dict] = None,
        agency: Optional[dict] = None,
    ) -> dict:
        mcc = self.store.mcc_type
        data = {
            "userName": self.store.api_username,
            "password": self.store.api_password,
            "orderNumber": order_number,
            "amount": str(amount),
            "currency": "170",
            "returnUrl": return_url,
            "language": language,
        }
        if fail_url:
            data["failUrl"] = fail_url
        if description:
            data["description"] = description
        if page_view:
            data["pageView"] = page_view
        if client_id:
            data["clientId"] = client_id
        if session_timeout:
            data["sessionTimeoutSecs"] = str(session_timeout)
        if expiration_date:
            data["expirationDate"] = expiration_date
        if features:
            data["features"] = features
        if email:
            data["email"] = email

        if json_params:
            data["jsonParams"] = json.dumps(json_params)

        if self.is_mcc4722:
            if airline:
                data["airline"] = json.dumps(airline)
            if agency:
                data["agency"] = json.dumps(agency)

        return await self._post("register.do", data)

    async def get_order_status(
        self,
        order_id: Optional[str] = None,
        merchant_order_number: Optional[str] = None,
        language: str = "es",
    ) -> dict:
        params = {
            "userName": self.store.api_username,
            "password": self.store.api_password,
            "language": language,
        }
        if order_id:
            params["orderId"] = order_id
        if merchant_order_number:
            params["merchantOrderNumber"] = merchant_order_number
        return await self._get("getOrderStatusExtended.do", params)

    async def refund(
        self,
        order_id: str,
        amount: int,
        merchant_order_number: Optional[str] = None,
    ) -> dict:
        data = {
            "userName": self.store.api_username,
            "password": self.store.api_password,
            "orderId": order_id,
            "amount": str(amount),
        }
        if merchant_order_number and self.is_mcc4722:
            data["merchantOrderNumber"] = merchant_order_number
        return await self._post("refund.do", data)

    async def payment_order(
        self,
        md_order: str,
        pan: str,
        cvc: str,
        year: str,
        month: str,
        cardholder_name: str,
        language: str = "es",
        ip: Optional[str] = None,
        email: Optional[str] = None,
        json_params: Optional[dict] = None,
        tii: Optional[str] = None,
    ) -> dict:
        data = {
            "userName": self.store.api_username,
            "password": self.store.api_password,
            "mdOrder": md_order,
            "$PAN": pan,
            "$CVC": cvc,
            "YYYY": year,
            "MM": month,
            "TEXT": cardholder_name,
            "language": language,
        }
        if ip:
            data["ip"] = ip
        if email:
            data["email"] = email
        if tii:
            data["tii"] = tii
        if json_params:
            data["jsonParams"] = json.dumps(json_params)
        return await self._post("paymentorder.do", data)

    async def payment_order_mcc4722(
        self,
        order_id: str,
        pan: str,
        cvc: str,
        year: str,
        month: str,
        cardholder_name: str,
        language: str = "es",
        ip: Optional[str] = None,
        email: Optional[str] = None,
        airline_installments: Optional[int] = None,
        agency_installments: Optional[int] = None,
        json_params: Optional[dict] = None,
    ) -> dict:
        data = {
            "userName": self.store.api_username,
            "password": self.store.api_password,
            "orderId": order_id,
            "pan": pan,
            "cvc": cvc,
            "year": year,
            "month": month,
            "cardholderName": cardholder_name,
            "language": language,
        }
        if ip:
            data["ip"] = ip
        if email:
            data["email"] = email
        if json_params:
            data["params"] = json.dumps(json_params)
        if airline_installments is not None:
            data["airline"] = json.dumps({"installments": str(airline_installments)})
        if agency_installments is not None:
            data["agency"] = json.dumps({"installments": str(agency_installments)})
        return await self._post("paymentorder.do", data)

    async def verify_card(
        self,
        pan: str,
        cvc: str,
        expiry: str,
    ) -> dict:
        data = {
            "userName": self.store.api_username,
            "password": self.store.api_password,
            "pan": pan,
            "cvc": cvc,
            "expiry": expiry,
        }
        return await self._post("verifyCard.do", data)

    async def pse_order_status(self, order_id: str, language: str = "es") -> dict:
        url = f"{self.pse_url}/status.do"
        payload = {"orderId": order_id, "language": language}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            return resp.json()

    @staticmethod
    def get_environments():
        return [
            {"id": "test", "name": "Pruebas (Sandbox)"},
            {"id": "production", "name": "Producción"},
        ]

    @staticmethod
    def get_mcc_types():
        return [
            {"id": "normal", "name": "Comercio Normal"},
            {"id": "restaurant", "name": "Restaurante"},
            {"id": "airline", "name": "Aerolínea"},
            {"id": "travel_agency", "name": "Agencia de Viajes (MCC 4722) con Dispersión"},
        ]

    @staticmethod
    def get_mcc_tax_checkboxes(mcc_type: str) -> list:
        boxes = {
            "normal": [
                {"key": "iva_amount", "label": "IVA (Impuesto al Valor Agregado)", "default": True},
            ],
            "restaurant": [
                {"key": "iva_amount", "label": "IVA (Impuesto al Valor Agregado)", "default": True},
                {"key": "iac_amount", "label": "IAC / Impoconsumo (Impuesto al Consumo)", "default": True},
                {"key": "tips_amount", "label": "Tips / Propina", "default": False},
            ],
            "airline": [
                {"key": "iva_amount", "label": "IVA (Impuesto al Valor Agregado)", "default": True},
                {"key": "airtax_amount", "label": "Air Tax (Tasa Aeroportuaria)", "default": False},
            ],
            "travel_agency": [
                {"key": "airline_iva", "label": "IVA por Aerolínea", "default": True},
                {"key": "airline_airtax", "label": "Air Tax por Aerolínea", "default": False},
                {"key": "agency_iva", "label": "IVA por Agencia", "default": True},
            ],
        }
        return boxes.get(mcc_type, boxes["normal"])

    def get_active_taxes(self) -> list:
        all_taxes = self.get_mcc_taxes(self.store.mcc_type)
        exc = self._get_exceptions()
        return [t for t in all_taxes if t["key"] not in exc]

    @staticmethod
    def get_mcc_taxes(mcc_type: str) -> list:
        taxes = {
            "normal": [
                {"key": "iva_amount", "label": "IVA amount", "required": True},
            ],
            "restaurant": [
                {"key": "iva_amount", "label": "IVA amount", "required": True},
                {"key": "iac_amount", "label": "IAC / Impoconsumo", "required": True},
                {"key": "tips_amount", "label": "Tips / Propina", "required": False},
            ],
            "airline": [
                {"key": "iva_amount", "label": "IVA amount", "required": True},
                {"key": "airtax_amount", "label": "Air Tax amount (Tasa Aeroportuaria)", "required": False},
                {"key": "airline_code", "label": "Airline Code (ID_AEROLINEA)", "required": False},
                {"key": "airline_name", "label": "Airline Name", "required": False},
            ],
            "travel_agency": [
                {"key": "airline_amount", "label": "Airline amount (monto tiquete)", "required": True},
                {"key": "airline_installments", "label": "Airline installments (cuotas)", "required": True},
                {"key": "airline_iva", "label": "Airline IVA amount", "required": True},
                {"key": "airline_airtax", "label": "Airline Air Tax amount", "required": False},
                {"key": "airline_id", "label": "Airline ID", "required": True},
                {"key": "agency_amount", "label": "Agency amount (monto agencia)", "required": True},
                {"key": "agency_installments", "label": "Agency installments (cuotas)", "required": True},
                {"key": "agency_iva", "label": "Agency IVA amount", "required": True},
            ],
        }
        return taxes.get(mcc_type, taxes["normal"])
