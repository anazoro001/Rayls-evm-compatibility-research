"""Re-fetch blocks saved by scan_blocks.py and compare them with what an endpoint returns NOW.

Usage:   python scripts/recheck_blocks.py SAVED_BLOCKS.json RPC_URL LABEL
Examples:
  # (a) same endpoint, a day later: did any recorded block change?
  python scripts/recheck_blocks.py data/blocks_rayls_14284474_<stamp>.json "$RPC" rayls_day2
  # (b) a SECOND endpoint: do two endpoints agree on the same heights?
  python scripts/recheck_blocks.py data/blocks_rayls_14284474_<stamp>.json "<second rpc url>" rayls_ep2

Writes data/recheck_<LABEL>_<UTC time>.json. The URL itself is not saved.
"""
import datetime
import json
import os
import sys
import time

from rpcutil import rpc

FIELDS = ["hash", "parentHash", "timestamp", "miner", "stateRoot",
          "transactionsRoot", "receiptsRoot", "gasUsed", "mixHash"]


def diff_block(old, new):
    """Return the list of FIELDS whose values differ (empty list = identical)."""
    if new is None:
        return ["MISSING"]
    return [f for f in FIELDS if old.get(f) != new.get(f)]


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    saved_path, url, label = sys.argv[1:4]
    saved = json.load(open(saved_path))

    changed, errors = {}, {}
    identical = 0
    for old in saved:
        num = old["number"]
        new, err = rpc(url, "eth_getBlockByNumber", [num, False])
        if err:
            errors[int(num, 16)] = err[:100]
            continue
        d = diff_block(old, new)
        if d:
            changed[int(num, 16)] = d
        else:
            identical += 1
        time.sleep(0.05)  # gentle

    now = datetime.datetime.now(datetime.timezone.utc)
    report = {
        "label": label,
        "saved_file": os.path.basename(saved_path),
        "checked_utc": now.isoformat(),
        "blocks_in_saved_file": len(saved),
        "first_block": int(saved[0]["number"], 16),
        "last_block": int(saved[-1]["number"], 16),
        "identical": identical,
        "changed": len(changed),
        "request_errors": len(errors),
        "changed_blocks": changed,
        "errors": errors,
    }
    os.makedirs("data", exist_ok=True)
    path = f"data/recheck_{label}_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"checked {len(saved)} blocks: identical={identical} changed={len(changed)} errors={len(errors)}")
    for n, d in list(changed.items())[:10]:
        print("  changed block", n, "fields:", d)
    print("saved", path)


if __name__ == "__main__":
    main()