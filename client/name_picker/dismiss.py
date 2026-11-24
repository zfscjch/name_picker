# -*- coding: utf-8 -*-
"""防拖堂：检测下课时间与演示软件进程（WPS 演示 / PowerPoint 等），
弹出全屏“保持安静”界面。

- 下课时间按星期分组：group_a = 周一/周三/周五/周六，group_b = 周二/周四；
  每个分组有自己的 times 列表，days 中的星期才生效；
  未出现在任何分组的星期（当前为周日）不触发。
- 一天内多个时间点，每个时间点独立触发一次；跨天自动重置。
- 关闭“保持安静”界面后，结束所有正在运行的演示进程。
"""
import os
import json
import subprocess
from datetime import datetime, time as dtime

from PyQt5.QtCore import QObject, QTimer, Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QLabel, QShortcut, QVBoxLayout, QWidget,
)

from .hotkey import HotkeyListener, DEFAULT_HOTKEY
from .config import ui_path
from .widgets.pet_actions import ActionFish

DISMISS_CONFIG_PATH = ui_path("dismiss_config.json")

DEFAULT_PRESENTATION_PROCESSES = ["wpp.exe", "POWERPNT.EXE"]

# 分组默认值（星期：0=周一 ... 6=周日）
DEFAULT_DISMISS_GROUPS = {
    "group_a": {
        "label": "周一 / 周三 / 周五 / 周六",
        "days": [0, 2, 4, 5],
        "times": ["08:40", "09:30", "10:30", "11:20",
                  "14:30", "15:20", "16:10", "17:00"],
    },
    "group_b": {
        "label": "周二 / 周四",
        "days": [1, 3],
        "times": ["08:40", "09:30", "10:30", "11:20",
                  "14:30", "15:20", "16:10", "17:00"],
    },
}

DEFAULT_DISMISS_CONFIG = {
    "enabled": True,
    "dismiss_times": DEFAULT_DISMISS_GROUPS,
    "check_interval_seconds": 3,
    "presentation_processes": list(DEFAULT_PRESENTATION_PROCESSES),
    "silence_title": "保持安静",
    "silence_hint": "上课已结束，请保持安静\n按 Esc 或 Ctrl+W 关闭本窗口",
    "hotkey": DEFAULT_HOTKEY,        # 新增
}

STARTUP_GRACE_SECONDS = 300


# ---------- 分组工具 ----------
def _normalize_times(raw) -> list:
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _normalize_days(raw) -> list:
    if not isinstance(raw, list):
        return []
    days = []
    for x in raw:
        try:
            d = int(x)
        except (TypeError, ValueError):
            continue
        if 0 <= d <= 6 and d not in days:
            days.append(d)
    days.sort()
    return days


def _deep_copy_groups(groups: dict) -> dict:
    result = {}
    for k, v in groups.items():
        result[k] = {
            "label": str(v.get("label", "")),
            "days": list(v.get("days", [])),
            "times": list(v.get("times", [])),
        }
    return result


# ---------- 配置读写 ----------
def default_dismiss_config() -> dict:
    """返回一份全新的默认防拖堂配置。"""
    return {
        "enabled": DEFAULT_DISMISS_CONFIG["enabled"],
        "dismiss_times": _deep_copy_groups(DEFAULT_DISMISS_GROUPS),
        "check_interval_seconds": DEFAULT_DISMISS_CONFIG["check_interval_seconds"],
        "presentation_processes": list(DEFAULT_PRESENTATION_PROCESSES),
        "silence_title": DEFAULT_DISMISS_CONFIG["silence_title"],
        "silence_hint": DEFAULT_DISMISS_CONFIG["silence_hint"],
        "hotkey": DEFAULT_HOTKEY,
    }


