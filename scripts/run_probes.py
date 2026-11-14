"""Step 3: differential EVM probes via eth_call / eth_estimateGas (free, read-only).

Usage:   python scripts/run_probes.py RPC_A LABEL_A RPC_B LABEL_B
Example (Rayls vs a local reference node):
         python scripts/run_probes.py "$RPC" rayls http://127.0.0.1:8545 anvil

How it works: an eth_call WITHOUT a "to" address executes the data as contract
creation code in a simulation. Whatever the code RETURNs comes back as the
response. No wallet, no gas balance, nothing is written on-chain.
"""
import csv
import datetime
import json
import os
import sys

from rpcutil import rpc

ERR = "__must_error__"          # sentinel: this probe is expected to fail
ZERO32 = "0x" + "00" * 32
WORD_2A = "0x" + "00" * 31 + "2a"


def create(code):
    return {"data": "0x" + code}


def call_to(n, data=""):
    return {"to": "0x" + format(n, "040x"), "data": "0x" + data}


def ret_op(op):
    # OP, PUSH1 0, MSTORE, PUSH1 0x20, PUSH1 0, RETURN -> returns the op's 32-byte value
    return op + "60005260206000f3"


PROBES = [
    # --- opcodes (known answers; validated on a reference EVM by tests/) ---
    {"name": "push0 (Shanghai)", "tx": create("5f60005260206000f3"), "expected": ZERO32},
    {"name": "blobhash(0) (Cancun)", "tx": create("60004960005260206000f3"), "expected": ZERO32},
    {"name": "tstore/tload (Cancun)", "tx": create("602a60005d60005c60005260206000f3"), "expected": WORD_2A},
    {"name": "mcopy (Cancun)", "tx": create("602a6000526020600060205e60206020f3"), "expected": WORD_2A},
    # --- chain-specific values: expected to differ between chains, just record them ---
    {"name": "chainid", "tx": create(ret_op("46")), "env": True},
    {"name": "basefee", "tx": create(ret_op("48")), "env": True},
    {"name": "prevrandao", "tx": create(ret_op("44")), "env": True},
    {"name": "gaslimit", "tx": create(ret_op("45")), "env": True},
    {"name": "timestamp", "tx": create(ret_op("42")), "env": True},
    {"name": "number", "tx": create(ret_op("43")), "env": True},
    {"name": "blobbasefee", "tx": create(ret_op("4a")), "env": True},
    # --- limits (differential only) ---
    {"name": "code size 24576 bytes (at limit)", "tx": create("6160006000f3")},
    {"name": "code size 24577 bytes (over limit)", "tx": create("6160016000f3")},
    # --- negative control: harness must see this fail on every endpoint ---
    {"name": "invalid opcode 0xfe (negative control)", "tx": create("fe"), "expected": ERR},
    # --- precompiles ---
    {"name": "0x01 ecrecover, empty input", "tx": call_to(1)},
    {"name": "0x02 sha256('')", "tx": call_to(2),
     "expected": "0xe3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    {"name": "0x03 ripemd160('')", "tx": call_to(3),
     "expected": "0x" + "00" * 12 + "9c1185a5c5e9fc54612808977ee8f548b2258d31"},
    {"name": "0x04 identity(0x1234)", "tx": call_to(4, "1234"), "expected": "0x1234"},
    {"name": "0x05 modexp 2^3 mod 5",
     "tx": call_to(5, "00" * 31 + "01" + "00" * 31 + "01" + "00" * 31 + "01" + "020305"),
     "expected": "0x03"},
    {"name": "0x06 bn256Add(0,0)", "tx": call_to(6, "00" * 128), "expected": "0x" + "00" * 64},
    {"name": "0x07 bn256Mul(0,0)", "tx": call_to(7, "00" * 96), "expected": "0x" + "00" * 64},
    {"name": "0x08 bn256Pairing(empty)", "tx": call_to(8), "expected": "0x" + "00" * 31 + "01"},
    {"name": "0x09 blake2f, short input (must error)", "tx": call_to(9, "00"), "expected": ERR},
    {"name": "0x0a point evaluation, short input (Cancun precompile; must error)",
     "tx": call_to(10, "00"), "expected": ERR},
    # --- gas schedule (differential only) ---
    {"name": "estimateGas: SSTORE(0,1) in create", "method": "eth_estimateGas", "tx": create("600160005500")},
    {"name": "estimateGas: bare STOP create", "method": "eth_estimateGas", "tx": create("00")},
    # --- Ethereum-upgrade level probes (differential only; which upgrades does Rayls track?) ---
    {"name": "initcode 49152 bytes (EIP-3860 limit, at limit)", "tx": create("00" * 49152)},
    {"name": "initcode 49153 bytes (EIP-3860 limit, over limit)", "tx": create("00" * 49153)},
    {"name": "CLZ opcode 0x1e (Osaka): CLZ(1)", "tx": create("60011e60005260206000f3")},
    {"name": "0x0b BLS12-381 G1ADD, short input (Prague)", "tx": call_to(0x0b, "00")},
    {"name": "0x0c BLS12-381 G1MSM, short input (Prague)", "tx": call_to(0x0c, "00")},
    {"name": "0x0d BLS12-381 G2ADD, short input (Prague)", "tx": call_to(0x0d, "00")},
    {"name": "0x0e BLS12-381 G2MSM, short input (Prague)", "tx": call_to(0x0e, "00")},
    {"name": "0x0f BLS12-381 PAIRING, short input (Prague)", "tx": call_to(0x0f, "00")},
    {"name": "0x10 BLS12-381 MAP_FP_TO_G1, short input (Prague)", "tx": call_to(0x10, "00")},
    {"name": "0x11 BLS12-381 MAP_FP2_TO_G2, short input (Prague)", "tx": call_to(0x11, "00")},
    {"name": "0x100 P256VERIFY, short input (Osaka)", "tx": call_to(0x100, "00")},
    # --- code present at well-known addresses? (eth_getCode; compare presence and bytecode) ---
    {"name": "code @ EIP-4788 beacon roots contract (Cancun)", "method": "eth_getCode", "tx": "0x000f3df6d732807ef1319fb7b8bb8522d0beac02"},
    {"name": "code @ EIP-2935 history storage (Prague)", "method": "eth_getCode", "tx": "0x0000f90827f1c53a10cb7a02335b175320002935"},
    {"name": "code @ EIP-7002 withdrawal requests (Prague)", "method": "eth_getCode", "tx": "0x00000961ef480eb55e80d19ad83579a64c007002"},
    {"name": "code @ EIP-7251 consolidation requests (Prague)", "method": "eth_getCode", "tx": "0x0000bbddc7ce488642fb579f8b00f3a590007251"},
    {"name": "code @ Multicall3", "method": "eth_getCode", "tx": "0xca11bde05977b3631167028862be2a173976ca11"},
    {"name": "code @ deterministic deployment proxy (Arachnid)", "method": "eth_getCode", "tx": "0x4e59b44847b379578588920ca78fbf26c0b4956c"},
    {"name": "code @ Safe singleton factory", "method": "eth_getCode", "tx": "0x914d7fec6aac8cd542e72bca78b30650d45643d7"},
    {"name": "code @ Permit2", "method": "eth_getCode", "tx": "0x000000000022d473030f116ddee9f6b43ac78ba3"},
    {"name": "code @ CreateX", "method": "eth_getCode", "tx": "0xba5ed099633d3b313e4d5f7bdc1305d3c28ba5ed"},
    {"name": "code @ 0x...0400 (USDr token address per Rayls explorer)", "method": "eth_getCode", "tx": "0x0000000000000000000000000000000000000400"},
]


