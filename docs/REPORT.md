# Adaptive Quantum-Safe Security and Privacy for Healthcare Data

Oct 11, 2026 · @Jose

## 1. Project Title

**Adaptive Quantum-Safe Security and Privacy for Healthcare Data**

| Item | Detail |
| --- | --- |
| System name | Agile-HQ-PQC |
| Controller | CADA-AASM (Context-Aware Dynamic Agility and Adaptive Anonymization Steering Matrix) |
| Programme | M.Tech (CSE, Cybersecurity) |
| Student | Jose Rohit M |
| Guide | Dr. Karthikeyan Jayaraman |
| Institution | School of Computer Science Engineering and Information Systems (SCORE), VIT Vellore |

## 2. Problem Statement

A hospital must protect patient data against future quantum attacks and also de-identify it for research, but stronger protection costs time that real-time patient monitoring does not have.

**Why protection is now urgent.** Clinical data such as genomes stays sensitive for decades, so an adversary can record encrypted traffic today and decrypt it once a quantum computer exists ("harvest now, decrypt later"). NIST has standardised the replacements, ML-KEM for key establishment \[1\] and ML-DSA for signatures \[2\].

**Why it is costly.** The new objects are far larger than the classical ones they replace. An ML-DSA-87 signature is 4,627 bytes against 64 bytes for Ed25519, and an ML-KEM-1024 ciphertext is 1,568 bytes against 32 bytes for X25519. A signed ICU telemetry packet therefore spans several Ethernet frames, which hurts most when the network is congested. Streaming telemetry tolerates only about 200 ms end to end.

**Why it is not solved.** Data released for research must also be de-identified, using differential privacy for signals and (K, L)-anonymity for records. Today, transport security and data privacy are configured separately, and neither reacts to live network conditions. A fixed maximum-strength setting risks missing the 200 ms deadline on weak links, while a fixed weak setting leaves patients exposed.

**Problem to solve.** How can a healthcare gateway choose, at run time and without human intervention, the strongest combination of post-quantum transport protection and privacy parameters that still meets the latency budget, while never lowering the protection of raw patient data below a safe minimum?

## 3. Abstract

This project treats quantum-safe transport security and data privacy as one latency-constrained trade-off, and builds a gateway that picks the strongest protection the network can currently afford.

A controller, CADA-AASM, computes a live latency budget L = 200 − RTT − 0.5 · CPU and maps it to one of three tiers. Each tier fixes together a post-quantum key-encapsulation parameter set, a signature parameter set, a data cipher, a differential-privacy parameter ε and anonymity parameters K and L. A three-cycle persistence filter prevents cipher flapping, and raw clinical telemetry is held at NIST Category 3 or above whatever the congestion. Sessions are re-keyed make-before-break, and post-quantum signatures are batched per epoch.

In 30 paired trials under an emulated congestion model, steering cut SLA violations during stress against static Tier 5 (clinical 7.4% to 4.1%, research 6.9% to 2.9%, p < 10⁻⁴) and cut tier changes by 65%. A real-link validation, using Linux network namespaces, kernel bandwidth shaping and real TCP, did **not** reproduce that gain at 2 Mbit/s and above. It showed that adaptation matters only on very thin links: at 0.5 Mbit/s static Tier 5 failed on every cycle, adaptive on 13%, and static Tier 3 on none. The distinctive contribution is therefore the joint, safe adaptation of cryptographic and privacy parameters under a compliance floor, not a latency win. The system is open, software-only and covered by 250 automated tests (65 core integration + 185 KAT and tier security tests), with a React operator console.

## 4. Objectives

The project has one aim: to keep quantum-safe protection and privacy as strong as the network allows, without ever dropping below a safe floor for raw patient data. It is broken into seven objectives.

