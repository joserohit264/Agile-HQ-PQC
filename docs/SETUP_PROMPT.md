# One-shot local setup prompt

> **What this is:** a complete, self-verifying setup checklist for Agile-HQ-PQC. It is written as a prompt you can paste into **Claude Code** (or any coding agent) so it runs end to end and reports back, and a person can follow it by hand just as well.
>
> **Where to run it:** in the folder that contains the project zip (or the already-unpacked project).
>
> **Expected results at a glance:** `65 passed` · `/healthz` → `{"ok":true}` · `/` serves the React app · `/legacy` → **404** (the old UI was removed) · admin sees a **▶ Run demo** button.

````text
You are setting up the project "Adaptive Quantum-Safe Security and Privacy for Healthcare Data"
(system name: Agile-HQ-PQC) on my local machine. Work autonomously, verify each step, and stop
only if a step fails twice. Do NOT modify any project source code; if something fails, diagnose
and report the cause and the exact fix instead of editing code.

CONTEXT
- The project ships as a zip (e.g. agile-hq-pqc-v5.zip) in the current folder, or is already
  unpacked here. It contains a Python 3 Flask + Socket.IO backend (package agile_hq_pqc), a
  prebuilt React 18 + Vite + Recharts frontend already compiled into agile_hq_pqc/web/static/app/,
  65 pytest tests, a 30-trial evaluation script, LaTeX sources, and an optional Linux-only
  network-namespace testbed (testbed/).
- The React app is the only UI. The old vanilla-JS UI and its /legacy route were removed.
- It is software only. No hardware is needed.

STEP 0 - Detect environment and report
- Print OS, CPU cores, and versions of python3 (need >= 3.10; tested on 3.10 and 3.13), pip,
  node (need >= 18, only for rebuilding the frontend), npm, and pdflatex (optional).
- If Python < 3.10 is the only one present, tell me how to install a newer one and stop.

STEP 1 - Unpack
- If only the zip is present: unzip it into a new folder, e.g.  unzip agile-hq-pqc-v5.zip -d agile-hq-pqc
  then cd into the folder that contains run.py and requirements.txt (the zip may or may not have
  a top-level folder; check). If the project is already unpacked, just cd into it.
- If frontend/node_modules came out of the zip, ignore it: it is platform-specific and may have
  lost its execute permissions. It is only needed for STEP 6, which recreates it.
- Read README.md and docs/LIMITATIONS.md first.

STEP 2 - Python environment
- python3 -m venv .venv ; activate it (Windows: .venv\Scripts\activate).
- pip install --upgrade pip ; pip install -r requirements.txt
  (flask, flask-socketio, simple-websocket, cryptography, PyJWT, numpy, psutil, kyber-py,
  dilithium-py, scipy, matplotlib, pytest).
- Verify: python -c "import flask, flask_socketio, jwt, numpy, psutil, kyber_py, dilithium_py, cryptography"

STEP 3 - Run the test suite
- python -m pytest -q   -> expect "65 passed" (about 5-20 s). If any test fails, show the full
  failure output and diagnose; do not skip tests.

