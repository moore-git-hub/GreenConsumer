from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

EXPECTED_CONTRACT_SHA = "64053A4178D61FED2F555C2AA2138D97453F1AE05DC3D3E2E8ED38CCD12B6C67"
EXPECTED_LAUNCHER_SHA = "5B80046065D73F7599878C01A2DBE6578B16708227DE309E33CA066E99E85821"

BANNED = {
    "requests", "httpx", "aiohttp", "urllib3", "openai",
    "dashscope", "socket", "websocket", "websockets",
}

class Ledger:
    def __init__(self):
        self.p = 0
        self.f = 0
        self.w = 0
        self.rows = []

    def check(self, name, condition, detail=""):
        if bool(condition):
            self.p += 1
            self.rows.append(("PASS", name, detail))
        else:
            self.f += 1
            self.rows.append(("FAIL", name, detail))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def banned_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            continue
        hits.extend(name for name in names if name in BANNED)
    return sorted(set(hits))


def run(cmd, cwd: Path):
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--launcher", type=Path, required=True)
    args = ap.parse_args()

    root = args.project_root.resolve()
    contract_path = args.contract.resolve()
    launcher_path = args.launcher.resolve()
    ledger = Ledger()

    ledger.check("contract exists", contract_path.is_file())
    ledger.check("launcher exists", launcher_path.is_file())
    ledger.check("contract SHA", sha256(contract_path) == EXPECTED_CONTRACT_SHA)
    ledger.check("launcher SHA", sha256(launcher_path) == EXPECTED_LAUNCHER_SHA)

    data = json.loads(contract_path.read_text(encoding="utf-8-sig"))

    ledger.check("stage", data["stage"] == "TASK_005 Stage I.5C-3C-3")
    ledger.check("status frozen", data["status"] == "frozen")
    ledger.check("classification", data["classification"] == "full-offline-oc-execution-launch-contract")
    ledger.check("parent head", data["parent"]["implementation_head"] == "7f04e2886d67f894595b4b946c40183e4b4b0013")
    ledger.check("launcher path", data["launcher"]["relative_path"] == "run_oc_full_calibration.py")
    ledger.check("launcher identity", data["launcher"]["sha256"] == EXPECTED_LAUNCHER_SHA)
    ledger.check("authorization token frozen", data["launcher"]["authorization_token"] == "I5C3D_FULL_OC_20000_5000")
    ledger.check("exact-head wrapper deferred", data["launcher"]["execution_requires_exact_head_wrapper_after_this_contract_is_committed"] is True)

    profile = data["execution_profile"]
    ledger.check("candidate N frozen", profile["candidate_n"] == [12,16,20,24,30,40])
    ledger.check("stress frozen", profile["variance_multipliers"] == [1.0,1.5,2.0])
    ledger.check("two streams", set(profile["primary_streams"]) == {"A","B"})
    ledger.check("primary cells 36", profile["primary_cells"] == 36)
    ledger.check("primary iterations 20000", profile["primary_iterations_per_cell_per_stream"] == 20000)
    ledger.check("primary total 720000", profile["primary_total_iterations"] == 720000)
    ledger.check("LOO variants 5", profile["loo_variants"] == 5)
    ledger.check("LOO cells 30", profile["loo_candidate_cells"] == 30)
    ledger.check("LOO iterations 5000", profile["loo_iterations_per_cell"] == 5000)
    ledger.check("LOO total 150000", profile["loo_total_iterations"] == 150000)
    ledger.check("no adaptive iterations", profile["adaptive_iteration_increase"] is False)
    ledger.check("selection enabled for full", profile["selection_enabled"] is True)

    output = data["output_contract"]
    ledger.check("frozen output directory", output["output_directory"] == "task005_stageI5C3D_oc_full_v1")
    ledger.check("frozen evidence ZIP", output["evidence_zip"] == "task005_stageI5C3D_oc_full_v1_evidence.zip")
    ledger.check("eight payload files", len(output["required_payload_files"]) == 8)
    ledger.check("refuse output overwrite", output["refuse_existing_output_directory"] is True)
    ledger.check("refuse ZIP overwrite", output["refuse_existing_evidence_zip"] is True)
    ledger.check("ZIP CRC required zero", output["zip_crc_errors_required"] == 0)
    ledger.check("deterministic payloads", output["deterministic_payloads"] is True)

    stop = data["stop_and_failure_rules"]
    ledger.check("no wall clock timeout", stop["no_wall_clock_timeout"] is True)
    ledger.check("no adaptive post-result change", stop["do_not_adapt_iterations_after_observing_results"] is True)
    ledger.check("partial output preserved", stop["partial_output_must_be_preserved_and_must_not_be_overwritten"] is True)

    interpretation = data["interpretation_rules"]
    ledger.check("diagnostic N not formal N", interpretation["diagnostic_selected_candidate_n_is_not_formal_n"] is True)
    ledger.check("N40 feasibility rule", interpretation["if_selected_n_is_40_require_explicit_feasibility_decision"] is True)
    ledger.check("local DID excluded", interpretation["local_trust_effect_did_3_excluded_from_confirmatory_oc"] is True)

    safety = data["safety"]
    ledger.check("network forbidden", safety["network_access_permitted"] is False)
    ledger.check("real LLM forbidden", safety["real_llm_calls_permitted"] is False)
    ledger.check("formal launch false", safety["formal_llm_launch_permitted"] is False)

    ledger.check("launcher no banned imports", banned_imports(launcher_path) == [])

    output_dir = root / output["output_directory"]
    evidence_zip = root / output["evidence_zip"]
    ledger.check("frozen output absent", not output_dir.exists())
    ledger.check("frozen evidence ZIP absent", not evidence_zip.exists())

    preflight = run([
        sys.executable,
        "-X",
        "utf8",
        str(launcher_path),
        "--project-root",
        str(root),
        "--launch-contract",
        str(contract_path),
        "preflight",
    ], root)
    ledger.check(
        "launcher preflight exit 0",
        preflight.returncode == 0,
        preflight.stderr,
    )
    ledger.check(
        "preflight records no full execution",
        '"full_oc_calibration_executed": false' in preflight.stdout.lower(),
        preflight.stdout,
    )
    ledger.check(
        "preflight creates no output",
        not output_dir.exists() and not evidence_zip.exists(),
    )

    wrong_token = run([
        sys.executable,
        "-X",
        "utf8",
        str(launcher_path),
        "--project-root",
        str(root),
        "--launch-contract",
        str(contract_path),
        "execute",
        "--authorization-token",
        "WRONG_TOKEN",
    ], root)
    ledger.check("wrong token rejected", wrong_token.returncode != 0)
    ledger.check(
        "wrong token creates no output",
        not output_dir.exists() and not evidence_zip.exists(),
    )

    for status, name, detail in ledger.rows:
        suffix = f" -- {detail}" if detail else ""
        print(f"{status} | {name}{suffix}")
    print("=" * 76)
    print(f"PASS={ledger.p} FAIL={ledger.f} WARN={ledger.w}")

    if ledger.f != 0:
        return 1

    print("Stage I.5C-3C-3 launch acceptance: MATCHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
