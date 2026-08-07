#!/usr/bin/env python
"""TASK_005 Stage I.5C-5B-0 formal activation gate acceptance tests."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_formal_launch as launch


EXPECTED_LAUNCH_SHA = (
    "fd9d8cb57c714a962d3476c4d07f0850d05f9f80c11eea9809578f32a471c8f6"
)
EXPECTED_LEDGER_SHA = (
    "44dd7e0381a2fbe7ea4525fad8748b5d9d8b0bdfb6fdd8ed9aa85e50140cc38e"
)
EXPECTED_MODEL_SHA = (
    "8311d2f5758009e1620d3cc10f588cb789fe2d0c801878854d19a79bf0900a61"
)


class Reporter:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, name: str, ok: bool, expected: Any = "", actual: Any = "") -> None:
        if ok:
            self.passed += 1
        else:
            self.failed += 1
            print(f"FAIL {name} | expected={expected} actual={actual}")

    def summary(self) -> int:
        print("TASK_005 FORMAL ACTIVATION GATE ACCEPTANCE RESULTS")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        return 1 if self.failed else 0


def clean_git_state() -> dict:
    return {
        "branch": "refactor/task005-replication-inference",
        "tracked_clean": True,
        "staged_clean": True,
        "upstream_behind": 0,
        "upstream_ahead": 0,
    }


def expect_gate_error(fn) -> bool:
    try:
        fn()
    except launch.FormalLaunchGateError:
        return True
    return False


def read_config() -> list[dict]:
    with (ROOT / "configs/models_config.yaml").open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, list):
        raise AssertionError("expected list config")
    return data


def write_config(path: Path, config: Any) -> None:
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def validate_mutated_config(config: Any) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "models_config.yaml"
        write_config(cfg, config)
        return expect_gate_error(
            lambda: launch.validate_current_formal_model_config(
                root=ROOT,
                config_path=cfg,
                frozen_sanitized_path=ROOT
                / ".kiro/specs/task005-replication-inference/"
                "formal_model_config_sanitized1.0.json",
            )
        )


def check_contract_and_preflight(v: Reporter) -> None:
    v.check(
        "A launch contract exact SHA",
        launch._sha256_file(ROOT / launch.CONTRACT_PATH) == EXPECTED_LAUNCH_SHA,
        EXPECTED_LAUNCH_SHA,
        launch._sha256_file(ROOT / launch.CONTRACT_PATH),
    )
    v.check(
        "A seed ledger exact SHA",
        launch._sha256_file(ROOT / launch.SEED_LEDGER_PATH) == EXPECTED_LEDGER_SHA,
        EXPECTED_LEDGER_SHA,
        launch._sha256_file(ROOT / launch.SEED_LEDGER_PATH),
    )
    v.check(
        "A model sanitized exact SHA",
        launch._sha256_file(ROOT / launch.MODEL_SANITIZED_PATH) == EXPECTED_MODEL_SHA,
        EXPECTED_MODEL_SHA,
        launch._sha256_file(ROOT / launch.MODEL_SANITIZED_PATH),
    )
    result = launch.run_preauthorization_preflight(
        root=ROOT,
        enforce_git=True,
        git_state_provider=clean_git_state,
    )
    v.check("B seed ledger reconstruction PASS", result["formal_n"] == 24, 24, result["formal_n"])
    v.check("C current sanitized model identity PASS", result["runtime_model_gate"] is True, True, result["runtime_model_gate"])
    v.check("I per-block requested seed override", result["per_block_requested_seed_override"] is True, True, result["per_block_requested_seed_override"])
    overrides = launch.validate_per_block_requested_seed_override(root=ROOT)
    v.check("I R001 requested seed is not base seed", overrides["R001"] != 42, "not 42", overrides["R001"])
    v.check("I R024 requested seed exists", "R024" in overrides, True, sorted(overrides)[-1])
    v.check("J llm seed support unknown", result["llm_seed_supported"] == "unknown", "unknown", result["llm_seed_supported"])
    v.check("J no provider determinism guarantee", result["provider_determinism_guaranteed"] is False, False, result["provider_determinism_guaranteed"])
    v.check("O no real LLM", result["real_llm_calls"] is False, False, result["real_llm_calls"])
    v.check("O no network", result["network_calls"] == 0, 0, result["network_calls"])


def check_model_mutations(v: Reporter) -> None:
    config = read_config()
    changed_model = copy.deepcopy(config)
    changed_model[0]["model"] = "other-model"
    v.check("D model changed fails", validate_mutated_config(changed_model), True, False)

    changed_base = copy.deepcopy(config)
    changed_base[0]["base_url"] = "https://example.invalid/v1"
    v.check("E base_url changed fails", validate_mutated_config(changed_base), True, False)

    changed_temp = copy.deepcopy(config)
    changed_temp[0]["temperature"] = 0.9
    v.check("F temperature changed fails", validate_mutated_config(changed_temp), True, False)

    added_chat = copy.deepcopy(config)
    extra = copy.deepcopy(added_chat[0])
    extra["name"] = "SecondProvider"
    added_chat.append(extra)
    v.check("G second chat-capable model fails", validate_mutated_config(added_chat), True, False)

    changed_key = copy.deepcopy(config)
    changed_key[0]["api_key"] = "synthetic-rotated-key"
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "models_config.yaml"
        write_config(cfg, changed_key)
        outcome = launch.validate_current_formal_model_config(
            root=ROOT,
            config_path=cfg,
            frozen_sanitized_path=ROOT
            / ".kiro/specs/task005-replication-inference/"
            "formal_model_config_sanitized1.0.json",
        )
    v.check("H API key value changed still matches", outcome["model_binding_verified"] is True, True, outcome)


def check_output_and_authorization(v: Reporter) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        existing = Path(tmp) / "task005-formal-v1"
        existing.mkdir()
        failed = expect_gate_error(
            lambda: launch.run_preauthorization_preflight(
                root=ROOT,
                output_path=existing,
                enforce_git=True,
                git_state_provider=clean_git_state,
            )
        )
    v.check("K formal output existing fails", failed, True, False)

    before = (ROOT / launch.FORMAL_OUTPUT_PATH).exists()
    exit_code = launch.run_execute_request(root=ROOT)
    after = (ROOT / launch.FORMAL_OUTPUT_PATH).exists()
    v.check("M authorization artifact absent fails", exit_code == 2, 2, exit_code)
    v.check("M no batch creation", before is False and after is False, False, after)
    exit_code = launch.run_execute_request(root=ROOT, runtime_token=None)
    v.check("N runtime token absent fails", exit_code == 2, 2, exit_code)


def check_git_gate(v: Reporter) -> None:
    v.check("L clean git mock passes", launch.validate_git_gate(clean_git_state)["upstream_ahead"] == 0, 0, "nonzero")
    dirty = dict(clean_git_state())
    dirty["tracked_clean"] = False
    v.check("L dirty git fails", expect_gate_error(lambda: launch.validate_git_gate(lambda: dirty)), True, False)
    wrong_branch = dict(clean_git_state())
    wrong_branch["branch"] = "main"
    v.check("L wrong branch fails", expect_gate_error(lambda: launch.validate_git_gate(lambda: wrong_branch)), True, False)
    upstream = dict(clean_git_state())
    upstream["upstream_ahead"] = 1
    v.check("L upstream mismatch fails", expect_gate_error(lambda: launch.validate_git_gate(lambda: upstream)), True, False)


def check_activation_contract(v: Reporter) -> None:
    contract = launch._read_json_object(ROOT / launch.ACTIVATION_CONTRACT_PATH)
    v.check("contract runtime model validation required", contract["runtime_model_validation_required"] is True, True, contract["runtime_model_validation_required"])
    v.check("contract per-child recheck required", contract["runtime_model_validation_before_each_child"] is True, True, contract["runtime_model_validation_before_each_child"])
    v.check("contract secret YAML not auth identity", contract["secret_bearing_config_hash_not_authorization_identity"] is True, True, contract["secret_bearing_config_hash_not_authorization_identity"])
    v.check("contract human authorization absent", contract["human_authorization_present"] is False, False, contract["human_authorization_present"])
    v.check("contract real execution inactive", contract["real_execution_activated"] is False, False, contract["real_execution_activated"])
    v.check("contract launch not permitted", contract["formal_llm_launch_permitted"] is False, False, contract["formal_llm_launch_permitted"])


def main() -> int:
    v = Reporter()
    check_contract_and_preflight(v)
    check_model_mutations(v)
    check_output_and_authorization(v)
    check_git_gate(v)
    check_activation_contract(v)
    return v.summary()


if __name__ == "__main__":
    raise SystemExit(main())
