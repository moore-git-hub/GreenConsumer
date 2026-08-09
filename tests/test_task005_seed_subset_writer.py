from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import replication_config as rc


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


def _raw_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _canonical_raw(row: dict) -> dict:
    out = dict(row)
    for field in (
        "master_seed",
        "replicate_index",
        "simulation_seed",
        "requested_llm_seed",
        "condition_count",
        "profile_seed",
        "network_seed",
        "target_seed",
        "python_hash_seed",
    ):
        out[field] = int(out[field])
    out["execution_order"] = tuple(json.loads(out["execution_order"]))
    return out


def test_subset_writer() -> None:
    full = rc.build_seed_ledger(
        2026080904,
        2,
        llm_seed_supported="unknown",
        provider_model="qwen-plus",
        provider_system_fingerprint="unknown",
    )
    with tempfile.TemporaryDirectory(prefix="task005_seed_subset_") as tmp:
        root = Path(tmp)
        full_path = root / "full.csv"
        rc.write_seed_ledger_csv(full, full_path)
        reread_full = rc.read_seed_ledger_csv(full_path)
        check("full writer unchanged", reread_full == full, reread_full)

        for rid in ("R001", "R002"):
            path = root / f"{rid}.csv"
            rc.write_seed_ledger_subset_csv(full, [rid], path)
            rows = _raw_rows(path)
            check(f"{rid} subset one row", len(rows) == 1, rows)
            raw = _canonical_raw(rows[0])
            expected = next(row for row in full if row["replicate_id"] == rid)
            check(f"{rid} replicate_id", raw["replicate_id"] == rid, raw)
            check(f"{rid} index preserved", raw["replicate_index"] == expected["replicate_index"], raw)
            for field in (
                "simulation_seed",
                "requested_llm_seed",
                "profile_seed",
                "network_seed",
                "target_seed",
                "python_hash_seed",
            ):
                check(f"{rid} {field} exact", raw[field] == expected[field], (raw, expected))

        try:
            rc.write_seed_ledger_subset_csv(full, ["R003"], root / "bad.csv")
        except ValueError:
            check("unknown R003 fails", True)
        else:
            check("unknown R003 fails", False)

        try:
            rc.write_seed_ledger_subset_csv(full, ["R001", "R001"], root / "dup.csv")
        except ValueError:
            check("duplicate requested ID fails", True)
        else:
            check("duplicate requested ID fails", False)

        tampered = [dict(row) for row in full]
        tampered[1]["simulation_seed"] += 1
        try:
            rc.write_seed_ledger_subset_csv(tampered, ["R002"], root / "tampered.csv")
        except ValueError:
            check("tampered full ledger fails", True)
        else:
            check("tampered full ledger fails", False)

        try:
            rc.validate_seed_ledger([full[1]])
        except ValueError:
            check("standalone R002 still invalid full ledger", True)
        else:
            check("standalone R002 still invalid full ledger", False)


def main() -> int:
    test_subset_writer()
    print("Passed:", P)
    print("Failed:", F)
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