1. **Joint model.** Define three protection levels (High, Medium, Low; Tier 5, 3, 1) that bind the key-encapsulation set, signature set, data cipher, differential-privacy ε and anonymity (K, L) together.
2. **Closed-loop controller.** Build CADA-AASM, which turns a measured latency budget into a tier, with a persistence filter against cipher flapping.
3. **Safety floor.** Hold raw clinical telemetry at NIST Category 3 or above under any congestion, and enforce K ≥ 5, L ≥ 3 with independent verification on every research export.
4. **Secure channel.** Implement a hybrid X25519 + ML-KEM handshake, make-before-break re-keying, and per-packet Ed25519 plus per-epoch ML-DSA signatures.
5. **Governance.** Provide role-based access (admin, auditor, researcher, operator), a tamper lab and a tamper-evident audit log.
6. **Honest evaluation.** Measure against static baselines with paired statistics, an ablation and a bandwidth sweep, then validate on a real shaped network link and measure native cryptographic cost.
7. **Usable artefact.** Deliver an open, tested implementation with a React operator console and a guided heavy-load demo.

**Success criteria:** the floor holds in every trial; the evaluation states plainly where adaptation helps and where it does not; and all 250 automated tests pass.

## 5. Literature Survey

The survey reads 18 papers from IEEE Xplore, all published from 2023 to 2026, together with the NIST guidance \[3\].

**How the survey was done.** Four IEEE Xplore searches covered post-quantum cryptography in healthcare, adaptive crypto-agility, differential privacy for medical data, and post-quantum TLS performance. About 20 candidates came back and 18 were kept for relevance. The full text of each of the 18 papers was then read, so the table below reports what each paper does and what it measured. The search was a single reviewer working on IEEE Xplore only, so the survey is not a systematic review, and the research gap below holds for these 18 papers and the seven non-IEEE works in section 8.3, not for all published work.

### 5.1 What each paper does

| Ref | Paper (venue, year) | What it does | Result or limit that matters here |
| --- | --- | --- | --- |
| \[4\] | El-Hadedy et al., DCAS 2024 | Kyber and ASCON on a Kubernetes (K3S) cluster of small ARM boards for IoMT | Kyber512 encapsulation took 3,464 µs. Power rose from 4.49 W to 32.5 W. The algorithm is chosen once per deployment. |
| \[5\] | Yadav et al., IEEE AIC 2023 | Ring-LWE and PUF authenticated key exchange for IoMT, assisted by blockchain and fog nodes | Security analysis and computation and communication cost analysis. No load or latency adaptation. |
| \[6\] | Sinaga et al., ICCIT 2025 | Rule-based tuning of Kyber and Saber parameters from CPU and RAM load | Light variants (Kyber512, Saber-Light) are accepted under full load and heavier ones rejected. One device with software limits, no network, no privacy. Saber is not a NIST standard. |
| \[7\] | Santos et al., ISDFS 2026 | ML-KEM-768 and ML-DSA-65 hybrid TLS for MQTT, emulated ARM64 with 0.2% loss and 30 ms jitter | Connection setup took 212 ms against 44 ms classical (4.7 times). The cost was computation, not bandwidth. Later publishing was negligible. |
| \[8\] | Karthikeyan, GCITC 2023 | RSA with Twofish plus NTRUEncrypt, deep-learning key selection, watermarking and blockchain for medical images | Reports a 50 to 75% cut in encryption overhead. Uses NTRU, not a NIST-standardised scheme. No network adaptation. |
| \[9\] | Zhukabayeva et al., IEEE Access 2024 | Hash-based post-quantum cryptography on Hyperledger Fabric for patient records | Discrete-event simulation of transactions, requests and encryption. No real network. |
| \[10\] | Aydeger and Carvalho, IEEE CCNC 2026 | Cryptographic agility for UAV swarms, 600 simulated missions | At 50 UAVs, static high security met 7.5% of deadlines while agile and static low met 90%. Security floors are soft and may be dropped under load. |
| \[11\] | Ojetunde et al., IEEE CCNC 2025 | PQC and PQC-AES hybrid public-key protocols over a wireless file transfer | Kyber1024 and BIKE-L1 matched AES-256 throughput (about 0.14 Mbit/s) for 1 KB files. Static choices. |
| \[12\] | Lokesh, NMITCON 2025 | Kyber512 inside TLS 1.3 on Raspberry Pi hardware | 14.1 ms handshake and 0.36 mJ per handshake on Raspberry Pi 3. Lists crypto agility only as a table entry and describes no run-time controller. |
| \[13\] | Rubio Garcia et al., IEEE CAMAD 2023 | Triple-hybrid TLS 1.3 with classical, post-quantum and quantum key distribution | About 68% more handshake time than a classical plus post-quantum hybrid. |
| \[14\] | Catoni et al., IEEE SMARTCOMP 2025 | X25519MLKEM768 and TLS 1.3 session resumption in edge-cloud proxies | Resumption cut connection cost by up to 73%. |
| \[15\] | Rigon et al., IEEE CNS 2025 | ML-KEM, BIKE, HQC and FrodoKEM, plain and hybrid, inside QUIC | ML-KEM was the most efficient and hybrids added little. Dilithium matched classical signatures and SPHINCS+ slowed the handshake. |
| \[16\] | Reazaei et al., IEEE CSPA 2026 | Review of ML-KEM, BIKE and HQC | ML-KEM is the primary choice and HQC the standardised backup. A review, with no network test. |
| \[17\] | He, Wang and Cai, IEEE IoT Journal 2024 | Local differential privacy for clustered federated learning (ACS-FL) with adaptive clipping | Tested on image datasets, not health data. The adaptation is per layer inside training. |
| \[18\] | Yu et al., IEEE BIBM 2024 | Adaptive noise and privacy budget from gradient components in medical federated learning | Accuracy up 3.47% on RSNA-ICH. Budget follows the gradients, not the link. |
| \[19\] | Zhang et al., IEEE Healthcom 2023 | Lightweight attribute-based encryption with differential privacy for medical IoT data | Cuts computation and communication cost in simulation. Static policy. |
| \[20\] | Lyu et al., IEEE Trans. Big Data 2025 | Edge-DPSDG: synthetic medical data with budgets set by Shapley value and entropy | Up to 21.29% better accuracy than the state of the art. Budgets are set once per dataset. |
| \[21\] | Birajdar et al., ICAAIC 2025 | Dynamic privacy budget framework with Rényi accounting for medical federated learning | Theory only, with no experiments. |

