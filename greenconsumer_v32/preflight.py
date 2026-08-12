"""运行前零调用检查。

检查 Python 依赖、模型配置和（可选）DashScope API key。该模块本身不会
向任何外部模型发请求。
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys

from .config import PROJECT_ROOT

REQUIRED_IMPORTS = (
    "agentkernel_standalone",
    "numpy",
    "pandas",
    "networkx",
    "yaml",
)


def ensure_dashscope_key() -> bool:
    """确保当前进程能读取 DASHSCOPE_API_KEY，但绝不打印 key。

    Windows 下若当前进程没有变量，会尝试读取 User scope 环境变量并桥接
    到当前 Python 进程。
    """
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


def run_preflight(*, require_real_llm: bool = False) -> dict:
    """执行零 API 预检并返回机器可读结果。"""
    missing = []
    for name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(name)
        except Exception as exc:
            missing.append({"module": name, "error": type(exc).__name__})

    # 模型文件只能保存占位符，不允许把 API key 写进 Git。
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
        "schema_version": "task005_fmcg_v32_clean_preflight1.1",
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
    """打印预检 JSON，并以 shell-friendly return code 表示 PASS/FAIL。"""
    payload = run_preflight(require_real_llm=require_real_llm)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2
