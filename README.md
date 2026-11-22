# Can I deploy my Ethereum smart contract on Rayls without changes? An EVM-compatibility test

**Author:** Anzoro

**Captures:** 11 Nov 2026 and 14 Nov 2026 

**Everything here is read-only.** I did not deploy a contract or send a transaction.

---

## 1. Short answer

For the features I tested, Rayls showed identical outcomes to Ethereum on 20 of 40 comparable probes. Another 13 probes returned errors on both endpoints, while 7 produced different outcomes. The identical outcomes included tested Shanghai/Cancun opcodes, standard precompiles, contract-size limits and byte-identical standard deployer contracts. These results indicate compatibility across some tested features, not complete EVM compatibility. It differs on the CLZ opcode, the Ethereum system-contract addresses and Permit2. I did not deploy a contract, so I can’t confirm “without changes” end to end. Treat this as a checklist of what to verify first.

Rayls says its Public Chain is EVM-compatible. I tested that with a read-only harness: 47 probes through eth_call, eth_estimateGas and eth_getCode on the public Rayls mainnet RPC, run side by side against an Ethereum RPC as a reference, plus block scans, a block re-check and a gas-token check.

**What matched Ethereum (observed):**
- Opcodes from the Shanghai and Cancun upgrades (`PUSH0`, `TSTORE`/`TLOAD`, `MCOPY`, `BLOBHASH`), the precompiles at 0x01 to 0x0a (identical results, or rejected on both for short-input probes), The seven Prague BLS12-381 precompiles returned similar rejection responses to short-input probes on both chains; full functionality was not established., the 24,576-byte contract size limit, the 49,152-byte initcode limit, two gas estimates, and byte-identical code at four standard deployment-helper addresses (Multicall3, the CREATE2 deployer, the Safe singleton factory, CreateX).
- All 14 probes that have known Ethereum answers returned the expected result on Rayls.
- Of 40 comparable probes, 20 produced identical outcomes. Another 13 returned errors on both chains, while 7 produced different outcomes. Both-error cases are reported separately and are not counted as successful compatibility matches.

**What differed (observed):**
- The `CLZ` opcode (0x1e) was rejected on Rayls with `EVM error: NotActivated` while the Ethereum reference executed it.
- The Ethereum system-contract addresses for EIP-4788, EIP-2935, EIP-7002 and EIP-7251 returned empty bytecode through eth_getCode. The canonical Permit2 address also returned empty bytecode. These are address-level observations, not proof that the corresponding protocol functionality is absent.
- The USDr gas token address holds a single zero byte of code, yet token calls return values there. Native balance equals token balance for the address I sampled.

**Reading (interpretation):** the block header fields, the opcodes, the precompiles and the missing `CLZ` opcode together look like Ethereum's Prague-level rules without the later `CLZ` opcode. Section 7 and section 8 explain this and its limits.

**What I did not establish:** real deployment, full gas schedule equivalence, behaviour inside executed transactions, or anything beyond one endpoint on two capture dates. See section 9.

---

## 2. Claims being tested (these are claims, not measurements)

| Claim (paraphrased) | Source | Accessed |
|---|---|---|
| Full compatibility with Ethereum (EVM) | Rayls Public Chain launch press release, 1 May 2026 | 11 Nov 2026 |
| Gas is paid in a stablecoin | Same press release | 11 Nov 2026 |
| Ethereum-compatible EVM built on reth and alloy, serving standard Ethereum JSON-RPC | Axyl repository README | 11 Nov 2026 |

---

## 3. Method and scope

**Endpoints.**
- Rayls: `https://mainnet-rpc.rayls.com` (chain ID 72957, `0x11cfd`). One endpoint.
- Reference: `https://eth.drpc.org`, a third-party Ethereum RPC. One endpoint.

**How the probes work.** An `eth_call` with no `to` address runs the supplied bytecode as contract creation code in a simulation and returns whatever the code `RETURN`s. No wallet, no gas balance, nothing written on-chain. Precompiles are called directly. Well known contracts are checked with `eth_getCode`.

**Three kinds of check.**
1. **Known-answer probes** (14): the expected value comes from specified Ethereum behaviour (for example, SHA-256 of the empty string).
2. **Differential probes**: the same call is sent to both chains and the results are compared. "Rejected on both" means both returned an error; I did **not** compare error text.
3. **Recorded-only probes** (7): values that legitimately differ per chain (chain ID, block number, and so on).

