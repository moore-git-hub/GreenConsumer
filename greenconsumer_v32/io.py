"""统一、最小化的 CSV/JSON 输入输出函数。"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Mapping


def write_json(path: Path, payload: Mapping) -> None:
    """以 UTF-8、稳定 key 顺序写 JSON，便于审计和 Git diff。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[Mapping]) -> None:
    """写字典行列表；字段按首次出现顺序稳定收集。"""
    if not rows:
        return
    fields: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(str(key))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    """读取 UTF-8 CSV；类型转换由具体分析模块负责。"""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
