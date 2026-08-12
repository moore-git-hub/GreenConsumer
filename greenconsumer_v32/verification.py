"""当前 v3.2 的最小核心回归测试集合。

历史 Task001–Task005 测试已经从 clean branch 移除；这里只保留直接覆盖
当前情境、购买机制、runtime 和 LLM audit 的六组测试。
"""
from __future__ import annotations

import subprocess
import sys

from .config import PROJECT_ROOT

V32_TESTS = (
    "tests/test_task005_fmcg_scenario_v32.py",
    "tests/test_task005_purchase_mechanism_v3.py",
    "tests/test_task005_purchase_mechanism_v31.py",
    "tests/test_task005_purchase_mechanism_v32.py",
    "tests/test_task005_fmcg_runtime_v32.py",
    "tests/test_task005_fmcg_audited_router_v32.py",
)


def verify_tests() -> dict:
    """顺序运行六组测试；首个失败即停止，且不会调用真实 LLM。"""
    rows = []
    for rel in V32_TESTS:
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(PROJECT_ROOT / rel)],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        rows.append(
            {
                "test": rel,
                "returncode": proc.returncode,
                "status": "PASS" if proc.returncode == 0 else "FAIL",
                "stdout_tail": (proc.stdout or "")[-1200:],
                "stderr_tail": (proc.stderr or "")[-1200:],
            }
        )
        if proc.returncode != 0:
            break

    return {
        "schema_version": "task005_fmcg_v32_clean_verify1.1",
        "status": "PASS" if len(rows) == len(V32_TESTS) and all(r["returncode"] == 0 for r in rows) else "FAIL",
        "tests_planned": len(V32_TESTS),
        "tests_run": len(rows),
        "results": rows,
        "real_llm_calls": 0,
        "external_api_calls": 0,
    }
