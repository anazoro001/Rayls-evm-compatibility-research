"""Step 4: block-semantics scan (free, read-only).

Usage:   python scripts/scan_blocks.py RPC_URL LABEL [N_BLOCKS]
Example: python scripts/scan_blocks.py "$RPC" rayls 300

Fetches the last N blocks (gently throttled), saves the raw JSON, and prints:
timestamp gaps, duplicate/backward timestamps, and which header values vary.
"""
import datetime
import json
import os
import sys
import time
from collections import Counter

from rpcutil import rpc


def analyze(blocks):
    ts = [int(b["timestamp"], 16) for b in blocks]
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    return {
        "blocks": len(blocks),
        "first_block": int(blocks[0]["number"], 16),
        "last_block": int(blocks[-1]["number"], 16),
        "same_timestamp_as_previous": sum(1 for g in gaps if g == 0),
        "backward_timestamps": sum(1 for g in gaps if g < 0),
        "timestamp_gap_histogram": {str(k): v for k, v in sorted(Counter(gaps).items())},
        "distinct_gasLimit": len({b["gasLimit"] for b in blocks}),
        "distinct_baseFeePerGas": sorted({int(b["baseFeePerGas"], 16) for b in blocks if "baseFeePerGas" in b})[:10],
        "distinct_mixHash": len({b.get("mixHash") for b in blocks}),
        "distinct_miner": len({b.get("miner") for b in blocks}),
        "distinct_difficulty": sorted({str(b.get("difficulty")) for b in blocks}),
        "txs_per_block_max": max(len(b["transactions"]) for b in blocks),
    }


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    url, label = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) == 4 else 300

    head, err = rpc(url, "eth_blockNumber")
    if err:
        sys.exit(f"cannot read block number: {err}")
    latest = int(head, 16)

    blocks = []
    for num in range(latest - n + 1, latest + 1):
        b, err = rpc(url, "eth_getBlockByNumber", [hex(num), False])
        if err or not b:
            sys.exit(f"block {num}: {err or 'null result'}")
        blocks.append(b)
        time.sleep(0.05)  # be gentle with the public endpoint

    os.makedirs("data", exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = f"data/blocks_{label}_{latest}_{stamp}.json"
    with open(path, "w") as f:
        json.dump(blocks, f)

    print(json.dumps(analyze(blocks), indent=2))
    print("raw blocks saved to", path)


if __name__ == "__main__":
    main()
