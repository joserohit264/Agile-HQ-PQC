#!/usr/bin/env python3
"""Launcher.  python run.py          -> web command center on http://127.0.0.1:5000
              python run.py --demo   -> headless terminal demo"""
import sys
if "--demo" in sys.argv:
    sys.argv.remove("--demo")
    import runpy; runpy.run_path("demo/run_gateway_demo.py", run_name="__main__")
else:
    from agile_hq_pqc.web.app import main
    main()
