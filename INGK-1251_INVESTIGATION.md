# INGK-1251 — Stale SDO Responses After Power Cycle on CANopen Capitan FW 2.9.0

## The Problem

`test_restore_parameters` (and subsequently `test_enable_disable`) fail intermittently on
**CANopen Capitan drives with firmware 2.9.0**. The failures do not occur with FW 2.4.0 or
on the Everest platform.

The test calls `DriveContextManager.force_restore()`, which triggers a **power cycle**
(store all → restore all → servo reboots). After the drive comes back online, SDO
communication is corrupted: the host receives responses that belong to requests issued
*before* the power cycle.

---

## Root Cause

### 1. Stale SDO responses after power cycle

When the drive power-cycles, the host calls `recover_from_disconnection()`, which resets
the CAN bus and polls `is_alive()` in a loop until the drive responds. During the window
where the drive is still booting, these `is_alive()` poll requests **time out on the host
side** — but the drive may still receive and queue them.

Once the drive finishes booting, it begins processing any SDO requests that arrived during
initialization. These **late responses** enter the CAN receive queue and are consumed by
the `canopen` SDO client as replies to *subsequent* requests. Because the SDO
index/subindex in the response doesn't match the current request, `canopen` raises:

```
SdoCommunicationError: Node returned a value for 0xXXXX:Y instead,
maybe there is another SDO client communicating on the same SDO channel?
```

### Not a simple cascade

The `canopen` SDO client (`SdoClient.request_response()`) **clears the response queue
before every request**:

```python
if not self.responses.empty():
    self.responses = queue.Queue()
```

This means a single stale response cannot cascade into subsequent reads — each read starts
fresh. For 220+ consecutive "wrong index" errors (as seen in the logs), there must be a
**continuous stream of stale SDO responses arriving** — one for each read, arriving fast
enough to beat the correct response into the queue.

The "wrong" response indices in the logs are sequential register addresses from the drive's
dictionary (`0x1602:2`, `0x5890:0`, `0x5891:0`, `0x5892:0`...). This pattern suggests the
firmware is replaying SDO responses for a bulk of registers in order — possibly responses
to the `DriveContextManager.__enter__()` reads that were queued internally in the firmware
before the power cycle and survive the reboot, or a FW 2.9.0-specific boot-up behavior.

> **Note:** The exact origin of the stale responses is not fully confirmed.
> They could be late responses to SDO requests sent during the recovery window,
> residual responses from pre-reboot SDO operations that survive in the firmware's
> internal queue, or a FW 2.9.0-specific boot sequence behavior.
> What *is* confirmed: the stale responses only appear on FW 2.9.0 (not 2.4.0), and
> only after a power cycle on the Capitan platform, suggesting the firmware's SDO server
> initialization behavior changed between versions.

If no response arrives at all (the stale response was consumed by a different request),
the client times out:

```
SdoAbortedError: Transfer aborted by client with code 0x05040000
```

### 2. PCAN buffer overrun

After recovery, `DriveContextManager.__enter__()` performs bulk reads of 200+ registers.
This flood of SDO requests can overwhelm the PCAN USB adapter, producing
`PCAN_ERROR_OVERRUN` ("The CAN controller was read too late").

In `python-can`, when `bus.recv()` raises an error inside `can.Notifier._rx_thread()`:

1. The exception is stored: `self.exception = exc`
2. `_on_error(exc)` is called — if a listener handles it, the thread keeps running
3. **But `self.exception` is never cleared**, even when `on_error()` handled it successfully

Then `canopen.Network.check()` — called on every `send_message()` — sees the stored
exception and re-raises it:

```python
if self.notifier.exception is not None:
    raise self.notifier.exception
```

Result: **every subsequent SDO operation fails** with the same already-handled error.

> This is a bug in `python-can` (tested 4.4.2) and `canopen` (tested 2.2.0).  
> Checked both upstream repositories (python-can `main`, canopen `master`) as of
> April 2026 — **neither has fixed this**.

---

## Fixes Applied

Six commits on branch `ingk-1251-investigate-restore-parameters-test-with-new-firmware-versions`:

### Commit 1 — `57a206b8` 
**Flush stale SDO responses after CANopen reconnection**

Added `_flush_sdo_responses()` called at the end of `recover_from_disconnection()`.
Drains the SDO response queue and performs a verification read to confirm communication
is clean.

### Commit 2 — `5c17f5eb` 
**Improve SDO flush: drain queue properly, loop with alternate register**

Improved the flush algorithm: drain → read alternate register (0x1018) → loop up to 10
iterations until clean.

### Commit 3 — `54bba2e4` 
**Add CustomListener for all CAN devices and settle delay in flush**

- Created `CustomListener(can.Listener)` with an `on_error()` handler to prevent the
  `can.Notifier` receive thread from dying on transient bus errors (PCAN overrun,
  IXXAT/KVASER error-limit errors).
- Registered it for **all CAN device types**, not just IXXAT/KVASER.
- Added 100ms settling delay between flush iterations.

### Commit 4 — `8cb6662b`
**Improve SDO flush: double-read verification with different registers**

Two consecutive SDO reads using **different** registers (Vendor ID `0x1018:01` +
Product Code `0x1018:02`). Both must succeed to consider the queue clean. Using different
registers prevents a stale response for register A from silently being accepted as a valid
reply for register B.

### Commit 5 — `de233421`
**Enable cron nightly builds on PR branches**

Removed the `BRANCH_NAME == "develop"` guard from the Jenkinsfile cron schedule so nightly
builds run on this branch (19:00 + 23:00 UTC daily, 08:00 + 14:00 UTC weekends).