def run_one(url, probe):
    method = probe.get("method", "eth_call")
    return rpc(url, method, [probe["tx"], "latest"])


def summarize(v, limit=140):
    if v is None:
        return ""
    v = str(v)
    return v if len(v) <= limit else f"{v[:70]}...(len={len(v)})"


def is_transport_error(err):
    """True when the endpoint could not be reached or answered with non-JSON.
    These are NOT EVM behaviour and must never count as a 'match'."""
    return bool(err) and (err.startswith("transport:") or err.startswith("http "))


def status(res, err, expected):
    """Check one endpoint against a known answer (empty string if none given)."""
    if expected is None:
        return ""
    if is_transport_error(err):
        return "UNREACHABLE"
    if expected == ERR:
        return "OK" if err else "UNEXPECTED_SUCCESS"
    if err:
        return "ERROR"
    return "OK" if res == expected else "WRONG"


def compare(a, b):
    """a, b are (result, error) tuples."""
    (ra, ea), (rb, eb) = a, b
    if is_transport_error(ea) or is_transport_error(eb):
        return "INCONCLUSIVE_transport"
    if ea and eb:
        return "both_error"
    if ea or eb:
        return "DIFF_error_vs_result"
    return "same" if ra == rb else "DIFF_result"


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    url_a, label_a, url_b, label_b = sys.argv[1:5]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs("data", exist_ok=True)

    # Preflight: refuse to run if either endpoint is unreachable.
    for label, url in ((label_a, url_a), (label_b, url_b)):
        _, err = rpc(url, "eth_chainId", timeout=10)
        if err:
            sys.exit(f"endpoint '{label}' is not usable ({err[:120]}); nothing was recorded")

    rows, raw = [], []
    for p in PROBES:
        a = run_one(url_a, p)
        b = run_one(url_b, p)
        env = bool(p.get("env"))
        cmp_ = "n/a (env-specific)" if env else compare(a, b)
        exp = p.get("expected")
        rows.append({
            "probe": p["name"],
            "method": p.get("method", "eth_call"),
            f"{label_a}_result": summarize(a[0]),
            f"{label_a}_error": summarize(a[1]),
            f"{label_a}_known_answer": status(a[0], a[1], exp),
            f"{label_b}_result": summarize(b[0]),
            f"{label_b}_error": summarize(b[1]),
            f"{label_b}_known_answer": status(b[0], b[1], exp),
            "compare": cmp_,
        })
        raw.append({"probe": p["name"],
                    label_a: {"result": a[0], "error": a[1]},
                    label_b: {"result": b[0], "error": b[1]}})
        print(f"{cmp_:24} {p['name']}")

    csv_path = f"data/probes_{label_a}_vs_{label_b}_{stamp}.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(csv_path.replace(".csv", ".json"), "w") as f:
        json.dump(raw, f, indent=2)

    comparable = [r for r in rows if not r["compare"].startswith("n/a")]
    good = [r for r in comparable if r["compare"] in ("same", "both_error")]
    print(f"\nMatching on {len(good)} of {len(comparable)} comparable probes "
          f"({len(rows) - len(comparable)} env-specific, recorded only)")
    print("saved", csv_path, "and the .json with full raw outputs")


if __name__ == "__main__":
    main()