**Controls.** An invalid opcode (`0xfe`) must fail everywhere (negative control). During development, the hand-assembled probe bytecode and expected answers were checked in an independent Python EVM (py-evm, Cancun rules); the `BLOBHASH` probe could not be run there, so it is corroborated only by the Ethereum comparison. An early version of the harness counted an unreachable endpoint as a match; this was fixed (a preflight check, and an `INCONCLUSIVE_transport` label that never counts as a match).

**Block-state consistency and reproducibility.**

The recorded captures contain observations from specific execution times. Unless a request explicitly records and uses a fixed block identifier, its result should not be interpreted as block-pinned. The current comparison is therefore a point-in-time RPC observation rather than a fully block-pinned differential test. A future capture should record the block number and block hash and use a fixed block reference for state-dependent methods wherever supported.

**Captures.**

| Capture (UTC) | What |
|---|---|
| 11 Nov 2026, 12:40 | JSON-RPC method probe |
| 11 Nov 2026, 12:41 | First probe run (Rayls queried twice, no reference; only the known-answer columns are meaningful) |
| 11 Nov 2026, 12:43 | Block scan #1: blocks 14,284,275 to 14,284,474 |
| 11 Nov 2026, 12:48 | 26 probes, Rayls vs Ethereum |
| 14 Nov 2026, 06:29 | 47 probes, Rayls vs Ethereum |
| 14 Nov 2026, 06:32 | USDr and fee check |
| 14 Nov 2026, 06:35 | Block scan #2: blocks 14,460,958 to 14,461,157 |
| 14 Nov 2026, 06:36 | Re-check of scan #1 blocks |

---

## 4. Results: behaviour probes

### 4.1 Core probes (26 probes; identical outcomes on 11 Nov and again on 14 Nov)

| Area | Probes | Result (observed) |
|---|---|---|
| Newer opcodes | `PUSH0` (Shanghai); `BLOBHASH(0)`, `TSTORE`/`TLOAD`, `MCOPY` (Cancun) | Identical to Ethereum |
| Precompiles | 0x01 ecrecover (empty input), 0x02 sha256, 0x03 ripemd160, 0x04 identity, 0x05 modexp, 0x06-0x08 bn256 add/mul/pairing | Identical to Ethereum; known answers correct |
| Rejections | 0x09 blake2f and 0x0a point-evaluation with short input; invalid opcode 0xfe; 24,577-byte contract | Rejected on both. Rayls error names: `PrecompileError`, `InvalidFEOpcode`, `CreateContractSizeLimit` |
| Size limit | 24,576-byte contract | Accepted on both |
| Gas estimates | `eth_estimateGas` for an SSTORE create and a bare STOP create | Identical on both |

Of the 19 comparable probes in this set, 15 returned identical outcomes and 4 were rejected on both chains. Rejected on both cases are not counted as successful compatibility matches.

### 4.2 Upgrade-level probes (added on 14 Nov)

| Probe | Rayls | Ethereum reference | Reading |
|---|---|---|---|
| Initcode 49,152 bytes (EIP-3860 limit) | accepted | accepted | same |
| Initcode 49,153 bytes | rejected | rejected | same |
| `CLZ` opcode 0x1e, `CLZ(1)` | **rejected: `EVM error: NotActivated`** | executed, returned a 32-byte result | **differs** |
| BLS12-381 precompiles 0x0b to 0x11 (7 probes), short input | rejected | rejected | Same rejection behaviour; full functionality not established |
| 0x100 `P256VERIFY`, short input | same result | same result | **inconclusive** (see note) |

Notes:
- For the BLS probes, a chain without the precompile would normally return an empty success for a call to an empty address, so "rejected on both" suggests the precompiles exist on both. This is my reading of the behaviour.
- `P256VERIFY` is inconclusive: invalid input returns empty on a chain that has the precompile and also on a chain that lacks it, so this probe cannot tell them apart. I make no claim from it.
- `CLZ` is the one opcode in this set where Rayls and the Ethereum reference disagree. The full raw outputs are in `data/probes_rayls_vs_eth_20261114T062908Z.json`.

### 4.3 Code at well-known addresses (14 Nov, `eth_getCode`)

