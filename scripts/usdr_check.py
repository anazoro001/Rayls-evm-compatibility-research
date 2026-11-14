"""How is gas paid on Rayls? Native balance vs the USDr token, plus a fee reconciliation.

Usage:   python scripts/usdr_check.py RPC_URL LABEL [ADDRESS] [TX_HASH]
Example: python scripts/usdr_check.py "$RPC" rayls
         (with no ADDRESS/TX_HASH it picks the first transaction it finds in the latest ~50 blocks)

Read-only. Prints raw numbers and a few comparisons; it draws NO conclusions for you.
The USDr token address below is the one shown on the Rayls explorer; change it if that changes.
"""
import datetime
import json
import os
import sys

from rpcutil import rpc

USDR_TOKEN = "0x0000000000000000000000000000000000000400"
SEL = {"name": "0x06fdde03", "symbol": "0x95d89b41", "decimals": "0x313ce567", "totalSupply": "0x18160ddd"}


def pad_addr(addr):
    return "00" * 12 + addr[2:].lower()


def to_int(h):
    return int(h, 16) if isinstance(h, str) and h.startswith("0x") and len(h) > 2 else None


def decode_string(h):
    """Decode an ABI-encoded string (or a bytes32-style name). Returns None if empty."""
    if not isinstance(h, str) or h in ("0x", ""):
        return None
    try:
        raw = bytes.fromhex(h[2:])
        if len(raw) == 32:
            return raw.rstrip(b"\x00").decode("utf-8", "replace")
        off = int.from_bytes(raw[0:32], "big")
        ln = int.from_bytes(raw[off:off + 32], "big")
        return raw[off + 32: off + 32 + ln].decode("utf-8", "replace")
    except Exception:
        return f"<undecodable {h[:24]}...>"


def call(url, to, data):
    return rpc(url, "eth_call", [{"to": to, "data": data}, "latest"])


def find_recent_tx(url, lookback=50):
    head, err = rpc(url, "eth_blockNumber")
    if err:
        sys.exit(f"cannot read block number: {err}")
    latest = int(head, 16)
    for n in range(latest, latest - lookback, -1):
        b, err = rpc(url, "eth_getBlockByNumber", [hex(n), True])
        if b and b.get("transactions"):
            tx = b["transactions"][0]
            return tx["from"], tx["hash"], n
    sys.exit("no transactions found in the lookback window; pass an ADDRESS and TX_HASH yourself")


def main():
    if len(sys.argv) not in (3, 4, 5):
        sys.exit(__doc__)
    url, label = sys.argv[1], sys.argv[2]
    if len(sys.argv) == 5:
        addr, txh, blk = sys.argv[3], sys.argv[4], None
    else:
        addr, txh, blk = find_recent_tx(url)
    out = {"label": label, "captured_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "address": addr, "tx_hash": txh, "tx_block": blk, "usdr_token": USDR_TOKEN}

    print(f"address: {addr}\ntx:      {txh}   (explorer: https://explorer.rayls.com/tx/{txh})\n")

    # 1) native balance vs token balance for the same address
    native, e1 = rpc(url, "eth_getBalance", [addr, "latest"])
    bal, e2 = call(url, USDR_TOKEN, "0x70a08231" + pad_addr(addr))
    code, e3 = rpc(url, "eth_getCode", [USDR_TOKEN, "latest"])
    out["native_balance_hex"], out["token_balanceOf_hex"] = native, bal
    out["token_code_length_bytes"] = (len(code) - 2) // 2 if isinstance(code, str) else None
    print("eth_getBalance (native):        ", to_int(native), e1 or "")
    print("USDr token balanceOf(address):  ", to_int(bal), e2 or "")
    print("code at USDr token address:     ", out["token_code_length_bytes"], "bytes", e3 or "")
    if to_int(native) is not None and to_int(bal) is not None:
        out["native_equals_token_balance"] = to_int(native) == to_int(bal)
        print("native == token balance?        ", out["native_equals_token_balance"])

    # 2) token metadata
    meta = {}
    for k, sel in SEL.items():
        res, err = call(url, USDR_TOKEN, sel)
        meta[k] = err if err else (decode_string(res) if k in ("name", "symbol") else to_int(res))
    out["token_metadata"] = meta
    print("\ntoken metadata:", meta)

    # 3) fee reconciliation for the transaction
    tx, _ = rpc(url, "eth_getTransactionByHash", [txh])
    rc, err = rpc(url, "eth_getTransactionReceipt", [txh])
    if err or not rc:
        print("\nreceipt not available:", err)
    else:
        gas_used = to_int(rc.get("gasUsed"))
        price = to_int(rc.get("effectiveGasPrice")) or (to_int(tx.get("gasPrice")) if tx else None)
        fee = gas_used * price if gas_used is not None and price is not None else None
        dec = meta.get("decimals")
        out["receipt"] = {"status": rc.get("status"), "type": rc.get("type"), "gasUsed": gas_used,
                          "effectiveGasPrice": price, "fee_smallest_units": fee,
                          "tx_value_hex": tx.get("value") if tx else None}
        print("\nreceipt: status", rc.get("status"), "| type", rc.get("type"))
        print("gasUsed:", gas_used, "| effectiveGasPrice:", price)
        print("fee (gasUsed x price) in smallest units:", fee)
        if fee is not None:
            for d in sorted({18, 6, dec} - {None}):
                print(f"   as units with {d} decimals: {fee / 10 ** d:.12f}")
        print("Now open the explorer link above and write down the fee and unit it shows.")

    os.makedirs("data", exist_ok=True)
    path = f"data/usdr_check_{label}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print("\nsaved", path)


if __name__ == "__main__":
    main()