### 5.2 Positioning against this work

| Ref | Healthcare | Post-quantum | Privacy (DP or anonymity) | Adapts at run time | Tested on a network |
| --- | --- | --- | --- | --- | --- |
| \[4\] | yes | yes | no | no | cluster, compute only |
| \[5\] | yes | yes | authentication privacy | no | analysis |
| \[6\] | no | yes | no | yes, CPU and RAM rules | no |
| \[7\] | no | yes | no | no | emulated |
| \[8\] | yes | yes (NTRU) | no | no | no |
| \[9\] | yes | yes | no | no | simulated |
| \[10\] | no | yes | no | yes, soft floors | simulated |
| \[11\] | no | yes | no | no | wireless test |
| \[12\] | no | yes | no | no | hardware, loss tested |
| \[13\] | no | yes | no | no | experimental network |
| \[14\] | no | yes | no | no | several conditions |
| \[15\] | no | yes | no | no | controlled |
| \[16\] | no | yes | no | no | review |
| \[17\] | no | no | yes | yes, in training | no |
| \[18\] | yes | no | yes | yes, in training | no |
| \[19\] | yes | no | yes | no | simulated |
| \[20\] | yes | no | yes | no (budgets set once per dataset) | no |
| \[21\] | yes | no | yes | yes, theory only | no |
| **This work** | **yes** | **yes** | **yes** | **yes, from latency budget** | **emulated and real shaped link** |

### 5.3 Research gap

