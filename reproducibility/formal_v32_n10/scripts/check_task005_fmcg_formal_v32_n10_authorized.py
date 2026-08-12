from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
proc = subprocess.run(
    [
        sys.executable,
        str(ROOT / "activate_task005_fmcg_formal_v32_n10.py"),
        "--check-only",
    ],
    cwd=ROOT,
    text=True,
    capture_output=True,
    check=False,
)
print(proc.stdout, end="")
if proc.stderr:
    print(proc.stderr, file=sys.stderr, end="")
raise SystemExit(proc.returncode)