| Address (what it is) | Rayls | Ethereum reference | Reading |
|---|---|---|---|
| EIP-4788 beacon roots contract | no code (0 bytes) | 97 bytes | differs |
| EIP-2935 history storage contract | no code (0 bytes) | 83 bytes | differs |
| EIP-7002 withdrawal requests contract | no code (0 bytes) | 504 bytes | differs |
| EIP-7251 consolidation requests contract | no code (0 bytes) | 414 bytes | differs |
| Permit2 (canonical address) | no code (0 bytes) | 9,152 bytes | differs |
| Multicall3 | 3,808 bytes | 3,808 bytes | identical code on both |
| Deterministic deployment proxy (CREATE2 deployer) | 69 bytes | 69 bytes | identical code on both |
| Safe singleton factory | 69 bytes | 69 bytes | identical code on both |
| CreateX | 11,838 bytes | 11,838 bytes | identical code on both |
| `0x…0400` (USDr token address per the Rayls explorer) | **1 byte: `0x00`** | no code | differs |

For the four "identical code" rows, the returned code strings were equal on both chains, and the byte counts show it is real code on both (not both empty). The USDr row compares a Rayls stub against an address with no code on the Ethereum reference.

### 4.4 Chain-specific values (recorded only; captured 11 Nov, about 12:49 UTC)

| Value (via `eth_call`) | Rayls | Ethereum reference |
|---|---|---|
| Chain ID | 72,957 | 1 |
| Block gas limit | 500,000,000 | 59,999,943 |
| `BASEFEE` opcode | 0 | 0 |
| `BLOBBASEFEE` opcode | 1 | 4,207,587 |
| Block number | 14,284,785 | 26,391,785 |
| Block timestamp | 2026-11-11 12:49:10 UTC | 2026-11-11 12:48:59 UTC |
| `PREVRANDAO` | non-zero 32-byte value (different values on two runs minutes apart) | non-zero 32-byte value |

---

## 5. Results: USDr, gas and fees (14 Nov, about 06:32 UTC)

For one recent transaction picked automatically from the latest blocks (hash `0x338d10c8…2892f`), and its sender (`0x339d…0749`):

| Check | Result (observed) |
|---|---|
| `eth_getBalance` (native) | 20,892,999,238,023,189,792 smallest units |
| USDr token `balanceOf` (same address) | 20,892,999,238,023,189,792, **equal to the native balance** |
| Token metadata | name "USD Rayls", symbol "USDr", decimals 18 |
| Token `totalSupply` | 25,342,245,494,933,504,401,529 (about 25,342.2455 USDr) |
| Code at the token address | 1 byte (`0x00`) |
| Transaction | status success, type 0 (legacy), gas used 43,128, gas limit 220,976 |
| Effective gas price | 69,120,000,000 (69.12 "Gwei") |
| Fee computed from RPC (gas used × price) | 2,981,007,360,000,000 smallest units = 0.00298100736 at 18 decimals |
| Fee shown by the explorer | 0.00298100736 USDr, gas price shown as 0.00000006912 USDr (69.12 Gwei) |

**Reconciliation:** the fee computed from RPC data matches the explorer's displayed fee exactly, and the explorer labels the unit USDr. [Explorer link for the transaction](https://explorer.rayls.com/tx/0x338d10c8f6ea1c62d54ea01c3ddba5d440269b4b196641c3e9add1849be2892f).

Other observations:
- This transaction's gas price is exactly 1.44 times the header base fee seen in the block scans (69.12 vs 48 "Gwei"). It is a type-0 transaction, so the sender chose the gas price. I record the ratio without explaining it.
- Only one address and one transaction were sampled.

---

## 6. Results: block production and stability

| | Scan #1 (11 Nov, 12:43 UTC) | Scan #2 (14 Nov, 06:35 UTC) |
|---|---|---|
| Blocks | 14,284,275 to 14,284,474 | 14,460,958 to 14,461,157 |
| Timestamp gaps (1 s / 2 s / 0 s) | 129 / 69 / 1 | 128 / 71 / 0 |
| Average block time in window | 1.34 s | 1.36 s |
| Backward timestamps | 0 | 0 |
| Distinct gas limits | 1 | 1 |
| Header `baseFeePerGas` | 48,000,000,000 in all 200 blocks | 48,000,000,000 in all 200 blocks |
| Distinct `mixHash` values | 200 | 200 |
| Distinct block-producer addresses | 7 | 7 |
| Header `difficulty` | `0x0` on 199 blocks, `0x10000` on 1 (block 14,284,439) | `0x0` on all 200 |
| Max transactions in one block | 4 | 4 |

