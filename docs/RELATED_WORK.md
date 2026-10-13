# Related work and positioning

> Source: sections 5.2 and 5.3 of [`REPORT.md`](REPORT.md), copied without change. What each paper does, and how the survey was done, are in [`LITERATURE_REVIEW.md`](LITERATURE_REVIEW.md). Reference numbers follow [`REFERENCES.md`](REFERENCES.md).

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