- **No paper joins post-quantum cryptography and privacy.** Of the 18, none sets a differential-privacy or anonymity parameter together with a post-quantum suite. The healthcare papers \[4\], \[5\], \[8\], \[9\] protect transport or storage with fixed settings. The privacy papers \[17\]–\[21\] never touch the transport cipher.
- **Run-time adaptation is thin.** Only \[6\] (rule-based, one device) and \[10\] (UAV simulation) adapt post-quantum settings at run time. Neither is for healthcare, neither adapts privacy, and neither is tested on a shaped link. Adaptive privacy \[17\], \[18\], \[21\] reacts to training, not to network latency, and \[21\] is theory only. \[20\] sets its budgets once per dataset, so it does not adapt at run time.
- **Floors are soft or absent.** \[10\] allows its security floor to drop under load and lists formal floor checks as future work. This project holds raw clinical data at NIST Category 3 or above, and the floor held in every trial.
- **Network evidence is mostly static.** The cost studies \[7\], \[11\]–\[15\] measure one fixed configuration at a time. \[7\] finds that computation, not bandwidth, caused the 4.7 times handshake penalty, and \[14\] shows resumption cuts connection cost by up to 73%. Both point to long-lived sessions, which fits the make-before-break re-keying here. They also expose a limit: this project's real-link test does not charge post-quantum computation to latency.
- **Not novel:** run-time selection of post-quantum settings exists \[6\], \[10\], \[24\]–\[26\], and so do adaptive or data-driven privacy budgets \[18\], \[20\], \[21\], \[27\]. This project does not claim either.
- **Claimed gap:** joint control of transport cryptography and privacy through one latency budget, with a hard floor for raw clinical data, evaluated on emulated and real shaped links. A 2026 survey lists this direction as open \[28\].

## 6. Detailed Description

### 6.1 Background

Healthcare data stays sensitive for decades, so it must survive the arrival of quantum computers. An attacker can record encrypted traffic today and decrypt it later (harvest now, decrypt later). NIST has standardised the replacements: ML-KEM for key exchange \[1\] and ML-DSA for signatures \[2\]. Guidance for the transition recommends hybrid use of classical and post-quantum algorithms \[3\].

Post-quantum algorithms are larger and slower than the classical ones they replace. A hospital link carrying ECG streams and clinical records has a real-time budget, so the strongest setting is not always the right one. The project turns that trade-off into a run-time decision.

### 6.2 Threat model and assumptions

- **Passive quantum adversary.** Records traffic now and attacks the key exchange later. Countered by hybrid X25519 + ML-KEM.
- **Active network attacker.** Forges, modifies or replays packets. Countered by Ed25519 per packet plus ML-DSA per epoch over a hash chain.
- **Curious insider or researcher.** Tries to re-identify patients from exported data. Countered by differential privacy, (K,L)-anonymity and a researcher export floor.
- **Assumptions.** Endpoints are trusted, the underlying algorithms are secure, and the network is untrusted. The project is software-only, so hardware side channels are out of scope.

### 6.3 Two traffic domains

| Domain | Data | Policy |
| --- | --- | --- |
| Clinical | Raw PHI (ECG, EHR) | Tier is max(agile tier, 3). Never drops below NIST Category 3. |
| Research | De-identified data | Full tier range, with privacy transforms applied before export. |

### 6.4 Latency budget model

The controller measures round-trip time (RTT) and CPU load, then computes the time left for cryptography.

```latex
L = 200 - \mathrm{RTT} - 0.5\cdot \mathrm{CPU}
```

Here L is the latency budget in ms, RTT is in ms and CPU is a percentage. A large L means the link can afford strong cryptography. A small L means the link is stressed.

### 6.5 Three security levels

| Level | Trigger | KEM | Signature | Cipher | DP ε | (K, L) |
| --- | --- | --- | --- | --- | --- | --- |
| High (Tier 5) | L > 80 | ML-KEM-1024 | ML-DSA-87 | AES-256-GCM | 0.1 | (5, 3) |
| Medium (Tier 3) | 40 < L ≤ 80 | ML-KEM-768 | ML-DSA-65 | AES-256-GCM | 0.5 | (3, 2) |
| Low (Tier 1) | L ≤ 40 | ML-KEM-512 | ML-DSA-44 | ChaCha20-Poly1305 | 1.0 | (2, 2) |

Object sizes grow with the level, which is why the lower levels help on thin links.

