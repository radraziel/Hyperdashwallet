import os
import time
import requests

HL_INFO = os.getenv("HYPERLIQUID_INFO_URL", "https://api.hyperliquid.xyz/info")

DEFAULT_TIMEOUT = int(os.getenv("HL_TIMEOUT", "20"))

def _post(payload: dict):
    r = requests.post(HL_INFO, json=payload, timeout=DEFAULT_TIMEOUT, headers={"Content-Type":"application/json"})
    r.raise_for_status()
    return r.json()

def get_positions(address: str) -> dict:
    """
    clearinghouseState: posiciones y resumen de margin.
    """
    payload = {"type": "clearinghouseState", "user": address, "dex": ""}
    return _post(payload)

def get_open_orders(address: str):
    """
    frontendOpenOrders: órdenes abiertas con info extra de frontend.
    """
    payload = {"type": "frontendOpenOrders", "user": address, "dex": ""}
    return _post(payload)

def get_recent_fills(address: str, aggregate: bool = True, start_ms: int = None, end_ms: int = None, limit: int = 10):
    """
    userFills: últimos fills (hasta 2000). Limit lo aplicamos client-side.
    """
    payload = {"type": "userFills", "user": address, "aggregateByTime": bool(aggregate)}
    if start_ms and end_ms:
        # se podría usar userFillsByTime, pero para simplicidad tiramos de userFills y cortamos
        pass
    data = _post(payload)
    # ordenamos por tiempo desc y cortamos
    data_sorted = sorted(data, key=lambda x: x.get("time", 0), reverse=True)
    return data_sorted[:limit]