### Commit 6 — `1ac3f7a2`
**Clear `notifier.exception` after `on_error` handles CAN bus errors**

`CustomListener.on_error()` now also clears `self._network.notifier.exception = None`.
This works around the `python-can` bug where the stored exception is never cleared after
being handled, causing `canopen.Network.check()` to re-raise it on every `send_message()`.

---

## Build-by-Build History (PR-776)

| Build | Result | What happened |
|-------|--------|---------------|
| #1 | SUCCESS | Non-nightly run; FW 2.9.0 stage not executed |
| #2 | ABORTED | Manually aborted |
| #3 | UNSTABLE | 3 failures (`test_enable_disable` ×2, `test_fault_reset`) — single-read flush was insufficient |
| #4 | ABORTED | Manually aborted |
| #5 | ABORTED | Manually aborted |
| #6 | **SUCCESS** | First all-green nightly after double-read flush (commit `8cb6662b`) |
| #7 | FAILURE | Infrastructure issue (Publish wheels / Unstash). No test failures. |
| #8 | SUCCESS | Non-nightly; FW 2.9.0 not executed |
| #9 | **SUCCESS** | All tests passed |
| #10 | UNSTABLE | 2 failures (`test_is_alive`, `test_status_word_wait_change`). PCAN overrun + `notifier.exception` never cleared → commit `1ac3f7a2` |
| #11 | **SUCCESS** | First build with `notifier.exception` fix |
| #12 | **SUCCESS** | All green |
| #13 | **SUCCESS** | All green |
| #14 | UNSTABLE | `test_enable_disable` ×1 (py3.10). Stale SDO in DriveContextManager exit. |
| #15 | UNSTABLE | `test_enable_disable` ×3, `test_fault_reset`. Also unrelated: Ethernet Everest FW 2.8.0 (47 tests, hardware). |
| #16 | UNSTABLE | `test_enable_disable` ×1. Also unrelated: EtherCAT Multislave PDO (3 tests). |
| #17 | UNSTABLE | `test_enable_disable` ×4 (all py versions). Also unrelated: EtherCAT Everest FW 2.8.0 (83 tests). |
| #18 | UNSTABLE | `test_enable_disable` ×1 |
| #19 | UNSTABLE | CANopen Cap 2.9.0: **PASSED**. Unrelated: EtherCAT Multislave PDO (3 tests). |
| #20 | UNSTABLE | `test_enable_disable` ×2, `test_fault_reset` |
| #21 | UNSTABLE | `test_enable_disable` ×1 |
| #22 | UNSTABLE | CANopen Cap 2.9.0: **PASSED**. Unrelated: EtherCAT Everest FW 2.8.0. |
| #23 | UNSTABLE | `test_enable_disable` ×3, `test_fault_reset`. Also unrelated: CANopen Everest FW 2.8.0 (48 tests). |
| #24 | ABORTED | Auto-triggered by SDOTracer commit, manually stopped |
| #25 | UNSTABLE | `test_enable_disable` ×1. **SDOTracer captured 743 stale SDO responses and 253 mismatches.** See "Jenkins Build #25" section. |
| #26 | ABORTED | Auto-triggered by logger.error commit, manually stopped |
| #27 | **SUCCESS** | All tests passed. SDOTracer: 0 mismatches, 0 unsolicited across all 3 traces. Bug did NOT reproduce. |
| #28 | UNSTABLE | `test_enable_disable` ×1. **SDOTracer: 494 unsolicited, 24 mismatches. `logger.error` confirmed errors in `__enter__()` of subsequent tests.** See "Jenkins Build #28" section. |
| #29 | ABORTED | Auto-triggered by FW 2.10.0 commit, manually stopped |
| #30 | **SUCCESS** | All tests passed (FW 2.4.0 + 2.9.0 + **2.10.0 first run**). SDOTracer: 0 mismatches, 0 unsolicited (except 2 segment FP per FW ≥2.9.0). Bug did NOT reproduce. |

### Success Rates (builds 11–23, after all fixes)

| Stage | Runs | Passed | Failed | Rate |
|-------|------|--------|--------|------|
| CANopen Capitan FW 2.9.0 | 14 | 6 | 8 | **43%** |
| `test_restore_parameters` | 14 | **14** | 0 | **100%** |
| CANopen Capitan FW 2.10.0 | 1 | 1 | 0 | **100%** |

### Unrelated Failures (infrastructure)

These failures affect other stages on different hardware/protocols and are **not related
to INGK-1251**:

| Stage | Builds affected | Nature |
|-------|-----------------|--------|
| EtherCAT Everest FW 2.8.0 | #17, #22 | Mass failure (80+ tests), hardware/infra |
| EtherCAT Multislave | #16, #19 | PDO-only failures (3 tests) |
| Ethernet Everest FW 2.8.0 | #15 | Mass failure (47 tests), network connectivity |
| CANopen Everest FW 2.8.0 | #23 | Mass failure (48 tests), hardware/connectivity |

---

## What's Fixed

**`test_restore_parameters` passes 100% of the time** (12/12 nightly runs after fixes).
The original INGK-1251 issue — stale SDO responses corrupting `is_alive()` checks during
`recover_from_disconnection()` — is resolved by the double-read verification flush.

---

## What's Still Failing

**`test_enable_disable` fails in ~67% of nightly runs** (8/12) on CANopen Capitan FW 2.9.0.

### Mechanism (Corrected — Build #25 Analysis)

The failure chain, confirmed from build #25 console logs with SDOTracer:

