from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

from oc_calibration_runner import prepare_full, run_full_frozen


AUTHORIZATION_TOKEN = "I5C3D_FULL_OC_20000_5000"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return proc.stdout.strip()


def load_contract(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data["stage"] != "TASK_005 Stage I.5C-3C-3":
        raise ValueError("launch contract stage mismatch")
    if data["status"] != "frozen":
        raise ValueError("launch contract is not frozen")
    return data


def resolve_frozen_paths(
    root: Path,
    contract: dict[str, Any],
) -> dict[str, Path]:
    frozen = contract["frozen_inputs"]
    paths = {
        key: root / value["relative_path"]
        for key, value in frozen.items()
    }
    for key, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"{key}: {path}")
        actual = sha256_file(path)
        expected = frozen[key]["sha256"]
        if actual != expected:
            raise ValueError(
                f"{key} SHA256 mismatch: {actual} != {expected}"
            )
    return paths


def verify_git_preflight(root: Path, contract: dict[str, Any]) -> dict[str, str]:
    branch = run_git(root, "branch", "--show-current")
    if branch != contract["git_gate"]["required_branch"]:
        raise RuntimeError(f"branch mismatch: {branch}")

    parent = contract["parent"]["implementation_head"]
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", parent, "HEAD"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("implementation parent is not an ancestor of HEAD")

    if run_git(root, "diff", "--name-only"):
        raise RuntimeError("tracked unstaged changes found")
    if run_git(root, "diff", "--cached", "--name-only"):
        raise RuntimeError("staged changes found")

    upstream = run_git(
        root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
    )
    counts = run_git(
        root,
        "rev-list",
        "--left-right",
        "--count",
        "HEAD...@{u}",
    ).split()
    if counts != ["0", "0"]:
        raise RuntimeError(f"local/upstream mismatch: {counts}")

    return {
        "head": run_git(root, "rev-parse", "HEAD"),
        "branch": branch,
        "upstream": upstream,
    }


def frozen_output_paths(
    root: Path,
    contract: dict[str, Any],
) -> tuple[Path, Path]:
    output_dir = root / contract["output_contract"]["output_directory"]
    evidence_zip = root / contract["output_contract"]["evidence_zip"]
    expected_zip = output_dir.parent / f"{output_dir.name}_evidence.zip"
    if evidence_zip != expected_zip:
        raise ValueError("contract output ZIP is inconsistent with runner naming")
    return output_dir, evidence_zip


def verify_output_absent(
    output_dir: Path,
    evidence_zip: Path,
) -> None:
    if output_dir.exists():
        raise FileExistsError(
            f"refuse existing frozen output directory: {output_dir}"
        )
    if evidence_zip.exists():
        raise FileExistsError(
            f"refuse existing frozen evidence ZIP: {evidence_zip}"
        )


def preflight(
    root: Path,
    launch_contract_path: Path,
) -> dict[str, Any]:
    contract = load_contract(launch_contract_path)
    git_state = verify_git_preflight(root, contract)
    paths = resolve_frozen_paths(root, contract)
    output_dir, evidence_zip = frozen_output_paths(root, contract)
    verify_output_absent(output_dir, evidence_zip)

    residuals, labels = prepare_full(
        paths["oc_design"],
        paths["i5c0_evidence"],
    )
    if residuals.shape != (5, 28):
        raise AssertionError(f"full input shape mismatch: {residuals.shape}")
    if len(labels) != 28:
        raise AssertionError("full input label count mismatch")

    return {
        "status": "preflight-passed",
        "head": git_state["head"],
        "branch": git_state["branch"],
        "upstream": git_state["upstream"],
        "full_input_shape": [5, 28],
        "output_directory": contract["output_contract"]["output_directory"],
        "evidence_zip": contract["output_contract"]["evidence_zip"],
        "primary_iterations_per_cell_per_stream": 20000,
        "loo_iterations_per_cell": 5000,
        "formal_target_n_frozen": False,
        "formal_llm_launch_permitted": False,
        "real_llm_calls_used": False,
        "network_access_used": False,
        "full_oc_calibration_executed": False,
    }


