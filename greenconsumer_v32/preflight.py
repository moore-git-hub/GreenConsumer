from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys

from .config import PROJECT_ROOT


def ensure_dashscope_key() -> bool:
    """Bridge Windows user-scope key into this process without printing it."""
    value = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if value and not value.startswith("__"):
        return True
    if os.name != "nt":
        return False
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "[Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    candidate = (proc.stdout or "").strip()
    if candidate and not candidate.startswith("__"):
        os.environ["DASHSCOPE_API_KEY"] = candidate
        return True
    return False


REQUIRED_IMPORTS = (
    "agentkernel_standalone",
    "numpy",
    "pandas",
    "networkx",
    "yaml",
)


def run_preflight(*, require_real_llm: bool = False) -> dict:
    missing = []
    for name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(name)
        except Exception as exc:
            missing.append({"module": name, "error": type(exc).__name__})

    model_path = PROJECT_ROOT / "configs" / "models_config.yaml"
    model_ok = False
    if model_path.exists():
        model_text = model_path.read_text(encoding="utf-8-sig")
        model_ok = (
            "model: qwen-plus" in model_text
            and "temperature: 0.3" in model_text
            and "__FROM_ENV_DASHSCOPE_API_KEY__" in model_text
        )

    key_present = ensure_dashscope_key() if require_real_llm else False
    status = "PASS"
    if missing or not model_ok or (require_real_llm and not key_present):
        status = "FAIL"

    return {
        "schema_version": "task005_fmcg_v32_clean_preflight1.0",
        "status": status,
        "python": sys.version.split()[0],
        "project_root": str(PROJECT_ROOT),
        "missing_dependencies": missing,
        "model_config_verified": model_ok,
        "real_llm_required": require_real_llm,
        "dashscope_api_key_present": key_present if require_real_llm else "not-required",
        "external_api_calls": 0,
        "real_llm_calls": 0,
    }


def print_preflight(*, require_real_llm: bool = False) -> int:
    payload = run_preflight(require_real_llm=require_real_llm)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2
