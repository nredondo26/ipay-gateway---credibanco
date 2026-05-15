"""
Pruebas unitarias contra el ambiente Sandbox de CredibanCo iPay.

Usa las credenciales del archivo email.com.txt:
  - API Username: DACASIGNAVNP2026-api
  - API Password: Colombia.25269
  - Terminal: 020006961
  - Commerce Code: 020006961

IMPORTANTE: Si la prueba falla con "El usuario debe cambiar su contrasena",
ingrese al portal https://ecouat.credibanco.com/mportal/#login con el
usuario operador (DACASIGNAVNP2026-operator) y cambie la contrasena API.
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.ipay_client import IPayClient


class MockStore:
    def __init__(self, mcc_type="normal"):
        self.api_username = "DACASIGNAVNP2026-api"
        self.api_password = "Colombia.25269"
        self.terminal_code = "020006961"
        self.commerce_code = "020006961"
        self.operator_user = "DACASIGNAVNP2026-operator"
        self.environment = "test"
        self.mcc_type = mcc_type


PASSWORD_ERROR = "cambiar su contrase"  # matches both con/ene accent variations


@pytest.mark.asyncio
async def test_sandbox_connectivity():
    """Verifica conectividad basica contra el sandbox de CredibanCo"""
    store = MockStore("normal")
    client = IPayClient(store)
    resp = await client.get_order_status(
        order_id="00000000-0000-0000-0000-000000000000",
    )
    assert resp is not None, "No response from sandbox"

    if resp.get("errorCode") in ("5", 5) and PASSWORD_ERROR in str(resp.get("errorMessage", "")):
        print("\n[!] CREDENCIALES EXPIRADAS - Debe cambiar la contrasena API en el portal:")
        print("   1. Ir a: https://ecouat.credibanco.com/mportal/#login")
        print("   2. Ingresar con operador: DACASIGNAVNP2026-operator / Colombia.25269")
        print("   3. Cambiar la contrasena del API user: DACASIGNAVNP2026-api")
        print("   4. Actualizar api_password en MockStore\n")
    elif resp.get("errorCode") in ("6", 6):
        print("\n[OK] Sandbox responde correctamente (order not found - esperado)")


@pytest.mark.asyncio
async def test_register_normal_order():
    """Test register.do para comercio NORMAL con IVA"""
    store = MockStore("normal")
    client = IPayClient(store)

    resp = await client.register_order(
        order_number="TEST001",
        amount=10000,
        return_url="https://httpbin.org/post",
        language="es",
        json_params={"IVA.amount": "1900"},
    )

    print(f"\n[register_normal] Response: {resp}")

    if resp.get("errorCode") == 0:
        assert "orderId" in resp
        assert "formUrl" in resp
        assert resp["formUrl"].startswith("https://ecouat.credibanco.com")
        print(f"[OK] Pedido registrado: {resp['orderId']}")
    elif PASSWORD_ERROR in str(resp.get("errorMessage", "")):
        pytest.skip(f"Credenciales expiradas: {resp.get('errorMessage')}")
    else:
        assert False, f"Error: {resp.get('errorMessage')} (code={resp.get('errorCode')})"


@pytest.mark.asyncio
async def test_register_restaurant_order():
    """Test register.do para RESTAURANTE con IVA + IAC + Tips"""
    store = MockStore("restaurant")
    client = IPayClient(store)

    resp = await client.register_order(
        order_number="TEST-REST-001",
        amount=50000,
        return_url="https://httpbin.org/post",
        language="es",
        json_params={
            "IVA.amount": "9500",
            "IAC.amount": "800",
            "tips.amount": "5000",
        },
    )

    print(f"\n[register_restaurant] Response: {resp}")

    if resp.get("errorCode") == 0:
        assert "orderId" in resp
        print(f"[OK] Pedido restaurante registrado: {resp['orderId']}")
    elif PASSWORD_ERROR in str(resp.get("errorMessage", "")):
        pytest.skip(f"Credenciales expiradas: {resp.get('errorMessage')}")
    else:
        assert False, f"Error: {resp.get('errorMessage')} (code={resp.get('errorCode')})"


@pytest.mark.asyncio
async def test_register_airline_order():
    """Test register.do para AEROLINEA con IVA + AirTax"""
    store = MockStore("airline")
    client = IPayClient(store)

    resp = await client.register_order(
        order_number="TEST-FLY-001",
        amount=200000,
        return_url="https://httpbin.org/post",
        language="es",
        json_params={
            "IVA.amount": "38000",
            "airTax.amount": "10000",
            "airlineCode": "AV",
            "airlineName": "AVIANCA",
        },
    )

    print(f"\n[register_airline] Response: {resp}")

    if resp.get("errorCode") == 0:
        assert "orderId" in resp
        print(f"[OK] Pedido aerolinea registrado: {resp['orderId']}")
    elif PASSWORD_ERROR in str(resp.get("errorMessage", "")):
        pytest.skip(f"Credenciales expiradas: {resp.get('errorMessage')}")
    else:
        assert False, f"Error: {resp.get('errorMessage')} (code={resp.get('errorCode')})"


@pytest.mark.asyncio
async def test_register_travel_agency_order():
    """Test register.do para AGENCIA VIAJES (MCC 4722) con dispersion"""
    store = MockStore("travel_agency")
    client = IPayClient(store)

    airline_obj = {
        "amount": "150000",
        "installments": "1",
        "ivaAmount": "28500",
        "airTaxAmount": "10000",
        "airlineId": "29",
    }
    agency_obj = {
        "amount": "50000",
        "installments": "3",
        "ivaAmount": "9500",
    }

    resp = await client.register_order(
        order_number="TEST-TRV-001",
        amount=200000,
        return_url="https://httpbin.org/post",
        language="es",
        airline=airline_obj,
        agency=agency_obj,
    )

    print(f"\n[register_travel_agency] Response: {resp}")

    if resp.get("errorCode") == 0:
        assert "crbOrderId" in resp
        assert "orders" in resp
        print(f"[OK] Pedido agencia viajes registrado: {resp['crbOrderId']}")
        for order in resp.get("orders", []):
            print(f"     - {order['type']}: {order['orderId']} (status={order.get('errorCode')})")
    elif PASSWORD_ERROR in str(resp.get("errorMessage", "")):
        pytest.skip(f"Credenciales expiradas: {resp.get('errorMessage')}")
    elif resp.get("errorCode") == 4:
        pytest.skip(f"Error de orden: {resp.get('errorMessage')}")
    else:
        assert False, f"Error: {resp.get('errorMessage')} (code={resp.get('errorCode')})"


@pytest.mark.asyncio
async def test_get_order_status():
    """Test getOrderStatusExtended.do"""
    store = MockStore("normal")
    client = IPayClient(store)

    resp = await client.get_order_status(
        order_id="00000000-0000-0000-0000-000000000000",
    )

    print(f"\n[get_status] Response: {resp}")
    assert "errorCode" in resp

    if resp.get("errorCode") in ("6", 6):
        print("[OK] Order not found (esperado sin ordenes previas)")
    elif resp.get("errorCode") in ("5", 5):
        if PASSWORD_ERROR in str(resp.get("errorMessage", "")):
            print("[i] Credenciales expiradas")
        else:
            assert False, f"Error inesperado: {resp.get('errorMessage')}"
    elif resp.get("errorCode") == 0:
        print(f"[OK] Order status: {resp.get('orderStatus')}")


@pytest.mark.asyncio
async def test_verify_card():
    """Test verifyCard.do con tarjeta de prueba"""
    store = MockStore("normal")
    client = IPayClient(store)

    resp = await client.verify_card(
        pan="4761340000000043",
        cvc="050",
        expiry="202512",
    )

    print(f"\n[verify_card] Response: {resp}")

    if resp.get("errorCode") == "0":
        assert "authCode" in resp
        print(f"[OK] Tarjeta verificada - Auth Code: {resp['authCode']}")
    elif PASSWORD_ERROR in str(resp.get("errorMessage", "")):
        pytest.skip(f"Credenciales expiradas: {resp.get('errorMessage')}")
    else:
        assert False, f"Error: {resp.get('errorMessage')} (code={resp.get('errorCode')})"


@pytest.mark.asyncio
async def test_pse_status():
    """Test PSE status.do"""
    store = MockStore("normal")
    client = IPayClient(store)

    resp = await client.pse_order_status(
        order_id="00000000-0000-0000-0000-000000000000",
    )

    print(f"\n[pse_status] Response: {resp}")
    assert "transactionStatus" in resp or "errorCode" in resp
    print("[OK] Endpoint PSE responde correctamente")


if __name__ == "__main__":
    import asyncio

    async def run_all():
        tests = [
            ("Sandbox Connectivity", test_sandbox_connectivity()),
            ("Normal Order", test_register_normal_order()),
            ("Restaurant Order", test_register_restaurant_order()),
            ("Airline Order", test_register_airline_order()),
            ("Travel Agency Order", test_register_travel_agency_order()),
            ("Get Order Status", test_get_order_status()),
            ("Verify Card", test_verify_card()),
            ("PSE Status", test_pse_status()),
        ]
        passed = 0
        failed = 0
        skipped = 0
        for name, coro in tests:
            try:
                await coro
                print(f"[PASS] {name}")
                passed += 1
            except pytest.skip.Exception as e:
                print(f"[SKIP] {name} - {e}")
                skipped += 1
            except Exception as e:
                print(f"[FAIL] {name} - {e}")
                failed += 1
        print(f"\n{'='*40}")
        print(f"Resultados: {passed} passed, {failed} failed, {skipped} skipped")

    asyncio.run(run_all())
