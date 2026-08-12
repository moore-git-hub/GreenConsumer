from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import types
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import run_experiments


P = 0
F = 0


def check(name: str, condition: bool, actual=None) -> None:
    global P, F
    if condition:
        P += 1
        print("PASS", name)
    else:
        F += 1
        print("FAIL", name, actual)


def _load_config():
    return yaml.safe_load((ROOT / "configs" / "models_config.yaml").read_text(encoding="utf-8"))


def _chat_entry(conf):
    entries = conf if isinstance(conf, list) else [conf]
    for entry in entries:
        if isinstance(entry, dict) and "chat" in (entry.get("capabilities") or []):
            return entry
    return entries[0]


def _install_fake_router_modules(captured: dict):
    module_names = [
        "agentkernel_standalone",
        "agentkernel_standalone.toolkit",
        "agentkernel_standalone.toolkit.models",
        "agentkernel_standalone.toolkit.models.router",
    ]
    previous = {name: sys.modules.get(name) for name in module_names}

    router_mod = types.ModuleType("agentkernel_standalone.toolkit.models.router")

    class AsyncModelRouter:
        def __init__(self, models_conf):
            captured["models_conf"] = models_conf

    class ModelRouter:
        def __init__(self, async_router):
            self.async_router = async_router

    router_mod.AsyncModelRouter = AsyncModelRouter
    router_mod.ModelRouter = ModelRouter

    sys.modules["agentkernel_standalone"] = types.ModuleType("agentkernel_standalone")
    sys.modules["agentkernel_standalone.toolkit"] = types.ModuleType("agentkernel_standalone.toolkit")
    sys.modules["agentkernel_standalone.toolkit.models"] = types.ModuleType(
        "agentkernel_standalone.toolkit.models"
    )
    sys.modules["agentkernel_standalone.toolkit.models.router"] = router_mod
    return previous


def _restore_modules(previous: dict) -> None:
    for name, module in previous.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def test_config_no_plaintext_key() -> None:
    conf = _load_config()
    entry = _chat_entry(conf)
    check("provider unchanged", entry.get("name") == "OpenAIProvider", entry.get("name"))
    check("model unchanged", entry.get("model") == "qwen-plus", entry.get("model"))
    check("temperature unchanged", entry.get("temperature") == 0.3, entry.get("temperature"))
    check(
        "api key is environment placeholder",
        entry.get("api_key") == run_experiments.TASK005_LLM_API_KEY_PLACEHOLDER,
        "<redacted>",
    )


def test_missing_env_fails_closed() -> None:
    old = os.environ.pop(run_experiments.TASK005_LLM_API_KEY_ENV, None)
    try:
        try:
            run_experiments._build_real_router()
        except run_experiments.ReplicationStartupError:
            failed_closed = True
        else:
            failed_closed = False
        check("missing env fails closed", failed_closed)
    finally:
        if old is not None:
            os.environ[run_experiments.TASK005_LLM_API_KEY_ENV] = old


def test_dummy_env_injection_is_memory_only_and_silent() -> None:
    dummy = "dummy-test-key-not-secret"
    captured = {}
    old = os.environ.get(run_experiments.TASK005_LLM_API_KEY_ENV)
    os.environ[run_experiments.TASK005_LLM_API_KEY_ENV] = dummy
    previous = _install_fake_router_modules(captured)
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            router = run_experiments._build_real_router(requested_llm_seed=12345)
        injected = _chat_entry(captured["models_conf"])
        disk_entry = _chat_entry(_load_config())
        check("dummy env injection reaches router memory", injected.get("api_key") == dummy, "<redacted>")
        check(
            "dummy env value not written to yaml",
            disk_entry.get("api_key") == run_experiments.TASK005_LLM_API_KEY_PLACEHOLDER,
            "<redacted>",
        )
        check("requested seed applied in memory", injected.get("seed") == 12345, injected.get("seed"))
        check("dummy env value absent from stdout", dummy not in stdout.getvalue())
        check("fake router constructed", hasattr(router, "_task005_async_router"))
    finally:
        _restore_modules(previous)
        if old is None:
            os.environ.pop(run_experiments.TASK005_LLM_API_KEY_ENV, None)
        else:
            os.environ[run_experiments.TASK005_LLM_API_KEY_ENV] = old


def test_real_mode_does_not_fallback_to_mock() -> None:
    old = os.environ.pop(run_experiments.TASK005_LLM_API_KEY_ENV, None)
    ctx = {
        "llm_mode": "real",
        "requested_llm_seed": 2026080902,
    }
    try:
        try:
            run_experiments._build_router_for_mode(ctx)
        except run_experiments.ReplicationStartupError:
            failed_closed = True
        else:
            failed_closed = False
        check("real mode missing env does not fallback to mock", failed_closed)
    finally:
        if old is not None:
            os.environ[run_experiments.TASK005_LLM_API_KEY_ENV] = old


def test_mock_mode_does_not_require_credential() -> None:
    old = os.environ.pop(run_experiments.TASK005_LLM_API_KEY_ENV, None)
    ctx = {
        "llm_mode": "deterministic-mock",
        "requested_llm_seed": 2026080902,
    }
    try:
        router = run_experiments._build_router_for_mode(ctx)
        check("mock mode does not require real credential", getattr(router, "_task005_router_close_noop", False))
    finally:
        if old is not None:
            os.environ[run_experiments.TASK005_LLM_API_KEY_ENV] = old


def test_metadata_is_sanitized() -> None:
    meta = run_experiments._read_llm_config(str(ROOT))
    payload = json.dumps(meta, sort_keys=True)
    check("metadata marks placeholder as not-present", meta.get("api_key_present") is False, meta)
    check("metadata contains redacted api_key field", meta.get("api_key") == "not-present", meta.get("api_key"))
    check("metadata contains no placeholder string", run_experiments.TASK005_LLM_API_KEY_PLACEHOLDER not in payload)


def main() -> int:
    test_config_no_plaintext_key()
    test_missing_env_fails_closed()
    test_dummy_env_injection_is_memory_only_and_silent()
    test_real_mode_does_not_fallback_to_mock()
    test_mock_mode_does_not_require_credential()
    test_metadata_is_sanitized()
    print(f"Passed: {P}")
    print(f"Failed: {F}")
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