| Level | KEM public key / ciphertext (B) | Signature public key / signature (B) |
| --- | --- | --- |
| Tier 5 | 1568 / 1568 | 2592 / 4627 |
| Tier 3 | 1184 / 1088 | 1952 / 3309 |
| Tier 1 | 800 / 768 | 1312 / 2420 |

## 7. Proposed Work and Design

### 7.1 Architecture

One controller decides the security level, and both the secure channel and the privacy engines follow that decision.

&#91;embedded content: system architecture · 5 components, 1 controller\]

### 7.2 Control algorithm

The controller runs once per cycle. It reads RTT and CPU load, computes the budget L, maps L to a tier, and applies a persistence filter so that a single noisy sample cannot trigger a switch.

```latex
\mathrm{tier}(L)=\begin{cases}5 & L>80\\ 3 & 40<L\le 80\\ 1 & L\le 40\end{cases}\qquad \mathrm{tier}_{\mathrm{clinical}}=\max(\mathrm{tier}(L),\,3)
```

A new tier is adopted only after it has been proposed for 3 consecutive cycles. The clinical domain never falls below Tier 3, so raw patient data always keeps NIST Category 3 strength. The research domain uses the full range because its data is de-identified.

### 7.3 Secure channel

1. **Hybrid key exchange.** X25519 and the ML-KEM variant of the current tier each produce a shared secret.
2. **Key derivation.** HKDF combines both secrets, salted with the transcript hash, so the session key depends on the whole handshake.
3. **Authentication.** Ed25519 and the tier's ML-DSA variant sign the handshake.
4. **Data protection.** AES-256-GCM, or ChaCha20-Poly1305 at Tier 1, protects each record.
5. **Re-keying.** When the tier changes, the new session is established before the old one is retired (make-before-break), so traffic is never interrupted.
6. **Batch signing.** Each packet carries an Ed25519 signature. ML-DSA signs once per epoch of 8 packets over a hash chain of those packets. Setting the epoch length to 1 gives the per-packet baseline.

### 7.4 Privacy engines

- **ECG streams.** Laplace noise with sensitivity Δ = 0.5 mV. A smaller ε means stronger privacy: 0.1 at Tier 5, 0.5 at Tier 3 and 1.0 at Tier 1.
- **EHR records.** Mondrian (K,L)-anonymity with K and L from the tier table. A researcher export is refused unless K ≥ 5 and L ≥ 3, and an independent check confirms it.

### 7.5 Governance and interface

- **Roles.** JWT-based access for admin, auditor, researcher and operator.
- **Audit.** Every action is written to a hash-chained HMAC log, so any edit to history is detectable.
- **Tamper lab.** Lets an operator flip bits in transit and watch the channel reject the packet.
- **Dashboard.** A React 18 interface shows the live tier, budget, charts, privacy settings and audit trail.

### 7.6 Implementation

The backend is Flask with Socket.IO. The frontend is React 18 with Vite, Recharts and socket.io-client. Cryptography uses pure-Python kyber-py and dilithium-py, plus a native liboqs 0.16.0 benchmark. The suite has 250 pytest tests (including NIST FIPS 203/204 Known Answer Tests and property-based verification), and a Linux network-namespace testbed validates behaviour on a real shaped link.

### 7.7 Evaluation

**Emulated link (30 paired trials, staged calm, moderate, heavy, severe, calm).**

| Comparison | Clinical violations | Research violations | Significance |
| --- | --- | --- | --- |
| Static Tier 5 | 7.4% | 6.9% | baseline |
| Adaptive (CADA-AASM) | 4.1% | 2.9% | p < 1e-4 vs Tier 5 |
| Adaptive vs static Tier 3 | not different | not different | p = 0.16 and 0.058 |

The persistence filter cut tier changes from 6.9 to 2.4 per run (65% fewer) and handshakes from 10.9 to 6.4. Batch signing cut wire size from about 5.0 kB to 0.9 kB with 1.1% violations. In the bandwidth and loss sweep, the gain reached about 45 percentage points at 1 Mbit/s. The clinical floor held in every trial.

