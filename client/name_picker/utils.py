# -*- coding: utf-8 -*-
"""纯工具函数：版本解析、Excel/CSV 读写、加权抽样。"""
import os
import re
import csv
import random
from typing import List, Tuple, Union

from openpyxl import load_workbook

from .config import DEFAULT_GROUP, HEADER_WORDS


def parse_version(v) -> tuple:
    try:
        parts = str(v).strip().lstrip("vV").split(".")
        result = []
        for p in parts:
            m = re.match(r"^\d+", p)
            result.append(int(m.group()) if m else 0)
        return tuple(result) if result else (0,)
    except (ValueError, AttributeError, TypeError):
        return (0,)


def col_to_index(col_id: str) -> int:
    """A -> 1, B -> 2, AA -> 27 ..."""
    col_id = (col_id or "").strip().upper()
    if not col_id or not col_id.isalpha():
        raise ValueError(f"非法的列号：{col_id!r}")
    idx = 0
    for ch in col_id:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx


def read_xlsx_columns(
    file_path: str, name_col: str, group_col: str = None
) -> Tuple[bool, Union[str, List[Tuple[str, str]]]]:
    if not os.path.exists(file_path):
        return False, "文件不存在！"
    try:
        wb = load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        name_idx = col_to_index(name_col)
        group_idx = col_to_index(group_col) if group_col else None
        cols = [name_idx] + ([group_idx] if group_idx else [])
        min_c, max_c = min(cols), max(cols)
        off_n = name_idx - min_c
        off_g = (group_idx - min_c) if group_idx else None

        rows: List[Tuple[str, str]] = []
        for row in ws.iter_rows(min_col=min_c, max_col=max_c, values_only=True):
            name_val = row[off_n] if off_n < len(row) else None
            if name_val is None:
                continue
            name = str(name_val).strip()
            if not name or name.lower() in HEADER_WORDS:
                continue
            group = DEFAULT_GROUP
            if off_g is not None and off_g < len(row) and row[off_g] is not None:
                g = str(row[off_g]).strip()
                if g and g.lower() not in HEADER_WORDS:
                    group = g
            rows.append((name, group))
        wb.close()
        return True, rows
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def read_csv_names(file_path: str) -> Tuple[bool, Union[str, List[Tuple[str, str]]]]:
    if not os.path.exists(file_path):
        return False, "文件不存在！"
    try:
        rows: List[Tuple[str, str]] = []
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                if not row:
                    continue
                name = row[0].strip()
                if not name or name.lower() in HEADER_WORDS:
                    continue
                group = DEFAULT_GROUP
                if len(row) > 1 and row[1].strip():
                    g = row[1].strip()
                    if g.lower() not in HEADER_WORDS:
                        group = g
                rows.append((name, group))
        return True, rows
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def save_csv(path: str, records: List[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["姓名", "分组"])
        for r in records:
            writer.writerow([r["name"], r["group"]])


def weighted_sample(pool: List[Tuple[str, float]], k: int) -> List[str]:
    items = [(n, w) for n, w in pool if w > 0]
    result: List[str] = []
    for _ in range(min(k, len(items))):
        total = sum(w for _, w in items)
        if total <= 0:
            break
        r = random.random() * total
        acc, chosen = 0.0, len(items) - 1
        for i, (_, w) in enumerate(items):
            acc += w
            if r < acc:
                chosen = i
                break
        result.append(items.pop(chosen)[0])
    return result