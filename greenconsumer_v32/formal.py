"""已完成正式实验的只读状态接口。

本模块故意不包含 launcher。F001-F010 已完成且关闭；clean workflow 只
允许读取归档身份，不能通过这里创建 F011 或重新运行 formal sample。
"""
from __future__ import annotations

import json

from .config import PROJECT_ROOT

FORMAL_ROOT = PROJECT_ROOT / "reproducibility" / "formal_v32_n10"
EVIDENCE = FORMAL_ROOT / "evidence"


def formal_status() -> dict:
    """读取正式 batch/analysis summary，并显式返回 CLOSED 状态。"""
    batch_path = EVIDENCE / "formal_batch_summary.json"
    analysis_path = EVIDENCE / "formal_analysis_summary.json"
    if not batch_path.exists() or not analysis_path.exists():
        return {
            "status": "ARCHIVE_INCOMPLETE",
            "formal_root": str(FORMAL_ROOT),
        }

    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    return {
        "status": "FORMAL_CLOSED",
        "formal_batch_id": batch.get("formal_batch_id"),
        "formal_execution_status": batch.get("status"),
        "valid_blocks": batch.get("valid_blocks"),
        "attempt_blocks": batch.get("attempt_blocks"),
        "analysis_status": analysis.get("status"),
        "planned_N_achieved": analysis.get("planned_N_achieved"),
        "source_head": batch.get("source_head"),
        "F011_or_later_permitted": False,
        "rerun_formal_permitted": False,
        "formal_root": str(FORMAL_ROOT),
    }