**Real shaped link (Linux namespaces, veth, kernel token-bucket shaping, real TCP).**

| Constant severe stress, clinical violations | 5 Mbit/s | 2 Mbit/s | 1 Mbit/s | 0.5 Mbit/s |
| --- | --- | --- | --- | --- |
| Adaptive | 0% | 0% | 3.3% | 13.3% |
| Static Tier 5 | 0% | 0% | 0% | 100% |
| Static Tier 3 | 0% | 0% | 0% | 0% |

Under staged stress, no configuration had a violation. Mean clinical p95 latency was 159.2 ms for adaptive, 164.8 ms for static Tier 5 and 159.2 ms for static Tier 3. The minimum clinical tier was 3 in every adaptive trial. Part B used 4 repetitions, so the smallest possible Wilcoxon p-value is 0.125 and these results are descriptive.

**Native cryptographic cost (liboqs, median ms).**

| Operation | Time |
| --- | --- |
| ML-KEM-768 keygen / encaps / decaps | 0.0184 / 0.0136 / 0.0153 |
| ML-DSA-44 sign | 0.0613 |
| ML-DSA-65 sign / verify | 0.0872 / 0.0321 |
| ML-DSA-87 sign | 0.1077 |
| Pure-Python ML-DSA signing in this project | about 94 |

Wire bytes per clinical exchange averaged 5020 for Tier 5, 3702 for Tier 3 and about 932 for Tier 5 with batch signing.

### 7.8 Findings, limitations and future work

The emulated gain over static Tier 5 is not reproduced on a real link at 2 Mbit/s and above, where every configuration meets the budget. Adaptation matters only on very thin links, and a well-chosen static Tier 3 matches or beats it on latency. The defensible contribution is therefore the joint, safe adjustment of cryptography and privacy under a compliance floor, not a latency win.

Limitations: propagation delay is a stated receiver hold and random loss is not modelled; Part B has few repetitions; pure-Python cryptography is much slower than native. Future work: multi-host virtual-machine testing with kernel delay and loss, native liboqs inside the channel, and a learned controller compared against the rule-based one.

## 8. References

### 8.1 Standards and guidance

1. NIST, *FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard*, 2024.
2. NIST, *FIPS 204: Module-Lattice-Based Digital Signature Standard*, 2024.
3. E. Barker, L. Chen, D. Cooper, D. Moody, A. Regenscheid, M. Souppaya, W. Newhouse, R. Housley, S. Turner, W. Barker and K. Kent, *Considerations for Achieving Cryptographic Agility: Strategies and Practices*, NIST CSWP 39, 2025. csrc.nist.gov/pubs/cswp/39

The surveyed papers \[4\]–\[21\] are from IEEE Xplore, were published from 2023 to 2026, and were read in full. NIST CSWP 39 \[3\] has been superseded by a newer update on the NIST site. \[25\] is a student project and is not peer reviewed. Author lists follow the printed first pages. Where a paper has more authors than shown, "et al." is used.

### 8.2 IEEE Xplore papers, 2023 to 2026