STEP 4 - Start the web app
- python run.py   (serves http://127.0.0.1:5000). On macOS port 5000 is often taken by AirPlay
  Receiver; if so run:  PORT=5001 python run.py   (Windows PowerShell: $env:PORT=5001; python run.py)
  Run it in the background (or a second terminal) so you can keep working.
- Check:
    curl -s http://127.0.0.1:5000/healthz                       -> {"ok":true}
    curl -s http://127.0.0.1:5000/ | grep -c 'id="root"'        -> 1   (the React page)
    curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/legacy   -> 404 (expected: removed)
- Open the app in my browser. Sign in with each demo persona and confirm the visible tabs:
    admin / admin@pqc          -> Overview, Live, Security Lab, Privacy, Data Sharing, Results, Audit
    auditor / audit@pqc        -> Overview, Live, Results, Audit
    researcher / research@pqc  -> Overview, Privacy, Data Sharing, Results
    operator / operator@pqc    -> Overview, Live, Privacy, Data Sharing, Results
  Only admin should see the "▶ Run demo" button in the header.
- As admin, check the guided demo: on the Live tab click "▶ Simulate Heavy Load" and confirm the
  header tier badge moves TIER 5 -> 3 -> 1 during stress, the "Clinical PHI" node never shows a
  tier below Tier 3 (it shows "Safety floor holding" while research is at Tier 1), and the badge
  returns to TIER 5 afterwards (the demo takes about 23 s).
- As admin, check the tamper lab: on the Security Lab tab click "⚡ Inject bit-flip" and confirm
  the verdict reads "Gateway REJECTED the forged packet" and "Control (untampered) packet
  verifies: yes".
- As admin, check the autopilot: click "▶ Run demo" and confirm it walks through 5 steps
  (Introduction, Heavy-load demo, Tamper Lab, Privacy sliders, Evaluation results) and ends with
  "Demo complete" (about 75 s). "■ Stop" must close the panel and leave the Live tab showing
  "no stress injected".
- If you can drive a headless browser (e.g. Playwright), do these checks automatically and report
  any console errors; otherwise tell me exactly what to look for.

STEP 5 - Optional headless demo
- python run.py --demo --fast   (terminal demo; add --static for the static-Tier-5 baseline).
  Expect a per-cycle table, then counters and "audit chain: {'ok': True, ...}".

STEP 6 - Optional: rebuild the frontend (only if I ask to change the UI)
- cd frontend && rm -rf node_modules && npm install && npm run build
  (writes into agile_hq_pqc/web/static/app/; Flask serves the new build without a restart).
- For live UI development: terminal A: python run.py ; terminal B: cd frontend && npm run dev
  (Vite on http://localhost:5173 proxies /api and /socket.io to Flask on :5000).

STEP 7 - Optional: reproduce the emulated evaluation (slow)
- python evaluation/run_eval.py   (about 17 min on 2 cores; writes reports/, figures fig1-fig5).
  Ask me before running; use screen/tmux or run in background and poll.
  Then: python evaluation/make_tex_tables.py  (refreshes LaTeX_Sources/results_tables.tex).

STEP 8 - Optional: compile the paper and patent PDFs (needs a LaTeX install)
- cd LaTeX_Sources ; pdflatex paper && bibtex paper && pdflatex paper && pdflatex paper ; pdflatex patent
  Pre-built PDFs are already in Compiled_PDFs/.

STEP 9 - Optional, Linux + root only: real-link testbed
- Skip entirely on macOS/Windows. On Linux as root with a kernel that has the "tbf" qdisc:
  pip install pyroute2 ; sudo -E env "PATH=$PATH" python testbed/run_testbed.py --quick
  (quick smoke run), then python testbed/analyze.py. The full run (--reps 4 --sweep-reps 4) takes
  ~35 min. Native liboqs timings (testbed/bench_native_oqs.py) need liboqs built from source plus
  `pip install liboqs-python` and LD_LIBRARY_PATH pointing at liboqs/build/lib - skip unless I ask.

SECURITY NOTES TO REMIND ME OF
- Demo passwords and default secrets are for local demos only. For anything beyond localhost set
  JWT_SECRET, AUDIT_HMAC_KEY, ADMIN_PW, AUDITOR_PW, RESEARCHER_PW, OPERATOR_PW as environment
  variables and run behind a TLS-terminating proxy.
- PQ libraries here (kyber-py, dilithium-py) are pure-Python reference code: not constant-time,
  not for production.

KNOWN GOTCHAS (check these before declaring failure)
- "Address already in use": change PORT.
- Port 5000 blocked on macOS: use PORT=5001.
- GET / returns 503 "Frontend not built": agile_hq_pqc/web/static/app/ is missing; run STEP 6.
- /legacy returns 404: expected, the old UI was removed. This is NOT a failure.
- "sh: vite: Permission denied" during npm run build: node_modules was copied from another
  machine or extracted without execute bits; delete frontend/node_modules and run npm install.
- Socket.IO shows "○ offline": make sure you opened the URL served by run.py (or the Vite proxy),
  and that no corporate proxy blocks websockets (it falls back to polling).
- data/audit.jsonl is created on first run; delete it (with the server stopped) to reset the log.
- Evaluation numbers vary slightly by CPU; the controller logic is deterministic in tests.

FINAL REPORT (required, concise)
1. Table: step, command run, result (OK / FAILED / SKIPPED), notes.
2. Test count and result, URL where the app is running, which logins were verified.
3. Any deviations, warnings, or things I must do manually.
4. The exact commands I should use next time to start the app (one-liner for my OS).
````

## Packaging the project for someone else

Build the zip **from the project folder**, leaving out everything that is generated, machine-specific or private:

```bash
cd agile-hq-pqc            # the folder that contains run.py
zip -r ../agile-hq-pqc.zip . \
  -x '.venv/*' 'frontend/node_modules/*' '*/__pycache__/*' '__pycache__/*' '*.pyc' \
     '.pytest_cache/*' 'data/*' '*.zip'
```

| Excluded | Why |
|---|---|
| `.venv/` | Recreated by STEP 2; contains absolute paths |
| `frontend/node_modules/` | ≈ 90 MB, platform-specific binaries (e.g. `@esbuild/linux-x64`), and extractors such as Windows Explorer or Python's `zipfile` drop its execute bits, which causes `vite: Permission denied`. Recreated by `npm install` |
| `__pycache__/`, `*.pyc`, `.pytest_cache/` | Generated caches |
| `data/` | `audit.jsonl` is a runtime log (logins, demo runs); it is recreated on first start |
| `*.zip` | Avoids nesting an older archive inside the new one |

The prebuilt frontend in `agile_hq_pqc/web/static/app/` **is** included, so the recipient needs only Python to run the app.
