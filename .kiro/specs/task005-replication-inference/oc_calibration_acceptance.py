from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

EXPECTED_FIXTURE_SHA = "3D4F4C3CA596B2B42E4E4A5C5E7EBC573D2CF62CA9A6149E696423F18854AEA9"
EXPECTED_CONTRACT_SHA = "DF1AC4373C6652674A7E38E645D241680B89712258A98B9F272CE52F94584A38"
EXPECTED_PREIMPLEMENTATION = (31, 12, 0)
TARGET_MODULE = "oc_calibration.py"
TARGET_CLI = "run_oc_calibration.py"

class Ledger:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warned = 0
        self.rows = []

    def check(self, name, condition, detail=""):
        ok = bool(condition)
        self.rows.append(("PASS" if ok else "FAIL", name, detail))
        if ok:
            self.passed += 1
        else:
            self.failed += 1

    def fail(self, name, detail):
        self.rows.append(("FAIL", name, str(detail)))
        self.failed += 1

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("task005_oc_calibration_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot create module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def forbidden_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    banned = {
        "requests", "httpx", "aiohttp", "urllib3", "openai",
        "dashscope", "socket", "websocket", "websockets",
    }
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            continue
        hits.extend(name for name in names if name in banned)
    return sorted(set(hits))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--expect-preimplementation", action="store_true")
    args = ap.parse_args()

    root = args.project_root.resolve()
    fixture_path = args.fixture.resolve()
    contract_path = args.contract.resolve()
    ledger = Ledger()

    # ----- Frozen artifact checks: 31 PASS expected before implementation -----
    ledger.check("fixture exists", fixture_path.is_file())
    ledger.check("contract exists", contract_path.is_file())
    ledger.check("fixture SHA", sha256(fixture_path) == EXPECTED_FIXTURE_SHA)
    ledger.check("contract SHA", sha256(contract_path) == EXPECTED_CONTRACT_SHA)

    fixture = json.loads(fixture_path.read_text(encoding="utf-8-sig"))
    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    matrix = np.asarray(fixture["centered_residual_matrix"], dtype=float)

    ledger.check("stage fixture", fixture["stage"] == "TASK_005 Stage I.5C-3A")
    ledger.check("stage contract", contract["stage"] == "TASK_005 Stage I.5C-3A")
    ledger.check("contract frozen", contract["status"] == "frozen")
    ledger.check("matrix shape 5x28", matrix.shape == (5, 28))
    ledger.check("matrix finite", np.isfinite(matrix).all())
    ledger.check("28 estimands", len(fixture["estimands"]) == 28)
    ledger.check("estimand ids unique", len({x["estimand_id"] for x in fixture["estimands"]}) == 28)
    ledger.check("strategy family size", len(fixture["families"]["strategy_primary_16"]) == 16)
    ledger.check("factorial family size", len(fixture["families"]["factorial_confirmatory_12"]) == 12)
    ledger.check("family union 0..27",
                 sorted(fixture["families"]["strategy_primary_16"] +
                        fixture["families"]["factorial_confirmatory_12"]) == list(range(28)))
    ledger.check("column means zero", np.max(np.abs(matrix.mean(axis=0))) <= 1e-12)
    ledger.check("all sample SD positive", np.all(matrix.std(axis=0, ddof=1) > 0))
    expected_sd = np.asarray(fixture["expected_column_sample_sd"], dtype=float)
    ledger.check("sample SD reference", np.allclose(matrix.std(axis=0, ddof=1), expected_sd, rtol=0, atol=5e-15))
    ledger.check("candidate N frozen", fixture["candidate_valid_block_counts"] == [12,16,20,24,30,40])
    ledger.check("variance stress frozen", fixture["variance_stress_multipliers"] == [1.0,1.5,2.0])
    ledger.check("stream seeds frozen", fixture["primary_stream_seeds"] == [202608071,202608072])
    inv = fixture["invariants"]
    ledger.check("whole block required", inv["whole_block_resampling_required"] is True)
    ledger.check("single sign required", inv["single_rademacher_sign_per_sampled_block"] is True)
    ledger.check("independent coordinate resampling forbidden", inv["independent_coordinate_resampling_forbidden"] is True)
    ledger.check("pilot mean truth forbidden", inv["observed_pilot_mean_as_truth_forbidden"] is True)
    ledger.check("pilot direction truth forbidden", inv["observed_pilot_direction_as_truth_forbidden"] is True)
    ledger.check("real LLM forbidden", inv["real_llm_calls_forbidden"] is True)
    ledger.check("network forbidden", inv["network_access_forbidden"] is True)
    ledger.check("required API count", len(contract["target_implementation"]["required_public_api"]) == 6)
    ledger.check("preimpl counts frozen",
                 (contract["preimplementation_baseline"]["expected_pass"],
                  contract["preimplementation_baseline"]["expected_fail"],
                  contract["preimplementation_baseline"]["expected_warn"]) == EXPECTED_PREIMPLEMENTATION)
    ledger.check("full calibration gate false", contract["gates"]["full_oc_calibration_permitted"] is False)
    ledger.check("formal launch gate false", contract["gates"]["formal_llm_launch_permitted"] is False)

    # ----- 12 implementation acceptance checks -----
    module_path = root / TARGET_MODULE
    cli_path = root / TARGET_CLI
    module = None
    if not module_path.is_file():
        ledger.fail("implementation module exists", "oc_calibration.py absent")
    else:
        ledger.check("implementation module exists", True)
        try:
            module = load_module(module_path)
        except Exception as exc:
            ledger.fail("required public API", f"module import failed: {exc}")
        else:
            required = contract["target_implementation"]["required_public_api"]
            ledger.check("required public API", all(callable(getattr(module, x, None)) for x in required))
    if module is None and module_path.is_file():
        # public API check was already counted above
        pass
    elif module is None and not module_path.is_file():
        ledger.fail("required public API", "module absent")

    ledger.check("CLI exists", cli_path.is_file())

    if module_path.is_file():
        ledger.check("module no banned network imports", forbidden_imports(module_path) == [])
    else:
        ledger.fail("module no banned network imports", "module absent")

    if cli_path.is_file():
        ledger.check("CLI no banned network imports", forbidden_imports(cli_path) == [])
    else:
        ledger.fail("CLI no banned network imports", "CLI absent")

    if module is None:
        for name in [
            "Holm known case",
            "Wilson known case",
            "centering",
            "deterministic whole-block draw",
            "stress and truth shift",
            "Student-t p-value reference",
            "Student-t CI reference",
        ]:
            ledger.fail(name, "module absent")
    else:
        try:
            got = np.asarray(module.holm_adjust([0.01, 0.04, 0.03, 0.20]), dtype=float)
            expected = np.array([0.04, 0.09, 0.09, 0.20])
            ledger.check("Holm known case", np.allclose(got, expected, atol=1e-12, rtol=0))
        except Exception as exc:
            ledger.fail("Holm known case", exc)

        try:
            lo, hi = module.wilson_interval(50, 100, 0.95)
            ref = stats._proportion.proportion_confint if False else None
            # closed-form Wilson reference
            z = stats.norm.ppf(0.975)
            phat = 0.5
            den = 1 + z*z/100
            center = (phat + z*z/(200))/den
            half = z*math.sqrt(phat*(1-phat)/100 + z*z/(4*10000))/den
            ledger.check("Wilson known case",
                         abs(lo-(center-half)) < 1e-12 and abs(hi-(center+half)) < 1e-12)
        except Exception as exc:
            ledger.fail("Wilson known case", exc)

        try:
            raw = matrix + np.linspace(-0.2, 0.2, 28)[None, :]
            centered = np.asarray(module.center_residual_matrix(raw), dtype=float)
            ledger.check("centering", centered.shape == raw.shape and
                         np.max(np.abs(centered.mean(axis=0))) <= 1e-12)
        except Exception as exc:
            ledger.fail("centering", exc)

        try:
            seed = 202608071
            n = 12
            stress = 1.5
            got = np.asarray(module.draw_synthetic_blocks(matrix, n, stress, seed), dtype=float)
            rng = np.random.Generator(np.random.PCG64(seed))
            idx = rng.integers(0, matrix.shape[0], size=n)
            bits = rng.integers(0, 2, size=n)
            signs = np.where(bits == 0, -1.0, 1.0)
            expected = stress * matrix[idx] * signs[:, None]
            ledger.check("deterministic whole-block draw",
                         got.shape == (n, 28) and np.array_equal(got, expected))
        except Exception as exc:
            ledger.fail("deterministic whole-block draw", exc)

        try:
            truth = np.linspace(0.01, 0.28, 28)
            a = np.asarray(module.draw_synthetic_blocks(matrix, 16, 1.0, 123, truth), dtype=float)
            b = np.asarray(module.draw_synthetic_blocks(matrix, 16, 2.0, 123, truth), dtype=float)
            ledger.check("stress and truth shift",
                         np.allclose(b-truth, 2*(a-truth), atol=1e-12, rtol=0))
        except Exception as exc:
            ledger.fail("stress and truth shift", exc)

        try:
            sample = np.array([
                [0.2, 0.0], [0.4, 0.0], [0.1, 0.0], [0.3, 0.0],
                [0.5, 0.0], [0.6, 0.0], [0.2, 0.0], [0.4, 0.0],
            ])
            got = np.asarray(module.one_sample_t_pvalues(sample), dtype=float)
            ref = np.array([
                stats.ttest_1samp(sample[:,0], 0.0).pvalue,
                1.0,
            ])
            ledger.check("Student-t p-value reference", np.allclose(got, ref, atol=1e-12, rtol=0))
        except Exception as exc:
            ledger.fail("Student-t p-value reference", exc)

        try:
            sample = np.array([
                [0.2, -0.3], [0.4, 0.1], [0.1, 0.2], [0.3, -0.1],
                [0.5, 0.0], [0.6, 0.4], [0.2, -0.2], [0.4, 0.3],
            ])
            lo, hi = module.student_t_confidence_intervals(sample, 0.95)
            lo = np.asarray(lo, dtype=float); hi = np.asarray(hi, dtype=float)
            mean = sample.mean(axis=0)
            sem = sample.std(axis=0, ddof=1)/math.sqrt(sample.shape[0])
            crit = stats.t.ppf(0.975, sample.shape[0]-1)
            ledger.check("Student-t CI reference",
                         np.allclose(lo, mean-crit*sem, atol=1e-12, rtol=0) and
                         np.allclose(hi, mean+crit*sem, atol=1e-12, rtol=0))
        except Exception as exc:
            ledger.fail("Student-t CI reference", exc)

    # report
    for status, name, detail in ledger.rows:
        suffix = f" -- {detail}" if detail else ""
        print(f"{status} | {name}{suffix}")
    print("=" * 72)
    print(f"PASS={ledger.passed} FAIL={ledger.failed} WARN={ledger.warned}")

    if args.expect_preimplementation:
        expected = EXPECTED_PREIMPLEMENTATION
        actual = (ledger.passed, ledger.failed, ledger.warned)
        if actual != expected:
            print(f"PREIMPLEMENTATION BASELINE MISMATCH: expected={expected} actual={actual}")
            return 2
        print("PREIMPLEMENTATION BASELINE: MATCHED")
        return 1

    return 0 if ledger.failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