4. M. El-Hadedy, P. V. Ankunda, J. Ung and W.-M. Hwu, *Securing the Internet of Medical Things (IoMT) with K3S and Hybrid Cryptography: Integrating Post-Quantum Approaches for Enhanced Embedded System Security*, 2024 IEEE 17th Dallas Circuits and Systems Conference (DCAS), 2024. doi.org/10.1109/DCAS61159.2024.10539887
5. D. K. Yadav, D. Yadav, Y. Pal, D. Chaudhary, H. Sahu and A. S. L. Manasa, *Post Quantum Blockchain Assisted Privacy Preserving Protocol for Internet of Medical Things*, 2023 IEEE World Conference on Applied Intelligence and Computing (AIC), 2023. doi.org/10.1109/AIC57670.2023.10263869
6. R. Sinaga, H. D. Purnomo, I. Sembiring, T. Wellem and A. Junaidi, *Adaptive Post Quantum Cryptography Tuning for Constrained Devices Using Kyber and Saber*, 2025 4th International Conference on Creative Communication and Innovative Technology (ICCIT), 2025. doi.org/10.1109/ICCIT65724.2025.11166918
7. E. C. Santos, T. A. O. D. Cordeiro and H. de O. Silva, *Performance Evaluation of Post-Quantum Cryptography in IoT: A Case Study on MQTT over TLS under Network Constraints*, 2026 14th International Symposium on Digital Forensics and Security (ISDFS), 2026. doi.org/10.1109/ISDFS69419.2026.11458974
8. D. Karthikeyan, *Secure Medical Data Transmission In Iot Healthcare: Hybrid Encryption, Post-Quantum Cryptography, And Deep Learning-Enhanced Approach*, 2023 Global Conference on Information Technologies and Communications (GCITC), 2023. doi.org/10.1109/GCITC60406.2023.10425954
9. T. Zhukabayeva, A. Ur Rehman, N. Tariq and E. Benkhelifa, *Hyperledger Fabric-Based Post Quantum Cryptography for Healthcare Application Using Discrete Event Simulation*, IEEE Access, 2024. doi.org/10.1109/ACCESS.2024.3513153
10. A. Aydeger and M. Carvalho, *Real-Time Cryptographic Agility for Autonomous UAV Swarms: A Performance-Driven Approach to Post-Quantum Migration*, 2026 IEEE 23rd Consumer Communications & Networking Conference (CCNC), 2026. doi.org/10.1109/CCNC65079.2026.11366545
11. B. Ojetunde, T. Kurihara, K. Yano, T. Sakano, H. Yokoyama et al., *Performance Evaluation of Post-Quantum Cryptography Algorithms for Secure Communication in Wireless Networks*, 2025 IEEE 22nd Consumer Communications & Networking Conference (CCNC), 2025. doi.org/10.1109/CCNC54725.2025.10975932
12. B. S. Lokesh, *Integrating Post-Quantum Cryptography in Transport Layer Security 1.3 for IoT: A Performance Analysis on Resource-Constrained Hardware*, 2025 Third International Conference on Networks, Multimedia and Information Technology (NMITCON), 2025. doi.org/10.1109/NMITCON65824.2025.11188356
13. C. Rubio Garcia, A. Cano Aguilera and J. J. Vegas Olmos, *Quantum-Resistant TLS 1.3: A Hybrid Solution Combining Classical, Quantum and Post-Quantum Cryptography*, 2023 IEEE 28th International Workshop on Computer Aided Modeling and Design of Communication Links and Networks (CAMAD), 2023. doi.org/10.1109/CAMAD59638.2023.10478407
14. L. Catoni, C. Puliafito and G. Dini, *Fast and Secure Service Continuity in the Edge-Cloud Continuum: A Study of TLS 1.3 Resumption and Post-Quantum Key Exchange*, 2025 IEEE International Conference on Smart Computing (SMARTCOMP), 2025. doi.org/10.1109/SMARTCOMP65954.2025.00115
15. P. Rigon, H. Fu, W. Cordeiro and C. Fung, *Comprehensive Post-Quantum Cryptography Performance Evaluations for QUIC Protocol*, 2025 IEEE Conference on Communications and Network Security (CNS), 2025. doi.org/10.1109/CNS66487.2025.11195046
16. P. Reazaei, A. S. K. Rashid, A. Afzalian Mand, M. Saberikamarposhti et al., *Post-Quantum Key Encapsulation Mechanisms: A Comparative Review of ML-KEM, BIKE, and HQC*, 2026 22nd IEEE International Colloquium on Signal Processing & Its Applications (CSPA), 2026. doi.org/10.1109/CSPA68262.2026.11517877
17. Z. He, L. Wang and Z. Cai, *Clustered Federated Learning With Adaptive Local Differential Privacy on Heterogeneous IoT Data*, IEEE Internet of Things Journal, vol. 11, no. 1, p. 137, 2024.
18. Z. Yu, Z. Lu, S. Lu, Y. Cui, X. Tang and J. Wu, *Adaptive Differential Privacy via Gradient Components in Medical Federated Learning*, 2024 IEEE International Conference on Bioinformatics and Biomedicine (BIBM), 2024. doi.org/10.1109/BIBM62325.2024.10822141
19. P. Zhang, T. Wu, J. Yang, J. Wang and Z. Zhang, *Lightweight Bidirectional Differential Privacy Protection Method for Privacy-Sensitive Data in Medical Internet of Things*, 2023 IEEE International Conference on E-health Networking, Application & Services (Healthcom), 2023. doi.org/10.1109/HEALTHCOM56612.2023.10472379
20. M. Lyu, Z. Ni, Q. Chen and F. Li, *Edge-DPSDG: An Edge-Based Differential Privacy Protection Model for Smart Healthcare*, IEEE Transactions on Big Data, vol. 11, no. 1, p. 21, 2025.
21. G. Birajdar, V. Narawade and S. Bhanre, *Dynamic Privacy Budget Allocation in Federated Learning for Medical Image Analysis: A Comprehensive Review and Framework Proposal*, 2025 4th International Conference on Applied Artificial Intelligence and Computing (ICAAIC), 2025. doi.org/10.1109/ICAAIC64647.2025.11330959

