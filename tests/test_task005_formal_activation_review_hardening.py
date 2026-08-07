#!/usr/bin/env python
from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import run_formal_launch as launch
import run_replications
import run_experiments

passed=failed=0
def check(name,ok,actual=""):
    global passed,failed
    if ok: passed+=1
    else:
        failed+=1; print(f"FAIL {name}: {actual}")

# 1. Full execution-source validator must include a 5A scientific source that
# is not one of the six activation plumbing files.
contract=launch._read_json_object(ROOT/launch.CONTRACT_PATH)
activation={
    "activation_source_sha256":{
        rel:launch._sha256_file(ROOT/rel) for rel in (
            "run_formal_launch.py","run_formal_replications.py","run_replications.py",
            "run_experiments.py","replication_config.py","replication_analysis.py")
    }
}
orig=launch._sha256_file
def fake_sha(path):
    if Path(path).name=="simulation_core.py": return "0"*64
    return orig(path)
launch._sha256_file=fake_sha
try:
    blocked=False
    try: launch._validate_execution_source_hashes(ROOT,contract,activation)
    except launch.FormalLaunchGateError: blocked=True
finally:
    launch._sha256_file=orig
check("5A simulation_core source is monitored",blocked,blocked)

# 2. Syntactically valid fake child markers are insufficient: they must bind
# to the actual authorization1.1 artifact.
fake_env={
 "TASK005_FORMAL_AUTHORIZATION_SHA256":"0"*64,
 "TASK005_FORMAL_ACTIVATION_CODE_HEAD":"a"*40,
 "TASK005_FORMAL_AUTHORIZATION_PATH":str(ROOT/launch.AUTHORIZATION_PATH),
 "TASK005_FORMAL_LAUNCH_CONTRACT_SHA256":launch.EXPECTED_LAUNCH_CONTRACT_SHA,
}
blocked=False
try:
    run_experiments._validate_formal_child_authorization(
        "task005-formal-v1","real",environ=fake_env)
except run_experiments.ReplicationStartupError:
    blocked=True
check("fake formal child provenance rejected",blocked,blocked)

# 3. Dedicated parent propagation contains the artifact path and launch SHA.
ledger={"python_hash_seed":3}
ctx={
 "authorization_artifact_sha256":"b"*64,
 "authorization_artifact_path":str(ROOT/launch.AUTHORIZATION_PATH),
 "activation_code_head":"a"*40,
 "launch_contract_sha256":launch.EXPECTED_LAUNCH_CONTRACT_SHA,
}
env=run_replications.build_child_env(
    ledger,llm_mode="real",base_env={},formal_activation_context=ctx)
check("child env authorization path propagated",
      env.get("TASK005_FORMAL_AUTHORIZATION_PATH")==ctx["authorization_artifact_path"],env)
check("child env launch SHA propagated",
      env.get("TASK005_FORMAL_LAUNCH_CONTRACT_SHA256")==launch.EXPECTED_LAUNCH_CONTRACT_SHA,env)

print("TASK_005 ACTIVATION REVIEW HARDENING RESULTS")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
raise SystemExit(1 if failed else 0)
