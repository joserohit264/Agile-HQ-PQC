# Literature review

> Source: section 5 of [`REPORT.md`](REPORT.md), copied without change (the report was updated to the same wording). Reference numbers follow section 8 of the report; the full list is in [`REFERENCES.md`](REFERENCES.md). The positioning summary is in [`RELATED_WORK.md`](RELATED_WORK.md).

## Method

- **Database:** IEEE Xplore only, papers published from 2023 to 2026, together with the NIST guidance \[3\].
- **Searches:** four, covering post-quantum cryptography in healthcare, adaptive crypto-agility, differential privacy for medical data, and post-quantum TLS performance. About 20 candidates came back and 18 were kept for relevance.
- **Reading:** the full text of all 18 papers was read.
- **Reviewer:** one.
- **Status:** not a systematic review. The research gap holds for these 18 papers and the seven non-IEEE works in section 8.3 of the report, not for all published work.

## 5.1 What each paper does

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

## 5.2 Positioning against this work

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

## 5.3 Research gap

- **No paper joins post-quantum cryptography and privacy.** Of the 18, none sets a differential-privacy or anonymity parameter together with a post-quantum suite. The healthcare papers \[4\], \[5\], \[8\], \[9\] protect transport or storage with fixed settings. The privacy papers \[17\]–\[21\] never touch the transport cipher.
- **Run-time adaptation is thin.** Only \[6\] (rule-based, one device) and \[10\] (UAV simulation) adapt post-quantum settings at run time. Neither is for healthcare, neither adapts privacy, and neither is tested on a shaped link. Adaptive privacy \[17\], \[18\], \[21\] reacts to training, not to network latency, and \[21\] is theory only. \[20\] sets its budgets once per dataset, so it does not adapt at run time.
- **Floors are soft or absent.** \[10\] allows its security floor to drop under load and lists formal floor checks as future work. This project holds raw clinical data at NIST Category 3 or above, and the floor held in every trial.
- **Network evidence is mostly static.** The cost studies \[7\], \[11\]–\[15\] measure one fixed configuration at a time. \[7\] finds that computation, not bandwidth, caused the 4.7 times handshake penalty, and \[14\] shows resumption cuts connection cost by up to 73%. Both point to long-lived sessions, which fits the make-before-break re-keying here. They also expose a limit: this project's real-link test does not charge post-quantum computation to latency.
- **Not novel:** run-time selection of post-quantum settings exists \[6\], \[10\], \[24\]–\[26\], and so do adaptive or data-driven privacy budgets \[18\], \[20\], \[21\], \[27\]. This project does not claim either.
- **Claimed gap:** joint control of transport cryptography and privacy through one latency budget, with a hard floor for raw clinical data, evaluated on emulated and real shaped links. A 2026 survey lists this direction as open \[28\].