### 8.3 Other 2023-and-later works (not on IEEE Xplore, used for the novelty check)

22. A. Alif, K. F. Hasan, B. Palaniswamy and M. M. Islam, *A Framework for Post Quantum Migration in IoT-Based Healthcare Systems*, arXiv:2604.15584, 2026.
23. P. Kampanakis and W. Childs-Klein, *The impact of data-heavy, post-quantum TLS 1.3 on the time-to-last-byte of real-world connections*, Proc. MADweb (NDSS Workshop), 2024; IACR ePrint 2024/176.
24. S. Ben Othman and G. Kumar, *Quantum-resilient and adaptive multi-region data aggregation for IoMT using zero-knowledge proofs and edge intelligence* (Q-PRADAX), Scientific Reports 15:37176, 2025. doi.org/10.1038/s41598-025-22457-6
25. H. Ajjour, W. Abdalaal, H. Nasrallah and F. Rajab, *AdaptiveQKE: Adaptive selection of hybrid post-quantum key-exchange groups for TLS 1.3*, GitHub HebaAj/AdaptiveQKE, 2025 (B.Sc. graduation project, not peer reviewed).
26. P. Sengupta, M. Raikwar, S. Maharjan, F. Eliassen and Y. Zhang, *Adaptive Quantum-Safe Cryptography for 6G Vehicular Networks via Context-Aware Optimization* (CAAP), arXiv:2602.01342, 2026.
27. G. Cheng, S. Liu, X. Zhao, Y. Chen, J. Huang, L. Kong and S. Deng, *ALPINE: Closed-Loop Adaptive Privacy Budget Allocation for Mobile Edge Crowdsensing*, arXiv:2510.17162, 2025.
28. Z. Zaman, P. Gauravaram, M. Hassan, S. Jha and W. Hu, *Privacy-Preserving Machine Learning for IoT: A Cross-Paradigm Survey and Future Roadmap*, arXiv:2603.13570, 2026.

### 8.4 Foundational methods (before 2023, cited only for the techniques used)

29. C. Dwork, F. McSherry, K. Nissim and A. Smith, *Calibrating Noise to Sensitivity in Private Data Analysis*, Proc. TCC, 2006.
30. K. LeFevre, D. J. DeWitt and R. Ramakrishnan, *Mondrian Multidimensional k-Anonymity*, Proc. IEEE ICDE, 2006.
31. L. Sweeney, *k-Anonymity: A Model for Protecting Privacy*, Int. J. Uncertainty, Fuzziness and Knowledge-Based Systems 10(5):557–570, 2002.
32. A. Machanavajjhala, D. Kifer, J. Gehrke and M. Venkitasubramaniam, *ℓ-Diversity: Privacy Beyond k-Anonymity*, ACM TKDD 1(1), 2007.
