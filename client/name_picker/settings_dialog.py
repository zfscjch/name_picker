# -*- coding: utf-8 -*-
"""设置对话框：防拖堂开关、按星期分组的下课时间、要检测/结束的演示进程。"""
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog, QMessageBox

from .config import ui_path
from .dismiss import (
    load_dismiss_config, save_dismiss_config, parse_time,
    DEFAULT_PRESENTATION_PROCESSES,
)

SettingsUIForm, _ = uic.loadUiType(ui_path("settings_dialog.ui"))


def _times_to_text(times) -> str:
    return "\n".join(str(x) for x in (times or []))


def _parse_times_from_text(text: str):
    """返回 (normalized_list, error_message)。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    normalized, seen = [], set()
    for ln in lines:
        t = parse_time(ln)
        if t is None:
            return None, f"时间格式不正确：{ln}（请使用 HH:MM，例如 17:30）"
        s = f"{t.hour:02d}:{t.minute:02d}"
        if s in seen:
            continue
        seen.add(s)
        normalized.append(s)
    return normalized, None


class SettingsDialog(QDialog, SettingsUIForm):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        cfg = load_dismiss_config()
        groups = cfg.get("dismiss_times") or {}

        self.enable_cb.setChecked(bool(cfg.get("enabled", True)))

        group_a = groups.get("group_a") or {}
        group_b = groups.get("group_b") or {}
        self.group_a_edit.setPlainText(_times_to_text(group_a.get("times", [])))
        self.group_b_edit.setPlainText(_times_to_text(group_b.get("times", [])))
        self.group_a_box.setTitle(str(group_a.get("label") or "周一 / 周三 / 周五 / 周六"))
        self.group_b_box.setTitle(str(group_b.get("label") or "周二 / 周四"))

        procs = cfg.get("presentation_processes") or list(DEFAULT_PRESENTATION_PROCESSES)
        self.proc_edit.setText(", ".join(procs))

        self.buttonBox.accepted.connect(self._on_accept)
        self.buttonBox.rejected.connect(self.reject)

    def _on_accept(self):
        times_a, err_a = _parse_times_from_text(self.group_a_edit.toPlainText())
        if err_a:
            QMessageBox.warning(self, "提示", f"[周一/周三/周五/周六] {err_a}")
            return
        times_b, err_b = _parse_times_from_text(self.group_b_edit.toPlainText())
        if err_b:
            QMessageBox.warning(self, "提示", f"[周二/周四] {err_b}")
            return
        if not times_a and not times_b:
            QMessageBox.warning(self, "提示", "两组下课时间不能同时为空。")
            return

        proc_raw = self.proc_edit.text()
        procs = [p.strip() for p in proc_raw.replace(";", ",").split(",") if p.strip()]
        if not procs:
            QMessageBox.warning(self, "提示", "请至少填写一个要检测的进程名。")
            return

        cfg = load_dismiss_config()
        groups = cfg.get("dismiss_times") or {}

        # 保留原 label / days，只更新 times
        group_a = groups.get("group_a") or {}
        group_a.setdefault("label", "周一 / 周三 / 周五 / 周六")
        group_a.setdefault("days", [0, 2, 4, 5])
        group_a["times"] = times_a

        group_b = groups.get("group_b") or {}
        group_b.setdefault("label", "周二 / 周四")
        group_b.setdefault("days", [1, 3])
        group_b["times"] = times_b

        cfg["enabled"] = self.enable_cb.isChecked()
        cfg["dismiss_times"] = {"group_a": group_a, "group_b": group_b}
        cfg["presentation_processes"] = procs
        cfg.pop("dismiss_time", None)

        if not save_dismiss_config(cfg):
            QMessageBox.warning(self, "提示", "保存设置失败。")
            return
        self.accept()