def load_dismiss_config() -> dict:
    cfg = default_dismiss_config()
    if not os.path.exists(DISMISS_CONFIG_PATH):
        # 首次运行没有配置文件：自动写一份默认配置
        ensure_dismiss_config()
        return cfg
    try:
        with open(DISMISS_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return cfg

    if "hotkey" in data:
        hk = str(data.get("hotkey", "")).strip()
        if hk:
            cfg["hotkey"] = hk

    # ---- 下课时间：新格式 dict ----
    raw_times = data.get("dismiss_times")
    if isinstance(raw_times, dict):
        groups = {}
        for k, v in raw_times.items():
            if not isinstance(v, dict):
                continue
            groups[str(k)] = {
                "label": str(v.get("label", "")),
                "days": _normalize_days(v.get("days", [])),
                "times": _normalize_times(v.get("times", [])),
            }
        if groups:
            cfg["dismiss_times"] = groups

    # ---- 旧格式：列表 -> 当作“每天都生效”放进 group_a ----
    elif isinstance(raw_times, list):
        old_times = _normalize_times(raw_times)
        if old_times:
            cfg["dismiss_times"] = {
                "group_a": {
                    "label": "每天（来自旧配置）",
                    "days": [0, 1, 2, 3, 4, 5, 6],
                    "times": old_times,
                },
                "group_b": {
                    "label": "周二 / 周四",
                    "days": [1, 3],
                    "times": [],
                },
            }

    # ---- 更旧格式：单个字符串 ----
    elif "dismiss_time" in data:
        old = str(data.get("dismiss_time", "")).strip()
        if old:
            cfg["dismiss_times"] = {
                "group_a": {
                    "label": "每天（来自旧配置）",
                    "days": [0, 1, 2, 3, 4, 5, 6],
                    "times": [old],
                },
                "group_b": {
                    "label": "周二 / 周四",
                    "days": [1, 3],
                    "times": [],
                },
            }

    # ---- 演示进程 ----
    procs = data.get("presentation_processes")
    if isinstance(procs, list):
        cleaned = [str(x).strip() for x in procs if str(x).strip()]
        if cleaned:
            cfg["presentation_processes"] = cleaned
    elif isinstance(procs, str) and procs.strip():
        parts = [p.strip() for p in procs.replace(";", ",").split(",") if p.strip()]
        if parts:
            cfg["presentation_processes"] = parts

    if "enabled" in data:
        cfg["enabled"] = bool(data["enabled"])
    if "check_interval_seconds" in data:
        cfg["check_interval_seconds"] = data["check_interval_seconds"]
    if "silence_title" in data:
        cfg["silence_title"] = str(data["silence_title"])
    if "silence_hint" in data:
        cfg["silence_hint"] = str(data["silence_hint"])
    return cfg


def save_dismiss_config(cfg: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(DISMISS_CONFIG_PATH), exist_ok=True)
        with open(DISMISS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def ensure_dismiss_config() -> bool:
    """确保 dismiss_config.json 存在；缺失时自动写入默认配置。"""
    if os.path.exists(DISMISS_CONFIG_PATH):
        return True
    return save_dismiss_config(default_dismiss_config())


def parse_time(text: str):
    """把 'HH:MM' 解析成 datetime.time，失败返回 None。"""
    try:
        h, m = str(text).strip().split(":")
        h, m = int(h), int(m)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return None
        return dtime(h, m)
    except Exception:
        return None


# ---------- Windows 进程查询/结束 ----------
def get_running_exe_names() -> set:
    if os.name != "nt":
        return set()
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        output = subprocess.check_output(
            ["tasklist", "/NH", "/FO", "CSV"],
            creationflags=creationflags,
            stderr=subprocess.DEVNULL,
        ).decode("mbcs", errors="ignore")
    except Exception:
        return set()

    names = set()
    for line in output.splitlines():
        line = line.strip()
        if not line or not line.startswith('"'):
            continue
        end = line.find('"', 1)
        if end > 1:
            names.add(line[1:end].lower())
    return names


def is_any_process_running(processes) -> bool:
    if not processes:
        return False
    running = get_running_exe_names()
    if not running:
        return False
    for p in processes:
        if str(p).strip().lower() in running:
            return True
    return False


def kill_one_process(exe_name: str) -> bool:
    if os.name != "nt":
        return False
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            ["taskkill", "/F", "/IM", exe_name],
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return True
    except Exception:
        return False


def kill_processes(processes) -> bool:
    ok = False
    for p in processes or []:
        name = str(p).strip()
        if not name:
            continue
        if kill_one_process(name):
            ok = True
    return ok


# ---------- “保持安静”全屏窗口 ----------
class SilenceWindow(QWidget):
    def __init__(self, title="保持安静", hint="", on_close=None):
        super().__init__(None)
        self._on_close = on_close
        self._closed = False
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("background-color: #0b1a2b;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(32)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "color: #ffcc00; font-size: 72px; font-weight: bold;"
        )

        hint_label = QLabel(hint or "上课已结束，请保持安静\n按 Esc 或 Ctrl+W 关闭本窗口")
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setStyleSheet("color: #e0e6ef; font-size: 26px;")

        bubble_label = QLabel("呼…安静休息一下吧～")
        bubble_label.setAlignment(Qt.AlignCenter)
        bubble_label.setStyleSheet("color: #9fd0ff; font-size: 22px;")

        # 大肥鱼：播完“打哈欠 → 蜷起来睡觉”的动作后定格，陪大家安静休息
        fish_size = 340
        try:
            screen_h = QApplication.primaryScreen().availableGeometry().height()
            fish_size = max(220, min(340, int(screen_h * 0.42)))
        except Exception:
            pass
        self._fish = ActionFish("sleep", size=fish_size, parent=self)

        layout.addStretch(1)
        layout.addWidget(title_label)
        layout.addWidget(hint_label)
        layout.addSpacing(18)
        layout.addWidget(bubble_label)
        layout.addWidget(self._fish, 0, Qt.AlignHCenter)
        layout.addStretch(1)

        sc1 = QShortcut(QKeySequence("Esc"), self)
        sc1.activated.connect(self.close)
        sc2 = QShortcut(QKeySequence("Ctrl+W"), self)
        sc2.activated.connect(self.close)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_W:
            self.close()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        try:
            self._fish.stop()
        except Exception:
            pass
        if self._closed:
            return
        self._closed = True
        if self._on_close:
            try:
                self._on_close()
            except Exception:
                pass
        super().closeEvent(event)


# ---------- 后台守卫 ----------
class DismissGuard(QObject):
    """按星期分组的下课时间守卫。

    每个 (日期, 时间点) 独立触发一次；跨天自动清空已处理记录。
    触发时只根据“今天星期几”所归属分组的时间列表判断。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = load_dismiss_config()
        self._handled = set()          # "YYYY-MM-DD HH:MM"
        self._last_date = None
        self._silence_window = None
        self._pending_processes = []

        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_ms())
        self._timer.timeout.connect(self._tick)
        self._hotkey_listener = None

    # ---------- 配置 ----------
    def _interval_ms(self) -> int:
        try:
            sec = int(self.cfg.get("check_interval_seconds", 3))
        except (TypeError, ValueError):
            sec = 3
        return max(1, sec) * 1000

    def _groups(self) -> dict:
        groups = self.cfg.get("dismiss_times")
        if isinstance(groups, dict):
            return groups
        return {}

    def _times_for_weekday(self, weekday: int) -> list:
        """返回指定星期几（0=周一…6=周日）对应的下课时间列表。"""
        for group in self._groups().values():
            if not isinstance(group, dict):
                continue
            if weekday in group.get("days", []):
                return [str(t).strip() for t in group.get("times", []) if str(t).strip()]
        return []

    def _presentation_processes(self) -> list:
        raw = self.cfg.get("presentation_processes")
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        return list(DEFAULT_PRESENTATION_PROCESSES)

    # ---------- 生命周期 ----------
    def start(self):
        self.cfg = load_dismiss_config()
        self._timer.setInterval(self._interval_ms())
        self._init_handled_on_start()
        self._timer.start()
        self._start_hotkey_listener()

    def stop(self):
        self._timer.stop()
        self._stop_hotkey_listener()

    def reload_config(self):
        self.cfg = load_dismiss_config()
        self._timer.setInterval(self._interval_ms())
        self._init_handled_on_start()
        self._start_hotkey_listener()      # 快捷键可能被改，重启监听

    def close_silence_window(self):
        if self._silence_window is not None:
            try:
                self._silence_window.close()
            except Exception:
                pass
            self._silence_window = None

    # ---------- 全局快捷键 ----------
    def _hotkey_string(self) -> str:
        cfg = self.cfg or {}
        hk = cfg.get("hotkey")
        if isinstance(hk, str) and hk.strip():
            return hk.strip()
        return DEFAULT_HOTKEY

    def _start_hotkey_listener(self):
        """(重新)启动全局快捷键监听。"""
        self._stop_hotkey_listener()
        listener = HotkeyListener(self._hotkey_string(), parent=self)
        listener.triggered.connect(self._on_hotkey_triggered)
        listener.error_occurred.connect(
            lambda msg: print(f"[防拖堂] 全局快捷键监听失败：{msg}")
        )
        listener.start()
        self._hotkey_listener = listener

    def _stop_hotkey_listener(self):
        if self._hotkey_listener is not None:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None

    def _on_hotkey_triggered(self):
        """主线程槽函数：快捷键触发时弹出保持安静窗口。

        行为约定（与自动触发保持一致）：
          - 不受 cfg["enabled"] 影响（用户显式按键就是要弹）；
          - 若已有窗口，_show_silence() 会自动 raise，不会重复创建；
          - 关闭窗口后仍会按配置结束演示进程（与自动触发一致）。
        如不希望关闭后结束演示进程，可把下面这行改为 self._pending_processes = []
        """
        self._pending_processes = self._presentation_processes()
        self._show_silence()

    # ---------- 内部 ----------
    def _init_handled_on_start(self):
        """按“今天星期几”取当天时间列表；把已过去较久的标记为已处理。"""
        now = datetime.now()
        today = now.date().isoformat()
        self._last_date = today
        self._handled = set()
        for t_str in self._times_for_weekday(now.weekday()):
            t = parse_time(t_str)
            if t is None:
                continue
            target_dt = datetime.combine(now.date(), t)
            if (now - target_dt).total_seconds() > STARTUP_GRACE_SECONDS:
                self._handled.add(f"{today} {t_str}")

    def _tick(self):
        if not self.cfg.get("enabled", True):
            return

        now = datetime.now()
        today = now.date().isoformat()
        weekday = now.weekday()  # 0=周一 … 6=周日

        if self._last_date != today:
            self._last_date = today
            self._handled = {k for k in self._handled if k.startswith(today)}

        today_times = self._times_for_weekday(weekday)
        if not today_times:
            return

        processes = self._presentation_processes()

        for t_str in today_times:
            t = parse_time(t_str)
            if t is None:
                continue
            key = f"{today} {t_str}"
            if key in self._handled:
                continue
            if now.time() < t:
                continue

            self._handled.add(key)

            if self._silence_window is not None:
                continue

            if is_any_process_running(processes):
                self._pending_processes = list(processes)
                self._show_silence()
                break

    def _show_silence(self):
        if self._silence_window is not None:
            try:
                self._silence_window.raise_()
                self._silence_window.activateWindow()
            except Exception:
                pass
            return

        title = str(self.cfg.get("silence_title") or "保持安静")
        hint = str(self.cfg.get("silence_hint") or "")
        self._silence_window = SilenceWindow(
            title=title, hint=hint, on_close=self._on_silence_closed,
        )
        self._silence_window.showFullScreen()
        self._silence_window.raise_()
        self._silence_window.activateWindow()
        self._silence_window.setFocus()

    def _on_silence_closed(self):
        self._silence_window = None
        procs = self._pending_processes or self._presentation_processes()
        self._pending_processes = []
        kill_processes(procs)