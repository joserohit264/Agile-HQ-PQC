# Limitations, deviations and honest caveats

> **Read this before presenting results.** Every point below is something an examiner could reasonably ask about. The project's credibility rests on stating these limits up front rather than having them discovered.

## Contents

1. [Summary: what is real and what is not](#1-summary-what-is-real-and-what-is-not)
2. [Deviations from the original project description](#2-deviations-from-the-original-project-description)
3. [Network and latency](#3-network-and-latency)
4. [Cryptography](#4-cryptography)
5. [Privacy](#5-privacy)
6. [Evaluation and statistics](#6-evaluation-and-statistics)
7. [Deployment and security of the prototype itself](#7-deployment-and-security-of-the-prototype-itself)
8. [Novelty, legal and IP](#8-novelty-legal-and-ip)

---

## 1. Summary: what is real and what is not

| Component | Status | Notes |
|---|:---:|---|
| Hybrid handshakes (X25519 + ML-KEM, Ed25519 + ML-DSA) | ✅ real | FIPS 203/204 object sizes asserted in tests |
| AEAD, per-packet Ed25519, epoch ML-DSA, anti-replay | ✅ real | Every packet is encrypted, transmitted through the model, verified and decrypted |
| CADA-AASM controller, hysteresis, clinical floor | ✅ real | Unit- and integration-tested |
| Laplace DP, Mondrian (K, L), verifier | ✅ real | Independent verifier on every release |
| Audit chain, JWT, PBKDF2, RBAC | ✅ real | Server-side enforcement on REST and sockets |
| Loopback RTT and host CPU probes | ✅ real | Fixed baselines during evaluation for reproducibility |
| Network congestion in the main evaluation | ⚠️ emulated | `StressInjector` + `NetworkModel` (see §3) |
| Real shaped link (`testbed/`) | ◐ partly real | Real TCP + kernel tbf; delay is a stated hold, no random loss |
| PQ compute cost on the data path | ⚠️ not charged | Pure-Python timings would measure Python, not the algorithms |
| Patient data | ⚠️ synthetic | No real patient data is used or needed |

---

## 2. Deviations from the original project description

| Original | This implementation | Reason |
|---|---|---|
| Combine secrets with XOR, then HKDF | HKDF over `ss_classical ‖ ss_pq` with a transcript-hash salt (XOR kept as an option) | Concatenation-KDF is the standard hybrid combiner; XOR needs equal lengths and adds no transcript binding |
| "Every packet verified against both signature algorithms" | Ed25519 on every packet; ML-DSA over a hash-chain digest every *N* packets (`epoch_len`) | A 2.4–4.6 KB PQ signature on every ≈ 300 B telemetry packet is the very cost the project studies. Batch signing is a design improvement; `epoch_len = 1` reproduces the original behaviour and is the evaluation baseline |
| Handshake implied on the data path | Make-before-break re-key | Otherwise every tier change would itself violate the SLA |
| Raw probe input to the controller | Optional EWMA smoothing (`smoothing_alpha`; live UI only, off in the evaluation) | Noisy CPU readings straddling the 40 ms threshold kept resetting the persistence counter (observed and now regression-tested) |

---

## 3. Network and latency

* **The main evaluation's congestion is a model.** `StressInjector` adds RTT, jitter, CPU load, loss and a bandwidth limit on top of real loopback/CPU probes, and `NetworkModel` converts packet size and conditions into delivery latency (RTT + serialisation + per-extra-fragment queueing + one RTO if any fragment is lost + measured crypto time). The results show how the *mechanism* behaves under a stated model, **not** measured performance on a hospital network.
* **The real-link testbed weakens the headline result.** On two network namespaces with kernel tbf shaping and real TCP, **no configuration violated the SLA at ≥ 2 Mbit/s**, so the emulated 7.4 % → 4.1 % improvement over static Tier 5 is **not reproduced** at those rates. The emulator's fragment-queueing and loss terms, not the wire bytes alone, produced it. Adaptation mattered only on very thin links (0.5 Mbit/s: static T5 failed every cycle, CADA 13 %, static T3 0 %), and at 1 Mbit/s CADA was slightly **worse** than both static configurations because of the transition cost.
* **What the testbed still emulates:** propagation delay (a stated per-phase receiver hold), random packet loss (kernel `netem` was unavailable; veth is lossless), multi-hop paths and competing traffic. Only 2 CPU cores were available.
* **Stress presets are author-chosen.** Different presets would move the numbers; the bandwidth × loss sweep exists to show sensitivity.

---

## 4. Cryptography

* **Reference implementations.** PQ primitives come from `kyber-py` / `dilithium-py`: pure Python, functionally correct (sizes and round-trips tested), but **slow and not constant-time**. Do not use them in production. For deployment, replace the `KEM` / `DSA` dictionaries in `crypto/hybrid.py` with liboqs (`oqs-python`).
* **PQ compute is not charged to per-packet latency.** It would measure Python, not the algorithms: pure-Python ML-DSA-65 signing took ≈ 94 ms, native liboqs ≈ 0.1 ms. On-wire **size** is the effect this project isolates. Compute-bound effects on very weak devices are therefore out of scope.
* **Single-process endpoints.** Both ends of each session run in the gateway process. Identities are generated at start-up; there is no PKI, certificate chain or key rotation policy.
* **The inspector shows session keys.** This is an evaluator/teaching feature, restricted to `admin`. Remove the `inspect` permission for any non-demo use.

---

## 5. Privacy

* **Sensitivity is a modelling decision.** The Laplace guarantee depends on the stated sensitivity (Δ = 0.5 mV per sample). Per-sample ε composes across a waveform window, and the accountant tracks only naive sequential composition (no advanced / Rényi accounting).
* **Mondrian gives k-anonymity + distinct l-diversity only.** It does not protect against skewness/similarity or background-knowledge attacks. t-closeness and DP synthetic data are future work.
* **Research-path privacy varies with the network.** Tier-dependent ε/K/L is a deliberate trade-off that a data-governance reviewer may question. Mitigation: the researcher export enforces K ≥ 5, L ≥ 3 regardless of tier, and refuses to release if verification fails.
* **Synthetic data.** The ECG is a sum-of-Gaussians PQRST model; EHR rows are random. Real data distributions could give different information-loss figures.

---

## 6. Evaluation and statistics

* **Conclusions come from the model in §3.** Read the "Reading" column of the evaluation report: the generator does not assume the adaptive result is better.
* **Probes are fixed during evaluation** (0.2 ms, 5 %), so parallel workers do not perturb the controller. This removes real host noise from the comparison.
* **Testbed statistics are descriptive.** With n = 4 pairs, the smallest attainable two-sided Wilcoxon p is 0.125, so no testbed difference can reach p < 0.05.
* **A negative result.** Batch ML-DSA signing alone removes most of the latency problem; after it, steering is latency-neutral. The adaptive controller's remaining value is joint privacy/crypto adaptation and stronger protection when the budget allows.
* **A discarded run.** A first full testbed run used a 16 KB token bucket and was discarded because the link never became the bottleneck; the shaper now uses a ≈ 1 MTU bucket. This is documented in the testbed report.

---

## 7. Deployment and security of the prototype itself

* **Demo secrets.** `JWT_SECRET`, `AUDIT_HMAC_KEY` and the `*_PW` passwords have development defaults. Set all of them through environment variables for anything beyond a local demo.
* **No TLS.** The Flask development server speaks plain HTTP. Run it behind a TLS-terminating reverse proxy if it is exposed beyond `localhost`.
* **Tokens.** The JWT is kept in `sessionStorage` and sent as a bearer header. There is no refresh or revocation; tokens expire after 8 h.
* **Development server.** Werkzeug runs with `allow_unsafe_werkzeug=True` for the demo; use a production WSGI/ASGI server for real deployments.
* **Single node.** All state (gateway, audit log, sessions) lives in one process; there is no high availability or horizontal scaling.

---

## 8. Novelty, legal and IP

* **Do not claim "adaptive PQC".** Runtime-adaptive PQC selection already exists (AdaptiveQKE, CAAP, Q-PRADAX), and adaptive privacy budgets exist (ALPINE). The defensible claim is the **joint coupling** of transport crypto and privacy parameters under one latency budget with a raw-PHI floor. See [`RELATED_WORK.md`](RELATED_WORK.md).
* **The literature search is not systematic.** It was an open-web, abstract-level, single-reviewer search; see [`LITERATURE_REVIEW.md`](LITERATURE_REVIEW.md) for its protocol and limits.
* **Drafts, not legal advice.** `LaTeX_Sources/` contains a *draft* paper and a *draft* patent specification. The patent draft has **not** been updated for the corrected Q-PRADAX / ALPINE descriptions and still needs a systematic prior-art search and review by a registered patent agent.