- **Block stability.** On 14 Nov at 06:36 UTC (about 66 hours after scan #1) I re-fetched all 200 blocks from scan #1 and compared hash, parent hash, timestamp, miner, state/transactions/receipts roots, gas used and mix hash. **All 200 were identical; 0 changed, 0 request errors.** This covers those 200 blocks only.
- **Block rate over the long run.** Between the last blocks of the two scans there are 176,683 blocks over about 237,100 seconds, which is about 1.34 s per block, consistent with the short windows.
- **Head progression.** An eight-sample poll of `eth_blockNumber` (2 s apart) rose from 14,285,072 to 14,285,083 with no backward jumps.
- In scan #1, one pair of consecutive blocks shared the same timestamp; scan #2 had none. Whole-second timestamps with blocks about 1.34 s apart make equal consecutive timestamps possible.

---

## 7. JSON-RPC method support and header format (11 Nov)

Captured 11 Nov 2026, 12:40 UTC, from `data/rpc_probe_rayls_20261111T124059Z.json`.

| Method | Result (observed) |
|---|---|
| `web3_clientVersion`, `net_version`, `eth_chainId`, `eth_blockNumber` | returned a result |
| `eth_gasPrice`, `eth_maxPriorityFeePerGas`, `eth_feeHistory`, `eth_blobBaseFee` | returned a result |
| `eth_syncing`, `eth_getBlockReceipts`, `eth_getProof` | returned a result |
| `debug_traceCall`, `trace_block`, `txpool_status` | `Method not found` |

Latest-block header fields, and the Ethereum upgrade each one is associated with:

| Header field | Present on Rayls |
|---|---|
| `baseFeePerGas` (London) | yes |
| `withdrawalsRoot` (Shanghai) | yes |
| `blobGasUsed`, `excessBlobGas`, `parentBeaconBlockRoot` (Cancun) | yes |
| `requestsHash` (Prague) | yes |

Node version string (observed): `web3_clientVersion` returned `1.4.3 (a8c0d0e9cf5493743052b1d267c295fd2a9866ea)`, i.e. a version number plus a 40-character git commit hash. It does not state the client's name. I have not matched that commit to any public repository, so the string neither confirms nor contradicts the Axyl README's description of a reth-based node (interpretation: it is consistent with a custom build that reports its own version).

Notes:
- These header fields describe the header **format**. They do not prove that the matching opcodes work; section 4 tests that separately.
- A public endpoint disabling `debug_*`, `trace_*` and `txpool_*` methods is common, so "Method not found" says what this endpoint exposes, not what the node software can do.
- Reading (interpretation): the Prague-style header fields, the Cancun opcodes, the BLS12-381 precompiles and the missing `CLZ` opcode are together consistent with a rule set at Ethereum's Prague level, without the later opcode. I did not test other Prague features, such as EIP-7702 transaction types.

---

## 8. What this means for a developer (interpretation, labelled as such)

These are my readings of the observations above, not verified facts.

- **Likely to work as on Ethereum:** contracts that use the tested Shanghai/Cancun opcodes, tested standard precompiles, standard contract and initcode size limits, subject to the scope of these probes. Standard deployment helpers (Multicall3, the CREATE2 deployer, the Safe singleton factory, CreateX) are present at their usual addresses with identical bytecode, so tooling that relies on them can probably find them.
- **BLS12-381 precompiles:** Both chains rejected the short-input probes, suggesting similar handling, but full functionality with valid inputs was not established.
- **Check before relying on:** contracts or libraries that use the `CLZ` opcode or expect Permit2 at its canonical address. The `CLZ` probe was rejected on Rayls, while Permit2 had no code at its canonical address during the capture.
- **System-contract addresses:** The canonical Ethereum addresses for EIP-4788, EIP-2935, EIP-7002 and EIP-7251 returned empty bytecode through `eth_getCode`. This establishes an address-level difference, but does not independently establish whether equivalent protocol-level functionality exists internally on Rayls. Compatibility for these features remains unresolved pending direct behavioral tests.
- **Gas token:** USDr is identified by the Rayls explorer as the gas currency and ERC-20-style token at a system address. During the capture, that address returned one byte of code (`0x00`), while calls to `name`, `symbol`, `decimals`, `totalSupply` and `balanceOf` returned values. This suggests special handling by the node or protocol, but the exact implementation mechanism was not established. The native-balance and token-balance equality was observed for only one sampled address.
- **Timing:** blocks about every 1.34 s with whole-second timestamps; contracts that assume the timestamp increases every block may see equal timestamps occasionally.
- **Scale numbers:** the block gas limit (500,000,000 at capture) is about 8 times the reference chain's at the time, which is relevant for tools that assume Ethereum's limit.

Other interpretations:
- Rayls error names (`NotActivated`, `CreateContractSizeLimit`, `InvalidFEOpcode`, `PrecompileError`) look like those of the Rust EVM library revm, consistent with the README's reth description.
- `BASEFEE` returned 0 on both chains in simulation; this is probably normal `eth_call` behaviour where base-fee checks are relaxed. I did not test `BASEFEE` inside an executed transaction.
- The absence of the EIP-4788/2935/7002/7251 contracts may reflect that Rayls does not run an Ethereum beacon chain.

---

## 9. What I cannot explain, and what this does not establish

**Observations I cannot explain**
- The header base fee was exactly 48,000,000,000 in all 400 scanned blocks across two windows three days apart. I do not know whether it is a fixed parameter, a floor, or something else.
- One block (14,284,439: 1 transaction, producer `0xeecf1a05…aa78bc`) had header difficulty `0x10000` (65,536) among 399 blocks with `0x0`.
- The sampled transaction's gas price is exactly 1.44× the header base fee.

**Not established**
- No contract was deployed and no transaction was executed, so end-to-end deployability is untested.
- `eth_call` is a simulation and can differ from execution inside a block.
- One Rayls endpoint and one Ethereum endpoint, on two dates. A second independent Rayls endpoint was not tested.
- 47 probes cover a small part of the EVM. Gas equivalence is shown only for two payloads.
- `P256VERIFY` support is untested (the probe is inconclusive).
- Other Prague features, such as EIP-7702 transaction types, were not tested.
- The identity of the node software is not confirmed: the version string above does not name the client, and its commit hash was not matched to a public repository.
- Native-equals-token balance and the fee match are for one address and one transaction.
- The press-release claim of "full EVM compatibility" is not fully tested by this work.
- Nothing here measures throughput, security or consensus behaviour.

---

## 10. Reproduce it

Windows PowerShell, Python 3, from the repository folder:

```powershell
pip install requests
$env:RPC = "https://mainnet-rpc.rayls.com"
python scripts\probe_rpc.py $env:RPC rayls
python scripts\run_probes.py $env:RPC rayls https://eth.drpc.org eth
python scripts\scan_blocks.py $env:RPC rayls 200
python scripts\usdr_check.py $env:RPC rayls
$f = (Get-ChildItem data\blocks_rayls_*.json | Sort-Object Name | Select-Object -First 1).FullName
python scripts\recheck_blocks.py $f $env:RPC rayls_recheck
```

Live values (block numbers, timestamps, balances, supply) will differ on a rerun, and the Ethereum reference will have moved on. My raw captures are in `data/`, so the analysis can be checked without the live chain. Python version used: 3.10.2.

## 11. Data files

- `data/probes_rayls_vs_eth_20261111T124848Z.csv` / `.json`: 26 probes, 11 Nov
- `data/probes_rayls_vs_eth_20261114T062908Z.csv` / `.json`: 47 probes, 14 Nov
- `data/probes_rayls_vs_rayls2_20261111T124139Z.csv` / `.json`: first run, Rayls queried twice (ignore the compare column)
- `data/blocks_rayls_14284474_20261111T124319Z.json`: block scan #1
- `data/blocks_rayls_14461157_20261114T063501Z.json`: block scan #2
- `data/recheck_rayls_recheck_20261114T063637Z.json`: re-check of scan #1
- `data/usdr_check_rayls_20261114T063219Z.json`: USDr and fee check
- `data/rpc_probe_rayls_20261111T124059Z.json`: JSON-RPC method probe

## 12. Sources

- Rayls launch press release (GlobeNewswire, 1 May 2026): https://www.globenewswire.com/news-release/2026/05/01/3286052/0/en/Rayls-Launches-Public-Chain-Advancing-its-Mission-to-Bring-Global-Finance-Onchain.html
- Axyl repository: https://github.com/raylsnetwork/axyl
- Rayls RPC: https://mainnet-rpc.rayls.com
- Rayls explorer: https://explorer.rayls.com
- Ethereum reference RPC: https://eth.drpc.org
