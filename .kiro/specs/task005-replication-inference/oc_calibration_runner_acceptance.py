from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

EXPECTED_CONTRACT_SHA = "3864F36F46BF1151A8C22F2F7398327B772C24FD5F8B1ADE009B80FF1DAEC3A5"
EXPECTED_COUNTS_PRE = (32, 10, 0)
EXPECTED_COUNTS_POST = (42, 0, 0)

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
        if condition:
            self.p += 1
            self.rows.append(("PASS", name, detail))
        else:
            self.f += 1
            self.rows.append(("FAIL", name, detail))
    def fail(self, name, detail):
        self.f += 1
        self.rows.append(("FAIL", name, detail))

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def banned_imports(path: Path):
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

def run(cmd, cwd):
    return subprocess.run(
        cmd, cwd=cwd, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--expect-preimplementation", action="store_true")
    args = ap.parse_args()

    root = args.project_root.resolve()
    contract_path = args.contract.resolve()
    ledger = Ledger()

    # -------- 32 frozen-contract checks --------
    ledger.check("contract exists", contract_path.is_file())
    ledger.check("contract SHA", sha256(contract_path) == EXPECTED_CONTRACT_SHA)
    data = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    ledger.check("stage", data["stage"] == "TASK_005 Stage I.5C-3C-0")
    ledger.check("status frozen", data["status"] == "frozen")
    ledger.check("classification", data["classification"] == "full-offline-oc-runner-preimplementation-acceptance-contract")
    ledger.check("target runner", data["target"]["runner_module"] == "oc_calibration_runner.py")
    ledger.check("CLI extension target", data["target"]["cli_to_extend"] == "run_oc_calibration.py")
    ledger.check("four CLI commands frozen", len(data["target"]["required_cli_commands_after_implementation"]) == 4)
    ledger.check("28 estimands", data["frozen_full_inputs"]["confirmatory_estimands"] == 28)
    ledger.check("family 16", data["frozen_full_inputs"]["families"]["strategy_primary_16"] == 16)
    ledger.check("family 12", data["frozen_full_inputs"]["families"]["factorial_confirmatory_12"] == 12)
    ledger.check("42 source rows", data["matrix_reconstruction"]["expected_source_rows_total"] == 42)
    ledger.check("28 selected rows", data["matrix_reconstruction"]["expected_selected_rows"] == 28)
    ledger.check("five canonical blocks", len(data["matrix_reconstruction"]["canonical_blocks"]) == 5)
    ledger.check("PCG64 RNG", "PCG64" in data["rng_contract"]["generator"])
    ledger.check("SHA256 seed derivation", data["rng_contract"]["cell_seed_derivation"]["algorithm"] == "SHA256")
    ledger.check("two primary streams", set(data["rng_contract"]["primary_stream_base_seeds"]) == {"A","B"})
    ledger.check("common random numbers within cell", "reused" in data["rng_contract"]["common_random_numbers"]["within_one_primary_cell"])
    ledger.check("smoke candidate N", data["profiles"]["smoke"]["candidate_n"] == [12,20])
    ledger.check("smoke stress", data["profiles"]["smoke"]["variance_multipliers"] == [1.0,2.0])
    ledger.check("smoke iterations", data["profiles"]["smoke"]["iterations_per_cell_per_stream"] == 200)
    ledger.check("smoke cannot select N", data["profiles"]["smoke"]["hard_gate_selection_enabled"] is False)
    ledger.check("full candidate N", data["profiles"]["full"]["candidate_n"] == [12,16,20,24,30,40])
    ledger.check("full stress", data["profiles"]["full"]["variance_multipliers"] == [1.0,1.5,2.0])
    ledger.check("full iterations", data["profiles"]["full"]["iterations_per_cell_per_stream"] == 20000)
    ledger.check("LOO iterations", data["profiles"]["full"]["loo_iterations_per_cell"] == 5000)
    ledger.check("LOO variants", data["profiles"]["full"]["loo_variants"] == 5)
    ledger.check("full confirmation flag", data["profiles"]["full"]["explicit_cli_confirmation_flag"] == "--confirm-full-calibration")
    ledger.check("deterministic ZIP", data["deterministic_output_contract"]["evidence_zip_deterministic"] is True)
    ledger.check("full output file count", len(data["required_output_files_full"]) == 8)
    ledger.check("formal N not frozen", data["gates"]["formal_target_n_frozen"] is False)
    ledger.check("formal launch false", data["gates"]["formal_llm_launch_permitted"] is False)

    # -------- 10 implementation checks --------
    runner = root / "oc_calibration_runner.py"
    cli = root / "run_oc_calibration.py"

    ledger.check("runner exists", runner.is_file(), "runner absent" if not runner.is_file() else "")

    cli_text = cli.read_text(encoding="utf-8-sig") if cli.is_file() else ""
    ledger.check("CLI calibrate-smoke command", "calibrate-smoke" in cli_text)
    ledger.check("CLI calibrate-full command", "calibrate-full" in cli_text)

    if runner.is_file():
        ledger.check("runner no banned imports", banned_imports(runner) == [])
        runner_text = runner.read_text(encoding="utf-8-sig")
        ledger.check("runner design hash gate", data["frozen_full_inputs"]["oc_design_sha256"] in runner_text)
        ledger.check("runner I5C0 hash gate", data["frozen_full_inputs"]["i5c0_evidence_sha256"] in runner_text)
        ledger.check("runner refuse overwrite", "FileExistsError" in runner_text or "refuse" in runner_text.lower())
        ledger.check("runner deterministic seed derivation", "sha256" in runner_text.lower() and "big" in runner_text.lower())
    else:
        ledger.fail("runner no banned imports", "runner absent")
        ledger.fail("runner design hash gate", "runner absent")
        ledger.fail("runner I5C0 hash gate", "runner absent")
        ledger.fail("runner refuse overwrite", "runner absent")
        ledger.fail("runner deterministic seed derivation", "runner absent")

    # Smoke E2E and full-profile explicit confirmation are runtime checks.
    if runner.is_file() and "calibrate-smoke" in cli_text:
        fixture = root / ".kiro/specs/task005-replication-inference/oc_calibration_synthetic_fixture1.0.json"
        contract = contract_path
        import tempfile
        with tempfile.TemporaryDirectory(prefix="task005_i5c3c_accept_") as tmp:
            tmp_path = Path(tmp)
            out_a = tmp_path / "a"
            out_b = tmp_path / "b"
            base_cmd = [
                sys.executable, "-X", "utf8", str(cli),
                "calibrate-smoke",
                "--fixture", str(fixture),
                "--runner-contract", str(contract),
            ]
            a = run(base_cmd + ["--output-dir", str(out_a)], root)
            b = run(base_cmd + ["--output-dir", str(out_b)], root)
            same = (
                a.returncode == 0 and b.returncode == 0
                and sorted(p.name for p in out_a.iterdir()) == sorted(p.name for p in out_b.iterdir())
                and all(
                    sha256(out_a / p.name) == sha256(out_b / p.name)
                    for p in out_a.iterdir() if p.is_file()
                )
            )
            ledger.check("smoke deterministic E2E", same, a.stderr or b.stderr)

            full = run([
                sys.executable, "-X", "utf8", str(cli),
                "calibrate-full",
                "--runner-contract", str(contract),
                "--design", str(root / ".kiro/specs/task005-replication-inference/oc_calibration_design1.0.json"),
                "--i5c0-evidence", str(root / "task005_stageI5C0_precision_stability.zip"),
                "--output-dir", str(tmp_path / "full_should_not_run"),
            ], root)
            ledger.check(
                "full requires explicit confirmation",
                full.returncode != 0 and not (tmp_path / "full_should_not_run").exists()
            )
    else:
        ledger.fail("smoke deterministic E2E", "runner/CLI not implemented")
        ledger.fail("full requires explicit confirmation", "runner/CLI not implemented")

    for status, name, detail in ledger.rows:
        suffix = f" -- {detail}" if detail else ""
        print(f"{status} | {name}{suffix}")
    print("=" * 72)
    print(f"PASS={ledger.p} FAIL={ledger.f} WARN={ledger.w}")

    actual = (ledger.p, ledger.f, ledger.w)
    if args.expect_preimplementation:
        if actual != EXPECTED_COUNTS_PRE:
            print(f"PREIMPLEMENTATION BASELINE MISMATCH expected={EXPECTED_COUNTS_PRE} actual={actual}")
            return 2
        print("PREIMPLEMENTATION BASELINE: MATCHED")
        return 1

    if actual != EXPECTED_COUNTS_POST:
        print(f"IMPLEMENTATION ACCEPTANCE MISMATCH expected={EXPECTED_COUNTS_POST} actual={actual}")
        return 1
    print("IMPLEMENTATION ACCEPTANCE: MATCHED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
