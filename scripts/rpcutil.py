"""Tiny JSON-RPC helper shared by all scripts."""
import requests


def rpc(url, method, params=None, timeout=30):
    """Return (result, error). JSON-RPC errors are returned, not raised,
    so callers can record them as data (an error IS a finding)."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    try:
        r = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as e:
        return None, f"transport: {e}"
    try:
        body = r.json()
    except ValueError:
        return None, f"http {r.status_code}: non-JSON body"
    if "error" in body:
        err = body["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        return None, msg
    return body.get("result"), None
