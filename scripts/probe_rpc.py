"""Step 2: JSON-RPC capability probe.

Usage:   python scripts/probe_rpc.py RPC_URL LABEL
Example: python scripts/probe_rpc.py "$RPC" rayls
         python scripts/probe_rpc.py http://127.0.0.1:8545 anvil

Writes data/rpc_probe_<LABEL>_<UTC time>.json. The URL itself is NOT saved
(RPC URLs can contain API keys); only the label is.
"""
import datetime
import json
import os
import sys

from rpcutil import rpc

METHODS = [
    ("web3_clientVersion", []),
    ("net_version", []),
    ("eth_chainId", []),
    ("eth_blockNumber", []),
    ("eth_gasPrice", []),
    ("eth_maxPriorityFeePerGas", []),
    ("eth_blobBaseFee", []),
    ("eth_feeHistory", ["0x4", "latest", [25, 75]]),
    ("eth_syncing", []),
    ("eth_getBlockReceipts", ["latest"]),
    ("eth_getProof", ["0x" + "00" * 20, [], "latest"]),
    ("debug_traceCall", [{"data": "0x00"}, "latest", {}]),
    ("trace_block", ["latest"]),
    ("txpool_status", []),
]

# Header fields that appear at specific Ethereum upgrades. Their presence says
# something about the header FORMAT, not about opcode support (use step 3 for that).
HEADER_FIELDS = [
    ("baseFeePerGas", "London"),
    ("withdrawalsRoot", "Shanghai"),
    ("blobGasUsed", "Cancun"),
    ("excessBlobGas", "Cancun"),
    ("parentBeaconBlockRoot", "Cancun"),
    ("requestsHash", "Prague"),
]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    url, label = sys.argv[1], sys.argv[2]
    now = datetime.datetime.now(datetime.timezone.utc)
    out = {"label": label, "captured_utc": now.isoformat(), "methods": {}}

    for method, params in METHODS:
        res, err = rpc(url, method, params)
        out["methods"][method] = {"result": res, "error": err}
        shown = err if err else str(res)[:80]
        print(f"{method:28} {'ERR ' if err else 'ok  '} {shown}")

    block, err = rpc(url, "eth_getBlockByNumber", ["latest", False])
    out["latest_block"] = block
    if err or not block:
        print("could not fetch latest block:", err)
    else:
        print("\nLatest block header fields (number %s):" % int(block["number"], 16))
        out["header_fields_present"] = {}
        for field, fork in HEADER_FIELDS:
            present = field in block
            out["header_fields_present"][field] = present
            print(f"  {field:24} ({fork:8}) {'present' if present else 'absent'}")
        print("  all keys:", sorted(block.keys()))

    os.makedirs("data", exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = f"data/rpc_probe_{label}_{stamp}.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print("\nsaved", path)


if __name__ == "__main__":
    main()