def verify_completed_output(
    output_dir: Path,
    evidence_zip: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    required = set(contract["output_contract"]["required_payload_files"])
    actual = {
        path.name
        for path in output_dir.iterdir()
        if path.is_file()
    }
    if actual != required:
        raise AssertionError(
            f"output file set mismatch: {sorted(actual)}"
        )

    with zipfile.ZipFile(evidence_zip) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise AssertionError(f"evidence ZIP CRC failure: {bad}")
        if set(archive.namelist()) != required:
            raise AssertionError("evidence ZIP member set mismatch")

    summary_path = output_dir / "oc_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    if summary["profile"] != "full":
        raise AssertionError("completed profile is not full")
    if summary["selection_enabled"] is not True:
        raise AssertionError("full selection gate not enabled")
    if summary["full_frozen_20000_5000_profile_executed"] is not True:
        raise AssertionError("frozen 20,000/5,000 profile not recorded as executed")
    if summary["formal_target_n_frozen"] is not False:
        raise AssertionError("formal target N was incorrectly frozen")
    if summary["formal_llm_launch_permitted"] is not False:
        raise AssertionError("formal LLM launch was incorrectly permitted")
    if summary["real_llm_calls_used"] is not False:
        raise AssertionError("real LLM use was recorded")
    if summary["network_access_used"] is not False:
        raise AssertionError("network access was recorded")

    return summary


def execute(
    root: Path,
    launch_contract_path: Path,
    authorization_token: str,
) -> dict[str, Any]:
    if authorization_token != AUTHORIZATION_TOKEN:
        raise PermissionError("full OC authorization token mismatch")

    contract = load_contract(launch_contract_path)
    preflight_result = preflight(root, launch_contract_path)
    paths = resolve_frozen_paths(root, contract)
    output_dir, evidence_zip = frozen_output_paths(root, contract)

    started = time.perf_counter()
    run_full_frozen(
        design_path=paths["oc_design"],
        i5c0_evidence=paths["i5c0_evidence"],
        runner_contract_path=paths["runner_contract"],
        full_executor_contract_path=paths["full_executor_contract"],
        output_dir=output_dir,
        execution_authorized=True,
    )
    elapsed_seconds = time.perf_counter() - started

    summary = verify_completed_output(
        output_dir,
        evidence_zip,
        contract,
    )

    return {
        "status": "full-oc-completed",
        "launch_head": preflight_result["head"],
        "elapsed_seconds_runtime_only_not_frozen_payload": elapsed_seconds,
        "diagnostic_selected_candidate_n": summary[
            "diagnostic_selected_candidate_n"
        ],
        "n40_feasibility_decision_required": summary[
            "n40_feasibility_decision_required"
        ],
        "formal_target_n_frozen": False,
        "formal_llm_launch_permitted": False,
        "real_llm_calls_used": False,
        "network_access_used": False,
        "full_oc_calibration_executed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )
    parser.add_argument(
        "--launch-contract",
        type=Path,
        required=True,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "preflight",
        help="Validate frozen full-OC inputs without executing calibration.",
    )

    execute_parser = sub.add_parser(
        "execute",
        help="Execute the frozen 20,000/5,000 offline OC calibration.",
    )
    execute_parser.add_argument(
        "--authorization-token",
        required=True,
    )

    args = parser.parse_args()
    root = args.project_root.resolve()
    launch_contract_path = args.launch_contract.resolve()

    if args.command == "preflight":
        result = preflight(root, launch_contract_path)
    elif args.command == "execute":
        result = execute(
            root,
            launch_contract_path,
            args.authorization_token,
        )
    else:
        raise AssertionError("unreachable")

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
