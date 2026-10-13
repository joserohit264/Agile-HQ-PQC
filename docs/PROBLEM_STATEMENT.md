# Problem statement, research gap and contributions

> **Agile-HQ-PQC** · *Adaptive Quantum-Safe Security and Privacy for Healthcare Data*
> This document frames the research problem in plain terms for reviewers, examiners and slide decks. Technical detail is in [`ARCHITECTURE.md`](ARCHITECTURE.md); caveats are in [`LIMITATIONS.md`](LIMITATIONS.md).

## Contents

1. [The 30-second explanation](#1-the-30-second-explanation)
2. [Problem](#2-problem)
3. [Research gap](#3-research-gap)
4. [Research question](#4-research-question)
5. [Contributions](#5-contributions)
6. [The three protection levels](#6-the-three-protection-levels)
7. [Scope and non-goals](#7-scope-and-non-goals)
8. [Answer to the research question (evidence so far)](#8-answer-to-the-research-question-evidence-so-far)
9. [Suggested slides](#9-suggested-slides)
10. [Strongest next step](#10-strongest-next-step)

---

## 1. The 30-second explanation

> Quantum-safe encryption makes hospital data packets much bigger, and that can break real-time patient monitoring on slow networks. Our system watches the network and picks the **strongest protection it can currently afford**, for both encryption *and* patient-data privacy, but it **never goes below a safe minimum for raw patient data**.

---

## 2. Problem

A hospital must protect patient data against future quantum attacks and also de-identify it for research, but stronger protection costs time that real-time patient monitoring does not have.

**Confidentiality has to last decades.** Health records must stay confidential for the lifetime of the patient. Encrypted traffic captured today can be stored and decrypted once large quantum computers exist ("harvest now, decrypt later"). Post-quantum cryptography (PQC) therefore cannot wait.

**PQC is large.** ML-KEM and ML-DSA objects are roughly 10–100× larger than their classical counterparts. An ML-DSA-87 signature (4 627 B) is about 16× the size of a typical ≈ 300 B ICU telemetry packet, and turns it into a 4-fragment, ≈ 5 KB packet.

**Clinical monitoring is latency-bound.** Streaming ICU telemetry tolerates roughly **200 ms** end to end. On congested, lossy or low-bandwidth links, bigger packets mean more serialisation, more fragments to queue and more exposure to loss.

**Privacy is configured separately.** Data shared for research must be de-identified (differential privacy, K-anonymity). Today crypto strength and privacy strength are tuned independently, so a hospital must either:

| Choice | Consequence |
|---|---|
| Fix everything at maximum strength | Risks SLA violations whenever the network degrades |
| Fix everything at a lighter setting | Under-protects data whenever the network is healthy |
| Retune by hand | Slow, error-prone, and can silently drop raw PHI below policy |

**Problem to solve.** How can a healthcare gateway choose, at run time and without human intervention, the strongest combination of post-quantum transport protection and privacy parameters that still meets the latency budget, while never lowering the protection of raw patient data below a safe minimum?

---

## 3. Research gap

From the 18 IEEE Xplore papers (2023 to 2026) in [`REPORT.md`](REPORT.md) section 5:

1. **No paper joins post-quantum cryptography and privacy.** Of the 18, none sets a differential-privacy or anonymity parameter together with a post-quantum suite.
2. **Run-time adaptation is thin.** Only \[6\] (rule-based, one device) and \[10\] (UAV simulation) adapt post-quantum settings at run time. Neither is for healthcare, neither adapts privacy, and neither is tested on a shaped link.
3. **Floors are soft or absent.** \[10\] allows its security floor to drop under load. This project holds raw clinical data at NIST Category 3 or above.
4. **Network evidence is mostly static.** The cost studies \[7\], \[11\]–\[15\] measure one fixed configuration at a time.

**Claimed gap:** joint control of transport cryptography and privacy through one latency budget, with a hard floor for raw clinical data, evaluated on emulated and real shaped links. A 2026 survey lists this direction as open \[28\].

> [!NOTE]
> The survey was a single reviewer working on IEEE Xplore only, with all 18 papers read in full. It is not a systematic review, and the gap holds for these 18 papers and the seven non-IEEE works in section 8.3 of the report, not for all published work. Run-time selection of post-quantum settings \[6\], \[10\], \[24\]–\[26\] and adaptive privacy budgets \[18\], \[20\], \[21\], \[27\] are **not** novel. See [`RELATED_WORK.md`](RELATED_WORK.md) and [`LITERATURE_REVIEW.md`](LITERATURE_REVIEW.md).

---

## 4. Research question

> **Can transport security and data privacy be steered together by the network's remaining latency budget, without dropping raw patient data below a safe minimum, and when is that worth doing?**

Sub-questions:

| # | Sub-question | Where answered |
|---|---|---|
| RQ1 | Does joint steering reduce SLA violations compared with a fixed maximum suite? | Evaluation Part A |
| RQ2 | Does a persistence filter prevent cipher flapping without hurting latency? | Evaluation Part A (ablation) |
| RQ3 | Is the clinical floor always held? | Evaluation invariants, tests |
| RQ4 | Under which network conditions does steering help, and when does it not? | Evaluation Part B sweep, real-link testbed |

---

## 5. Contributions

| # | Contribution | Artefact |
|---|---|---|
| C1 | **Joint model**: three levels (High / Medium / Low = Tier 5 / 3 / 1), each binding KEM, signature, AEAD, ε, K and L | `core/tiers.py` |
| C2 | **Safe adaptive policy**: one latency-budget controller (CADA-AASM), a 3-cycle persistence filter, a Category-3 floor for raw PHI, and a K ≥ 5 / L ≥ 3 floor on researcher exports | `core/cada.py`, `web/app.py` |
| C3 | **Honest evaluation**: 30 paired trials, ablations, a bandwidth × loss sweep and a real-link testbed. It shows the approach helps on constrained links but not at ≥ 5 Mbps, not with batch signing, and, on a real link, not at ≥ 2 Mbit/s | `evaluation/`, `testbed/`, `reports/` |

The Command Center, tamper lab, autopilot and audit log are **supporting implementation**, not claimed novelty.

---

## 6. The three protection levels

| Level | Tier | KEM + signature | Cipher | ε | K / L | Chosen when budget is |
|---|:---:|---|---|:---:|:---:|---|
| 🟢 High | 5 | ML-KEM-1024 + ML-DSA-87 | AES-256-GCM | 0.1 | 5 / 3 | > 80 ms |
| 🟡 Medium | 3 | ML-KEM-768 + ML-DSA-65 | AES-256-GCM | 0.5 | 3 / 2 | 40–80 ms |
| 🔴 Low | 1 | ML-KEM-512 + ML-DSA-44 | ChaCha20-Poly1305 | 1.0 | 2 / 2 | ≤ 40 ms |

Raw clinical telemetry always uses **max(agile tier, Medium)**.

---

## 7. Scope and non-goals

| In scope | Out of scope |
|---|---|
| Transport security of IoMT telemetry between gateways | End-device firmware security, physical attacks |
| Privacy of the de-identified research stream and EHR exports | Clinical decision support, data quality |
| Latency-driven steering with a compliance floor | Formal security proofs of the hybrid construction |
| Synthetic ECG / vitals / EHR | Real patient data, regulatory certification |
| A single-host prototype and a single-host real-link testbed | Multi-hospital deployment, PKI, high availability |

---

## 8. Answer to the research question (evidence so far)

| Question | Answer | Evidence |
|---|---|---|
| RQ1 | **Yes, in the emulator**: 7.4 % → 4.1 % clinical violations under stress vs static T5 (p < 1e-4). **Not reproduced on a real link at ≥ 2 Mbit/s**, where nothing violated the SLA | `reports/module7_evaluation_report.md`, `reports/testbed_report.md` |
| RQ2 | **Yes**: tier changes fall 6.9 → 2.4 per trial (−65 %) with no significant latency penalty | Evaluation Part A |
| RQ3 | **Yes**: minimum clinical tier was 3 in every trial, in both the emulator and the testbed | Evaluation invariants; testbed Part A |
| RQ4 | Helps on **constrained links** (≈ −45 pp at 1 Mbps emulated; 100 % → 13 % at 0.5 Mbit/s real). Little or nothing at ≥ 5 Mbps; batch signing removes most of the problem on its own; a well-chosen static T3 is as good or better on latency | Part B sweep; testbed Part B |

**Overall:** joint steering is a sound and safe mechanism, but its latency benefit is narrow. Its stronger argument is that it delivers the **strongest crypto and privacy the budget allows** (mean ε 0.37 vs 0.50 for static T3) while guaranteeing the clinical floor.

---

## 9. Suggested slides

| Slide | Message | Figure |
|---|---|---|
| 1 | Violations and latency: static High vs static Medium vs adaptive | `reports/fig1.png`, `reports/fig2.png` |
| 2 | Tier trajectory, with the floor holding and no flapping | `reports/fig3.png` |
| 3 | Where steering helps: benefit vs bandwidth | `reports/fig5.png` |
| 4 | Reality check on a real shaped link | `reports/fig6_testbed.png` |

---

## 10. Strongest next step

Extend the software testbed (`testbed/`) with kernel `netem` packet loss and delay (needs a kernel with `sch_netem`), or move to a multi-host virtual-machine setup, using the native liboqs stack. This removes the remaining emulated parts and tests whether the thin-link benefit holds under real random loss.