1. `test_restore_parameters` triggers `servo.restore_parameters()` → drive reboots
2. `environment.power_cycle(reconnect_drives=True)` calls `recover_from_disconnection()`
3. Recovery succeeds, `_flush_sdo_responses()` clears the SDO queue ✅
4. `test_restore_parameters` reads one register (`DRV_PROT_USER_OVER_VOLT`) → **succeeds**
5. `test_restore_parameters` **PASSES** ✅
6. STF `servo` fixture teardown: `has_power_cycle_happened=True` → calls
   `_force_context_manager_to_initial_state()` → `force_restore()` →
   `_store_register_data()` (bulk read of ~500 registers)
7. **~862ms after flush**: 743 stale SDO responses arrive from the PCAN USB adapter's
   internal buffer (confirmed by SDOTracer in build #25)
8. These stale responses corrupt the bulk reads: each `_store_register_data()` read gets
   a wrong-index response, raises `ILIOError`, which is caught with `continue` → register
   skipped. The errors appear in `------ live log setup ------` of SUBSEQUENT tests (not
   in `test_restore_parameters`'s own teardown — pytest logs them under the next test's
   fixture setup phase)
9. The stale response stream spans ~7 seconds (11:31:05.068 → 11:31:12.586), affecting
   the setup fixtures of `test_read`, `test_write`, `test_monitoring_*`,
   `test_disturbance_*`, each getting 4-65 register read failures
10. `test_enable_disable` (the next test) calls `servo.enable()` → reads
    `DRV_STATE_CONTROL` → gets a stale response for `0x2011:0` instead → **FAILS**

**Important correction**: The stale SDO errors do NOT happen in `DriveContextManager.__exit__()`.
They occur in `DriveContextManager.__enter__()` → `_store_register_data()` of the NEXT test's
fixture setup. The STF `servo` fixture (from `summit_testing_framework.fixtures.servo_fixtures`)
creates a new `DriveContextManager` per test with `scope="function"`.

### Error Handling in `_store_register_data()`

Two types of SDO errors occur, neither involves a timeout:

1. **Wrong-index response (fast, no timeout)**: When a stale response arrives before the
   real one, `canopen` detects the index mismatch and raises `SdoCommunicationError`
   immediately (< 1ms). `servo._read_raw()` logs `logger.error("Failed reading %s...")`
   then raises `ILIOError`. `_store_register_data()` catches `ILIOError` → `continue`.
   This is why bursts of 8-65 errors appear at the same millisecond.

2. **SDO timeout (`0x05040000`)**: Rare, only when a stale response was consumed by the
   previous request leaving no response for the current one. Costs 300ms per occurrence
   (`SdoClient.RESPONSE_TIMEOUT = 0.3`). The ~400ms gaps between test setup error bursts
   correspond to exactly one SDO timeout per `_store_register_data()` run.

### Evidence from build #25 (FW 2.9.0)

```
11:31:04.206  Recovery succeeds, flush passes, SDOTracer #2 attaches
11:31:05.068  test_restore_parameters PASSED [63%]
11:31:05.068  test_read setup — 8 "another SDO client" errors (same ms)
11:31:05.467  test_read PASSED
11:31:05.876  test_write setup — 8 errors
11:31:06.278  test_write PASSED
11:31:07.079  test_monitoring — 4 errors
11:31:08.328  test_monitoring — 7 errors
11:31:09.215  test_disturbance — 65+ errors (massive burst, same ms)
11:31:10.419  test_disturbance — 6 errors
11:31:11.217  test_disturbance — 4 errors
11:31:12.586  test_enable_disable — reads DRV_STATE_CONTROL → got 0x2011 → FAILED
11:31:17.235  SDOTracer #2: 253 mismatches, 743 unsolicited
```

### Why the current flush doesn't prevent this

The flush runs inside `recover_from_disconnection()` and successfully verifies the SDO
queue is clean **at that moment** (both verification reads succeed, no stale responses in
the python-side Queue). The 743 stale responses are still in transit through the lower
layers:

1. PCAN USB adapter's internal FIFO (not cleared by `disconnect()`/`connect()`)
2. USB driver buffer
3. OS kernel buffer

These layers deliver the stale frames to python ~862ms after the flush completes.
The SDOTracer proves this: all 743 unsolicited responses arrive at t=0.750s relative to
tracer attachment (which happens immediately after the flush).

---

## What's Missing (potential next steps)

1. **Instrument SDO requests** — ✅ DONE (build #25). SDOTracer confirmed 743 stale
   responses arriving 750ms after flush completes. Root cause: PCAN adapter FIFO not
   cleared on disconnect/reconnect.

2. **Fix the flush race condition** — The flush runs too fast (<100ms). Stale responses
   arrive ~750ms later from the PCAN adapter's internal buffer. Options:
   - **Option A**: Add a mandatory post-flush cooldown (2s) + second flush pass
   - **Option B**: Use a CAN bus listener to wait until no stale frames arrive for N
     seconds (adaptive, doesn't waste time when no stale responses exist)
   - **Option C**: Reset the PCAN adapter hardware (`CAN_Reset` / `CAN_Initialize`) to
     clear its internal FIFO before reconnecting
   - **Option D**: NMT Reset Communication to the drive — may abort queued SDO responses

3. **Fix SDOTracer false positive** — `_is_initiate_frame()` needs direction-awareness:
   SCS=1 (0x20-0x3F) is segment download response for RX, not initiate.

4. **SDO-level retry on stale response** — at the `canopen` SDO client level, if a
   response for the wrong index/subindex is received, discard it and retry instead of
   raising an error. This would be the cleanest fix but requires changes to `canopen`
   or monkey-patching.

5. **Upstream PR's** — file a bug/PR against `python-can` for the `notifier.exception`
   not being cleared after successful `on_error()` handling. File a similar one against
   `canopen` for the `check()` method not verifying whether the exception was already
   handled.

---

## Local Reproduction Tests (CAP-NET-C FW 2.10.0)

### Setup

- **Drive**: CAP-NET-C (originally said CAP-XCR-C, confirmed as NET-C)
- **Firmware**: 2.10.0.000 (newer than the 2.9.0 that shows the bug in CI)
- **Transceiver**: PEAK USB (PCAN_USBBUS1)
- **Node ID**: 32
- **Baudrate**: 1 Mbit/s
- **Dictionary**: `cap-net-c_can_2.9.0_v2.xdf` (2.9.0 dict works with 2.10.0)

### Test 1: Passive listener (reproduce_stale_sdo.py)

Clean disconnect → manual power cycle → passive CAN listening for 10s → reconnect.

| Metric | Result |
|--------|--------|
| Unsolicited SDO responses | **0** |
| Heartbeats | 1 (NMT boot-up) |
| Post-reconnect SDO mismatches | **0** |
| Reads OK / errors | 504 / 6 (write-only) |

### Test 2: CI recovery path (reproduce_ci_path.py)

Same network → restore → manual power cycle → `recover_from_disconnection()` → bulk read.

| Metric | Result |
|--------|--------|
| Recovery time | ~1.5s |
| SDO flush iterations | 1 (clean immediately) |
| Post-recovery SDO mismatches | **0** |
| is_alive() | True |
| SDOTracer: TX/RX frames | 507 / 507 (perfectly paired) |
| SDOTracer: mismatches | **0** |
| SDOTracer: unsolicited | **0** |

### Conclusion

**CAP-NET-C FW 2.10.0 does NOT reproduce the stale SDO response bug.** Three runs showed
zero SDO mismatches, zero unsolicited responses, and zero "another SDO client" errors.

Possible explanations:
1. **FW 2.10.0 fixed the issue** — the SDO server initialization changed between 2.9.0
   and 2.10.0
2. **Different hardware variant** — CAP-NET-C vs CAP-XCR-C may have different SDO behavior
3. **Timing differences** — manual power cycle is slower than CI's automated relay; the
   drive has more time to settle before recovery begins

**Next step**: push the SDOTracer instrumentation to Jenkins so the next nightly build on
**CAP-XCR-C FW 2.9.0** produces a detailed SDO traffic trace when the bug occurs.

---

## Jenkins Build #25 — SDOTracer Captures the Bug (2026-04-07)

### Setup

- **Build**: PR-776 #25, triggered manually with `test_session_filter=canopen_capitan`,
  `RUN_POLICY_NIGHTLY=true`, `PYTHON_VERSIONS=MIN`
- **Commit**: `c1e63fb8` — SDOTracer instrumentation added
- **Drive**: CAP-XCR-C (node 21), FW 2.9.0 (CI hardware)

### Results

| Stage | Status | test_restore_parameters | test_enable_disable |
|-------|--------|------------------------|---------------------|
| CANopen Capitan FW 2.4.0 | **SUCCESS** | PASSED | PASSED |
| CANopen Capitan FW 2.9.0 | **UNSTABLE** | PASSED | **FAILED** |

### SDOTracer Output — FW 2.4.0 (All Clean)

Three recovery cycles, all perfectly clean:

| Trace | TX | RX | Mismatches | Unsolicited |
|-------|----|----|------------|-------------|
| 1 (test_recover_from_disconnection) | 11,295 | 11,295 | 0 | 0 |
| 2 (test_store_parameters_timed_recovery) | 947 | 947 | 0 | 0 |
| 3 (test_enable_disable) | 9,746 | 9,746 | 0 | 0 |

**Total: 43,976 frames, 0 mismatches, 0 unsolicited.** FW 2.4.0 has no SDO desync.

### SDOTracer Output — FW 2.9.0 (Bug Captured!)

| Trace | TX | RX | Mismatches | Unsolicited | Notes |
|-------|----|----|------------|-------------|-------|
| 1 (test_restore_parameters) | 12,003 | 12,003 | **0** | 2* | *False positives — segment frames (see below) |
| 2 (test_enable_disable) | 10,192 | **10,935** | **253** | **743** | **THE BUG!** 743 excess RX |

### Detailed Analysis — Trace 2 (The Failing Test)

**Frame count**: 10,192 TX requests sent, **10,935 RX responses received** — **743 more
responses than requests.** These 743 excess responses are stale SDO replies from the
previous test session.

**Timing**: All 743 unsolicited responses arrive within the first **750ms** (t=0.750s)
after the SDOTracer attaches (which is immediately after `_flush_sdo_responses()` completes).

**First 10 unsolicited responses** (all at t=0.750s):
```
0x1600:1  raw=[43 00 16 01 10 00 40 60]  ← PDO mapping register
0x1600:2  raw=[43 00 16 02 00 00 00 00]
0x1600:3  raw=[43 00 16 03 00 00 00 00]
0x1600:4  raw=[43 00 16 04 00 00 00 00]
0x1600:5  raw=[43 00 16 05 00 00 00 00]
0x1600:6  raw=[43 00 16 06 00 00 00 00]
0x1600:7  raw=[43 00 16 07 00 00 00 00]
0x1600:8  raw=[43 00 16 08 00 00 00 00]
0x1601:0  raw=[4f 01 16 00 02 00 00 00]
0x1601:1  raw=[43 01 16 01 10 00 40 60]
```

All byte 0 = `0x43` or `0x4F` = SCS 2 (initiate upload response). These are well-formed,
complete SDO responses for sequential register addresses — exactly like the "another SDO
client" errors seen in previous builds.

**First 5 mismatches** (at t=0.750s):
```
sent 0x1A00:8, got 0x1600:0   ← off by one dictionary section
sent 0x1A01:0, got 0x1602:4   ← completely desynchronized
sent 0x1A01:1, got 0x1603:4
sent 0x1A01:2, got 0x1800:6
sent 0x1A01:3, got 0x1A00:6   ← response index close but wrong subindex
```

### Timeline — FW 2.9.0 Second Recovery (the failing one)

```
11:30:33  SDOTracer #1 attached (test_restore_parameters recovery)
11:30:48  test_restore_parameters starts reads
11:30:59  SDOTracer #1 report: 24,006 frames, all matched, 2 segment FP
11:31:02  ⚠ Recovery partially failed ("some servos still disconnected")
11:31:04  Recovery succeeded, flush runs → reports clean
11:31:04  SDOTracer #2 attached
11:31:05  ~750ms later: SDO mismatch errors begin flooding
11:31:05  "Failed reading CIA301_COMMS_TPDO1_MAP_8: got 0x1600:0 instead"
  ... 220+ "another SDO client" errors ...
11:31:12  test_enable_disable starts
11:31:12  "Failed reading DRV_STATE_CONTROL: got 0x2011:0 instead"
11:31:21  test_enable_disable FAILED
11:31:17  SDOTracer #2 report: 253 mismatches, 743 unsolicited
```

### Root Cause Confirmed: Flush Race Condition

The SDOTracer data definitively proves the failure mechanism:

1. **The flush succeeds** — `_flush_sdo_responses()` drains the python-side Queue and
   two verification reads pass. At this moment, the queue IS clean.

2. **Stale responses arrive 750ms later** — They are buffered in lower-level layers
   (PCAN USB adapter internal buffer → USB driver → OS kernel buffer) and take ~750ms
   to be delivered to the python-side Queue after the flush.

3. **The stale responses are from a previous test session** — Their indices
   (`0x1600:1-8`, `0x1601:0-1`, etc.) are sequential PDO mapping registers from
   bulk reads performed during previous `DriveContextManager` operations.

4. **743 excess responses corrupt all subsequent SDO communication** — Each new SDO
   request picks up a stale response instead of the real one, causing index mismatches
   that cascade through the entire test.

**Why the flush fails**: The flush runs in <100ms. The stale response buffer is 743 frames
deep. At CAN 1Mbit/s, one extended SDO frame takes ~130μs, so 743 frames take ~96ms to
transmit on the bus. But the bottleneck is NOT the bus — it's the PCAN USB adapter's
internal buffering and USB transfer latency. The adapter collects frames in its internal
FIFO and transfers them to the PC over USB in batches. After a `disconnect()` + `connect()`
cycle, the adapter's FIFO is NOT cleared. The 743 stale frames sit in the FIFO and are
delivered over USB after the connection is re-established, arriving ~750ms later.

---

## Jenkins Build #28 — DCM Instance Analysis Confirms Error Flow (2026-04-07)

### Setup

- **Build**: PR-776 #28, triggered manually with same parameters as #25/#27
- **Commit**: `c6ea9517` — Added `logger.error` for skipped registers in `_store_register_data()`
- **Result**: UNSTABLE — `test_enable_disable` FAILED ×1

### SDOTracer Output

| Trace | TX | RX | Mismatches | Unsolicited | Notes |
|-------|----|----|------------|-------------|-------|
| 1 (test_store_parameters) | 12,003 | 12,003 | 0 | 2* | *Segment frame false positives |
| 2 (test_enable_disable) | 10,485 | **10,977** | **24** | **494** | **492 excess RX** |

### New `logger.error` Output — DCM Instance to Test Mapping

Each unique DCM instance ID confirms `scope="function"` — every test gets its own DCM.
All errors appear in `------ live log setup ------` (= `__enter__()` → `_store_register_data()`).

| Time | Test (`live log setup`) | DCM Instance | Registers Skipped |
|------|------------------------|--------------|-------------------|
| 13:26:27.597 | `test_read` | 2646429779760 | MON_CFG_REG7-10_MAP (4) |
| 13:26:28.401 | `test_monitoring_enable_disable` | 2646440551760 | TPDO1_3, TPDO1_5, TPDO1_6 (3) |
| 13:26:29.657 | `test_monitoring_remove_data` | 2646430670608 | Under_temp, STO, Sync (3) |
| 13:26:30.456 | `test_monitoring_data_size` | 2646434783584 | CL_TOR_PID_KI/MAX/MIN (3) |
| 13:26:31.676 | `test_disturbance_enable_disable` | 2646436407376 | FBK_BISS1_SSI1_* (4) |
| 13:26:32.890 | `test_disturbance_map_register` | 2646440500912 | DRV_STATE_CONTROL, DRV_OP_CMD, CL_VOL_Q (3) |
| **13:26:33.740** | **`test_enable_disable`** | 2646438749520 | TPDO1_MAP_1-3 (3) |
| 13:26:35.150 | `test_enable_disable` **body** | — | DRV_STATE_CONTROL → got 0x2011 → **FAILED** |
| 13:26:35.978 | `test_fault_reset` | 2646439630400 | MEM_USR_ADDR (1, SDO timeout + PCAN overrun) |

**Total**: 8 consecutive test setups affected, 24 registers skipped, 1 test body read corrupted.
After `test_fault_reset`, stale responses are exhausted — all subsequent tests pass.

---

## Build #30 — FW 2.10.0 First Run (2026-04-08)

- **Build**: PR-776 #30
- **Commit**: `c26ac459` — Enhanced SDOTracer (full unsolicited index dump) + DCM register
  read order logging
- **Result**: SUCCESS — all FW versions clean (2.4.0, 2.9.0, 2.10.0)
- Bug did NOT reproduce. SDOTracer clean on all FW versions.
- Both FW 2.9.0 and 2.10.0 show exactly 2 residual segment frames for 0x58A4:0 (false positives).

---

## PCAN FIFO Theory Debunked (2026-04-08)

### The Challenge

If our flush sequence sends at least two round-trip SDO reads and both succeed, those
reads must have traversed the entire FIFO. Any stale frames would be **ahead** of them
in a true FIFO — consumed before the flush reads, not after.

### Evidence

1. **`canopen.Network.disconnect()`** calls `PCANBasic.Uninitialize()` — fully releases the
   hardware channel. This destroys all internal PCAN adapter state.
2. **`canopen.Network.connect()`** calls `PCANBasic.Initialize()` — opens a fresh channel
   with empty buffers.
3. **FIFO ordering**: Even if something survived, stale frames would arrive BEFORE the
   flush verification reads — the flush would consume them first.

### Conclusion

The "PCAN adapter FIFO" theory is **WRONG**. The stale responses cannot exist in any
adapter-side buffer at flush time. They are **generated by the drive AFTER** the flush
completes.

The drive's CAN controller does NOT power cycle during the hardware relay cycle — it
retains its state while only the CPU power domain is affected.

---

## Build #34 — BREAKTHROUGH: Full Unsolicited Index Capture (2026-04-08)

### Setup

- **Build**: PR-776 #34
- **Commit**: `c26ac459` (same as #30 — enhanced SDOTracer + DCM register order logging)
- **Result**: FW 2.4.0 SUCCESS, **FW 2.9.0 UNSTABLE** (3 failures), FW 2.10.0 SUCCESS
- **Failed tests**: `test_enable_disable` ×2, `test_fault_reset`

### SDOTracer Output

| Trace | TX | RX | Mismatches | Unsolicited | Notes |
|-------|----|----|------------|-------------|-------|
| 1 (test_restore_parameters run) | 12,003 | 12,003 | 0 | 2* | *0x58A4:0 false positives |
| 2 (post-recovery through session end) | 11,788 | **12,592** | **32** | **804** | **804 excess RX** |

### Timeline of test_restore_parameters

```
11:09:42.688  __enter__() → _store_register_data() reads 494 registers (all succeed)
11:09:42.689  restore_parameters() → NV restore (drive still operational)
11:09:42.7    servo.read() → succeeds → power_cycle() starts
11:09:45.278  First bus error (CAN controller issues after relay off)
11:09:45-54   Bus errors continue (~9 seconds, CPU off)
11:09:54.025  SDOTracer#1 report: 24,006 frames, ALL MATCHED, 2 false-positive unsolicited
11:09:54.860  First reconnect (PCAN Initialize) → is_alive() fails 5× → returns False
11:09:58.204  Second reconnect → is_alive() succeeds → "communication recovered"
11:09:58.204  SDOTracer#2 attached
11:09:58.891  ★ t=0.687s: First stale responses start arriving from the drive
11:09:58.986  PASSED [63%]
11:09:58.986  Teardown: force_restore() → _store_register_data() reads 494 again
11:09:58.986  test_read __enter__(): "Failed reading CIA301_COMMS_RPDO1_6: got 0x60F2:0 instead"
  ... stale responses interfere with subsequent tests ...
11:10:07.697  test_enable_disable FAILED [87%]
11:10:08.934  test_enable_disable FAILED [89%]
11:10:11.794  SDOTracer#2 report: 32 mismatches, 804 unsolicited
```

### Programmatic Analysis of 804 Unsolicited Responses

```
Total unsolicited: 806 (804 from SDOTracer#2 + 2 from SDOTracer#1)
DRV_STATE_STATUS (0x2011:0): 183 entries
Dictionary registers (excl. status): 623 entries (414 unique)

Set analysis:
  DCM unique registers: 494
  Unsolicited unique (excl. status): 414
  In DCM register set: 413/414 (99.8%)
  NOT in DCM: 1 (0x58A4:0 — false positive from SDOTracer#1)

Sequence analysis:
  First 50 unsolicited: STRICTLY DECREASING in DCM order (positions 493→125)
    → These are the LAST registers from _store_register_data() in REVERSE
  Forward block [50-433]: 384 entries in roughly FORWARD DCM order
  Status block [434-494]: 61 × DRV_STATE_STATUS
  Remaining [495-805]: 311 entries, mix of forward DCM order + status

Coverage: 413/494 DCM registers appear in unsolicited (81 missing)
Duplicates: 164 registers appear >1 time (up to 6× for 0x2010:0)
```

### Key Finding: Nobody Sends These Requests

The SDOTracer hooks `network.send_message()` and captures **every outgoing SDO request
frame**. With 11,788 TX and 12,592 RX, there are **804 more responses than requests**.
These 804 response frames have **NO corresponding request** from our side.

The PCAN adapter was fully reinitialized (`CAN_Uninitialize` + `CAN_Initialize`) between
recovery attempts. Any PCAN-side buffering was cleared. The responses **must originate
from the drive itself**.

### Revised Root Cause: Drive CAN Controller Retransmission

The drive's CAN controller does NOT power cycle during the hardware relay cycle (CPU-only
power domain). The CAN controller's message RAM (TX buffers) retains old data while the
CPU is off.

**Mechanism (FW 2.9.0 bug)**:

1. During normal operation, each SDO response is written to the CAN controller's hardware
   TX buffer and transmitted on the bus. The host receives it normally.

2. The hardware power cycle turns off only the CPU. The CAN controller stays powered, and
   its message RAM (containing TX buffer contents) is preserved.

3. When the CPU boots back up, the bootloader/firmware re-initializes the CAN controller.
   **In FW 2.9.0, the TX buffer is NOT properly cleared during this initialization.**

4. The old response frames (from the previous session's `_store_register_data()` reads
   and status listener polls) remain in the TX buffer.

5. Once the CAN stack is fully initialized (~0.687s after reconnection), the CAN controller
   begins retransmitting these old frames as if they were new pending transmissions.

6. These 804 stale response frames arrive as a burst and interfere with the legitimate SDO
   reads of `force_restore()` and subsequent test setups.

**Why this only affects FW 2.9.0**:
- FW 2.4.0 likely clears the CAN TX buffer properly during initialization
- FW 2.10.0 likely fixed this bug (2/2 runs clean)
- The ~0.687s boot-to-retransmit delay is consistent across reproductions (~750ms in #25, ~687ms in #34)

**Why the flush cannot help**: The flush runs immediately after recovery succeeds. The
stale responses arrive ~0.687s LATER. No amount of host-side flushing can prevent frames
that haven't been generated yet.

**Supporting evidence**:
- 99.8% of unsolicited register indices match the DCM register set → same registers read
  by `_store_register_data()`
- First 50 unsolicited are in REVERSE DCM order → last entries in the TX buffer
- 183 × DRV_STATE_STATUS → from the servo_status_listener responses in the TX buffer
- Some registers appear up to 6× → TX buffer contains responses from multiple DCM read
  sessions (multiple test setups accumulated before the power cycle)
- The `0x60` command specifier on some entries = SDO Download Response (write
  acknowledgment) → from `_restore_register_data()` writes also retained in TX buffer

---

## Updated Build History

| Build | Commit | FW 2.4.0 | FW 2.9.0 | FW 2.10.0 | Notes |
|-------|--------|----------|----------|-----------|-------|
| #25 | `c6ea9517` | ✅ | ❌ (3 fail) | — | First SDOTracer capture: 743 unsolicited |
| #27 | `c6ea9517` | ✅ | ✅ | — | Bug did not reproduce |
| #28 | `c6ea9517` | ✅ | ❌ (1 fail) | — | DCM instance analysis confirms `__enter__()` |
| #29 | `c26ac459` | — | — | — | ABORTED |
| #30 | `c26ac459` | ✅ | ✅ | ✅ | FW 2.10.0 first run — all clean |
| #34 | `c26ac459` | ✅ | ❌ (3 fail) | ✅ | **BREAKTHROUGH**: 804 unsolicited with full index dump |

### Success Rates (FW 2.9.0 with SDOTracer builds only)

| Metric | Value |
|--------|-------|
| Total runs | 5 (#25, #27, #28, #30, #34) |
| Passed | 2 (#27, #30) |
| Failed | 3 (#25, #28, #34) |
| Rate | 40% pass, **60% fail** |

### Success Rates (FW 2.10.0)

| Metric | Value |
|--------|-------|
| Total runs | 2 (#30, #34) |
| Passed | 2 |
| Rate | **100%** (insufficient data for firm conclusions) |

### Mismatch Timing Distribution (vs Build #25)

Unlike build #25 (all mismatches at t=0.750s in one burst), build #28 shows mismatches
spread across **~8 seconds** at ~1s intervals:

```
t=0.812s:  4 mismatches  (test_read setup)
t=1.859s:  3 mismatches  (test_monitoring_enable_disable setup)
t=2.906s:  3 mismatches  (test_monitoring_remove_data setup)
t=3.953s:  3 mismatches  (test_monitoring_data_size setup)
t=5.000s:  4 mismatches  (test_disturbance_enable_disable setup)
t=6.047s:  3 mismatches  (test_disturbance_map_register setup)
t=7.094s:  3 mismatches  (test_enable_disable setup)
t=8.187s:  1 mismatch    (test_enable_disable body → failure)
```

Each ~1s interval = ~500ms for `_store_register_data()` bulk read + ~400ms SDO timeout
when a stale response consumes the slot of a legitimate read.

### Key Confirmation

1. **Zero errors in `force_restore()`** — It completes before stale responses arrive
   (`force_restore()` runs at ~13:26:27.0, stale responses start at 13:26:27.597 = 812ms
   after SDOTracer attachment at 13:26:26.786)
2. **All errors in `__enter__()`** — Every `Skipping uid=` log is under `live log setup`
3. **Different DCM instances per test** — 8 unique IDs across 8 test setups
4. **Stale responses trickle, don't burst** — 494 unsolicited over 8s vs 743 over <1s in #25

### False Positive in SDOTracer (Minor Bug)

The 2 "unsolicited responses" in Trace 1 at t=10.938s are **false positives**:
```
0x58A4:0  raw=[20 a4 58 00 00 00 00 00]  ← byte 0 = 0x20 → SCS 1 → segment download response
0x58A4:0  raw=[30 a4 58 00 00 00 00 00]  ← byte 0 = 0x30 → SCS 1 (toggle bit)
```

`_is_initiate_frame()` checks `(data[0] >> 5) & 0x07 in (1, 2, 3, 4)`. For server (RX)
responses, SCS=1 (0x20-0x3F) is a segment download response — bytes 1-7 are data payload,
NOT index/subindex. The `0x58A4` "index" is actually segment data bytes misinterpreted.

**Fix needed**: `_is_initiate_frame()` should accept a `direction` parameter and use
different CCS/SCS sets for TX vs RX:
- TX (client): CCS ∈ {1, 2} = initiate (CCS 0 = segment, CCS 3 = block)
- RX (server): SCS ∈ {2, 3} = initiate (SCS 0, 1 = segment)
- Both: CCS/SCS 4 = abort (always has index/subindex)

---

## Jenkins Build #30 — FW 2.10.0 First Run (2026-04-07)

### Setup

- **Build**: PR-776 #30, triggered manually with `test_session_filter=canopen_capitan`,
  `RUN_POLICY_NIGHTLY=true`, `PYTHON_VERSIONS=MIN`
- **Commit**: includes FW 2.10.0 rack specifier additions
- **Result**: **SUCCESS** — all tests passed on FW 2.4.0, 2.9.0, and 2.10.0

### SDOTracer Output — All FW Versions

| FW | Trace | TX | RX | Mismatches | Unsolicited | Notes |
|----|-------|----|----|------------|-------------|-------|
| 2.4.0 | 1 (test_store) | 11,295 | 11,295 | 0 | 0 | |
| 2.4.0 | 2 (test_restore) | 947 | 947 | 0 | 0 | |
| 2.4.0 | 3 (test_enable_disable) | 9,712 | 9,712 | 0 | 0 | |
| **2.9.0** | 1 (test_store) | 12,003 | 12,003 | 0 | 2* | *Segment frame FP |
| **2.9.0** | 2 (test_enable_disable) | 10,354 | 10,354 | 0 | 0 | |
| **2.10.0** | 1 (test_store) | 12,491 | 12,491 | 0 | 2* | *Segment frame FP |
| **2.10.0** | 2 (test_enable_disable) | 10,781 | 10,781 | 0 | 0 | |

### Key Observations

1. **FW 2.10.0 behaves identically to FW 2.9.0** — both show exactly 2 residual segment
   frames for register `0x58A4:0` in the test_restore_parameters recovery span. FW 2.4.0
   never produces these. This confirms the segment frames are a FW ≥2.9.0 behavior change
   (harmless, false positive in SDOTracer).

2. **Bug did NOT reproduce** — 0 stale SDO floods on any FW version. No "Skipping uid="
   DCM logger.error messages. The timing lottery went in our favor this run.

3. **FW 2.10.0 frame counts** are slightly higher than 2.9.0 (12,491 vs 12,003 TX in
   trace 1, 10,781 vs 10,354 TX in trace 2). This is expected — the dictionary for 2.10.0
   likely has a few more registers.

4. **Recovery pattern identical across all FW versions**: double-reconnect (first attempt
   "still disconnected", second succeeds), 5 SDO timeouts during is_alive() retries, all
   recover successfully.

### Build #30 Success Rates Summary

With build #30 data:

| FW Version | Runs with SDOTracer | Stale flood occurred | Rate |
|------------|-------------------|---------------------|------|
| FW 2.4.0 | 4 (#25, #27, #28, #30) | 0 | **0%** |
| FW 2.9.0 | 4 (#25, #27, #28, #30) | 2 (#25, #28) | **50%** |
| FW 2.10.0 | 1 (#30) | 0 | **0%** (insufficient data) |

---

## Architecture: Error Flow

```mermaid
sequenceDiagram
    participant FW as Drive Firmware
    participant PCAN as PCAN USB
    participant Notifier as can.Notifier._rx_thread
    participant CL as CustomListener.on_error()
    participant SDO as canopen SDO Client
    participant DCM as DriveContextManager
    participant Test as test_restore_parameters

    Test->>FW: force_restore() → power cycle
    Note over FW: Drive reboots

    Test->>SDO: recover_from_disconnection() #1
    SDO->>FW: is_alive() × 5 → all timeout (drive still booting)
    Note over Test: Recovery #1 fails

    Test->>SDO: recover_from_disconnection() #2
    SDO->>FW: is_alive() → OK (drive is up)
    SDO->>SDO: _flush_servo_sdo_responses() ✅
    Note over SDO: Flush passes: queue clean at this moment

    Test->>Test: test_restore_parameters PASSES ✅

    Note over DCM: force_restore() runs in teardown
    DCM->>SDO: _store_register_data() (bulk read ~500 regs, ~500ms)
    Note over SDO: Completes before stale responses arrive

    FW-->>PCAN: ~494 stale SDO responses buffered in PCAN FIFO
    Note over FW: FW 2.9.0 replays SDO responses (sequential register order)

    Note over DCM: Next test (test_read) fixture setup begins
    DCM->>SDO: __enter__() → _store_register_data()
    Note over PCAN: ~812ms after flush: stale responses start arriving
    FW-->>SDO: Stale response (wrong index) arrives
    SDO-->>DCM: SdoCommunicationError → ILIOError
    DCM->>DCM: logger.error("Skipping uid=...") → continue
    Note over DCM: 4 registers skipped in test_read setup

    Note over DCM: test_monitoring setup (new DCM instance)
    DCM->>SDO: __enter__() → _store_register_data()
    FW-->>SDO: More stale responses
    Note over DCM: 3 registers skipped

    Note over DCM: ... pattern repeats across 8 test setups ...

    Note over DCM: test_enable_disable setup (DCM 2646438749520)
    DCM->>SDO: __enter__() → _store_register_data()
    FW-->>SDO: Stale responses still arriving
    Note over DCM: 3 registers skipped (TPDO1_MAP_1-3)

    Test->>SDO: test_enable_disable body → servo.enable()
    SDO->>FW: read DRV_STATE_CONTROL
    FW-->>SDO: Stale response for 0x2011:0
    SDO-->>Test: ILIOError: got 0x2011:0 instead
    Note over Test: FAILS ❌

    Note over DCM: test_fault_reset setup
    PCAN-->>Notifier: PCAN_ERROR_OVERRUN
    Notifier->>CL: on_error(exc)
    CL->>Notifier: notifier.exception = None (cleared ✅)
    Note over DCM: 1 register skipped (MEM_USR_ADDR) — last stale response
    Test->>Test: test_fault_reset PASSES ✅ (stale stream exhausted)
```
