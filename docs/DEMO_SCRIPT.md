# Live demonstration script

> **Audience:** a review panel or examiners. **Length:** ≈ 10 minutes live, or ≈ 75 s with the hands-free autopilot.
> Every number on screen comes from the running system; nothing is pre-recorded.

## Contents

1. [Before the panel arrives](#1-before-the-panel-arrives)
2. [Option A: hands-free autopilot (▶ Run demo)](#2-option-a-hands-free-autopilot--run-demo)
3. [Option B: guided walkthrough (manual)](#3-option-b-guided-walkthrough-manual)
4. [Questions to expect, with honest answers](#4-questions-to-expect-with-honest-answers)
5. [Recovery: if something goes wrong](#5-recovery-if-something-goes-wrong)
6. [Headless alternative](#6-headless-alternative)

---

## 1. Before the panel arrives

| ✔ | Step | Command / action |
|:---:|---|---|
| ☐ | Start the server | `source .venv/bin/activate && python run.py` (macOS: `PORT=5001 python run.py`) |
| ☐ | Check it is alive | `curl -s http://127.0.0.1:5000/healthz` → `{"ok":true}` |
| ☐ | Optional clean audit log | stop the server, delete `data/audit.jsonl`, start again |
| ☐ | Main window | open <http://127.0.0.1:5000>, sign in as **admin** (`admin` / `admin@pqc`) |
| ☐ | Second window | a private window for the **researcher** and **auditor** logins |
| ☐ | Readability | press **P** for presenter mode (larger text, secondary panels hidden); pick the light or dark theme for the room |
| ☐ | Live indicator | the header shows **● live** and a **TIER 5** badge |

---

## 2. Option A: hands-free autopilot (▶ Run demo)

<p align="center"><img src="images/autopilot.png" alt="Autopilot narration panel" width="820"></p>

Click **▶ Run demo** in the header (or on the Overview page). The tour drives the real system and narrates each step; you talk over it.

| Step | ≈ Time | On screen | Say |
|:---:|---:|---|---|
| 1 · Introduction | 5 s | Overview | "Strongest protection the network can afford, never below Tier 3 for raw patient data." |
| 2 · Heavy-load demo | 30 s | Live: tier 5 → 3 → 1 → 5 | "Watch the budget fall and the hysteresis pips fill. The research path drops to Tier 1, but the clinical card stays at Tier 3: **Safety floor holding**." |
| 3 · Tamper Lab | 13 s | Three bit-flips, three **REJECTED** verdicts | "One flipped bit in ciphertext, tag or signature, and the packet is rejected. The untampered control still verifies." |
| 4 · Privacy sliders | 14 s | ε sweeps 2 → 0.1; K goes 2 → 5 | "Smaller ε, more noise, stronger privacy. Larger K, every patient hides in a bigger crowd." |
| 5 · Results | 9 s | Evaluation charts | "Thirty paired trials: fewer SLA violations than static Tier 5 under stress, 65 % less flapping, floor held every time." |

Controls: **⏸ Pause** (the gateway keeps running live), **⏭ Skip**, **■ Stop** (also cancels the server-side stress). Clicking any tab hands control back to you.

---

## 3. Option B: guided walkthrough (manual)

### 3.1 Live tab: the closed loop (≈ 4 min)

<p align="center"><img src="images/live-stress.png" alt="Live tab during severe congestion" width="820"></p>

| # | Do | Point at | Say |
|:---:|---|---|---|
| 1 | Open **Live**, calm network | Control loop: Probe → Budget → CADA → Tier | "Budget is ≈ 195 ms, so CADA-AASM runs the maximum suite: Tier 5, ML-KEM-1024 + ML-DSA-87 + AES-256-GCM, ε = 0.1, K = 5." |
| 2 | Click **▶ Simulate Heavy Load** | Guided-demo rail, phase 2 | "This injects congestion on top of the *real* loopback RTT and host CPU. The injected part is always shown separately." |
| 3 | Watch the budget marker cross 80 ms | CADA node: target + pips | "The controller *wants* a lower tier, but it needs three agreeing cycles: 1/3, 2/3, 3/3. A single spike never causes a re-key." |
| 4 | Tier badge turns amber, then red | Events panel: TIER + REKEY lines | "Each change re-keys make-before-break: a new hybrid handshake runs while data keeps flowing, so no packet is dropped." |
| 5 | Severe phase | Clinical vs research nodes | "Research is at Tier 1 (ε = 1.0, K = 2). Clinical PHI is held at **Tier 3** by the floor: that is the compliance invariant." |
| 6 | Recovery phase | Timeline: background bands, dashed tier changes | "Stress cleared; after three good cycles it climbs back to Tier 5. That is the closed loop." |
| 7 | KPI row | Lowest clinical tier = T3 | "The floor held throughout, and it held in all 30 evaluation trials." |
| 8 | *(optional)* Manual controls → **Static Tier 5 baseline**, run the demo again | KPI counters | "Same stress, no steering. Compare the violation counters." Honest framing: on a real link this difference only matters on very thin links (see §4). |

### 3.2 Security Lab: one real packet (≈ 2 min)

<p align="center"><img src="images/security-lab.png" alt="Security Lab" width="820"></p>

| # | Do | Say |
|:---:|---|---|
| 9 | Click **Refresh** on the inspector | "Five stages of one real clinical packet: hybrid master secret → HKDF keys → plaintext → AEAD envelope → base64url wire token." |
| 10 | Tamper Lab: target *Ciphertext*, **⚡ Inject bit-flip** | "One flipped bit: the signature layer fails, the AEAD layer fails, the packet is rejected. The untampered control still verifies." |
| 11 | Repeat with *Header (sequence)* | "Now all three layers fail, including anti-replay." |
| 12 | Repeat with *Ed25519 signature* | "Only the signature fails, and that alone is enough to reject." |

### 3.3 Privacy (≈ 1.5 min)

<p align="center"><img src="images/privacy.png" alt="Privacy tab" width="820"></p>

| # | Do | Say |
|:---:|---|---|
| 13 | Drag the ε slider, or click **T5 · ε 0.1** / **T3** / **T1** | "Smaller ε, more noise, stronger privacy. The curve below shows the cost in signal-to-noise; the ring is where we are." |
| 14 | Click **T5 · K 5 L 3** | "Each released record now hides among at least 5 patients with 3 different diagnoses, and the release is independently verified." |

### 3.4 Roles, results and audit (≈ 2 min)

| # | Do | Say |
|:---:|---|---|
| 15 | Private window: sign in as **researcher** | "No Live tab, no raw ECG or EHR. The server returns 403, it is not just hidden. The export is hard-floored at K ≥ 5, L ≥ 3." |
| 16 | **Results** tab | "The evaluation, live from `results.json`: violations, flapping, where it helps (the heat-map), and the paired tests, including the negative result for batch signing." |
| 17 | Sign in as **auditor** → **Audit** | "Every handshake, tier change, stress event, tamper test, login and export is in a hash-chained, HMAC-protected log. Chain status: intact." |

---

## 4. Questions to expect, with honest answers

| Question | Answer |
|---|---|
| *Is the network real?* | RTT and CPU probes are real loopback / host readings; congestion is **emulated** in the main evaluation and always shown separately. The separate real-link testbed uses kernel shaping, and there the gain over static Tier 5 **disappears at ≥ 2 Mbit/s**. See [`LIMITATIONS.md`](LIMITATIONS.md) and [`reports/testbed_report.md`](../reports/testbed_report.md). |
| *Does adaptation always help?* | No. It helps on constrained links (≈ −45 pp at 1 Mbps in the emulator; at 0.5 Mbit/s on the real link static T5 fails every cycle, CADA 13 %). A well-chosen static Tier 3 is as good or better on latency. The remaining value is joint privacy/crypto adaptation and stronger protection when the budget allows. |
| *Why not sign every packet with ML-DSA?* | That is exactly the cost the project is about. Batch (epoch) signing amortises it; `epoch_len = 1` reproduces per-packet signing and is the evaluation baseline. |
| *Isn't adaptive PQC already known?* | Yes (AdaptiveQKE, CAAP, Q-PRADAX). The claim is narrower: the **joint** coupling of transport crypto and privacy under one latency budget with a raw-PHI floor. See [`RELATED_WORK.md`](RELATED_WORK.md). |
| *Why pure-Python PQ, not liboqs?* | Portability for the demo. It is functionally correct but slow and not constant-time. The library boundary is two dictionaries in `crypto/hybrid.py`; native liboqs timings are in the testbed report (≈ 0.1 ms per ML-DSA sign). |
| *Why does research privacy change with the network?* | A deliberate trade-off; exports are floored at K ≥ 5, L ≥ 3 regardless of tier. |
| *Is any patient data real?* | No. All ECG, vitals and EHR data are synthetic. |
| *Why does the inspector show keys?* | It is a teaching view for evaluators, restricted to the admin role. Remove the `inspect` permission for any non-demo use. |

---

## 5. Recovery: if something goes wrong

| Symptom | Fix |
|---|---|
| Header shows **○ offline** | Reload the page; make sure you opened the exact URL printed by `run.py`; check that no proxy blocks WebSockets |
| "Address already in use" | Start on another port: `PORT=5001 python run.py` |
| Tier stays low after a demo | Live → Manual controls → **calm**, or press **■ Stop** in the autopilot panel |
| A demo is already running | Wait for it to finish (≈ 23 s) or stop it from the autopilot panel |
| Signed out unexpectedly | Tokens last 8 h; sign in again |
| Blank page at `/` with a 503 message | The frontend is not built: `cd frontend && npm install && npm run build` |

---

## 6. Headless alternative

No browser available? The same scenario runs in the terminal:

```bash
python run.py --demo            # real host probes, ≈ 25 s
python run.py --demo --fast     # no sleeping between cycles
python run.py --demo --static   # adaptation OFF (static Tier 5 baseline) for comparison
```

Each row shows budget, RTT, CPU, hysteresis count, agile tier, PHI tier, both latencies, ε, K/L and events; the run ends with counters and the audit-chain verification.
