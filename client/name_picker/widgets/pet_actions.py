# -*- coding: utf-8 -*-
"""桌宠动作帧：待机、招手、睡觉、学习、敲鼓、举鱼。

素材来自 pics/All.webp，由 utils/build_pet_actions.py 打包成 client/pet_actions.png。
每格 192×208，按行存放不同动作。
"""
import os
import math
import time

from PyQt5.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtWidgets import QWidget

from ..config import ui_path

CELL_W, CELL_H = 192, 208
SHEET_FILE = "pet_actions.png"

# 动作名 -> (行号, 帧数, 每帧毫秒)
ACTION_LAYOUT = {
    "idle":  (0, 7, 180),
    "wave":  (1, 4, 130),
    "sleep": (2, 6, 220),
    "study": (3, 6, 180),
    "drum":  (4, 6, 120),
    "fish":  (5, 8, 150),
}

_sheet_cache = None
_frames_cache = None


def load_action_sheet():
    """加载动作总表；文件缺失时返回 None（调用方回退到 pet.png）。"""
    global _sheet_cache
    if _sheet_cache is not None:
        return _sheet_cache or None

    path = ui_path(SHEET_FILE)
    pixmap = QPixmap(path) if os.path.exists(path) else QPixmap()
    _sheet_cache = pixmap if not pixmap.isNull() else False
    return _sheet_cache or None


def load_action_frames() -> dict:
    """把总表切成 {动作名: [QPixmap, ...]}，结果缓存。"""
    global _frames_cache
    if _frames_cache is not None:
        return _frames_cache

    sheet = load_action_sheet()
    frames = {}
    if sheet is not None:
        for name, (row, count, _interval) in ACTION_LAYOUT.items():
            items = []
            for col in range(count):
                items.append(
                    sheet.copy(col * CELL_W, row * CELL_H, CELL_W, CELL_H)
                )
            frames[name] = items
    _frames_cache = frames
    return frames


class ActionPlayer(QObject):
    """在桌宠窗口里播放动作帧。

    - loop=True 且给了 duration_ms：循环播放，时间到后结束；
    - hold_last=True：播到最后一帧后停住（睡觉用），直到 stop()；
    - 其余情况播完发出 finished。
    """

    frame_changed = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frames = load_action_frames()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.name = None
        self._index = 0
        self._loop = False
        self._hold_last = False
        self._holding = False
        self._until = 0.0

    def has(self, name: str) -> bool:
        return bool(self._frames.get(name))

    def play(self, name, loop=False, duration_ms=0, hold_last=False) -> bool:
        frames = self._frames.get(name)
        if not frames:
            return False
        if (
            name == self.name
            and self._timer.isActive()
            and loop
            and not self._holding
        ):
            return True

        self.name = name
        self._index = 0
        self._loop = bool(loop)
        self._hold_last = bool(hold_last)
        self._holding = False
        self._until = (time.monotonic() + duration_ms / 1000.0) if duration_ms else 0.0
        self._timer.setInterval(ACTION_LAYOUT[name][2])
        self._timer.start()
        self.frame_changed.emit()
        return True

    def stop(self):
        was_active = self.name is not None
        self._timer.stop()
        self.name = None
        self._index = 0
        self._holding = False
        if was_active:
            self.frame_changed.emit()

    def current(self):
        frames = self._frames.get(self.name or "")
        if not frames:
            return None
        return frames[min(self._index, len(frames) - 1)]

    @property
    def holding(self) -> bool:
        return self._holding

    def _tick(self):
        frames = self._frames.get(self.name or "")
        if not frames:
            self.stop()
            return

        if self._until and time.monotonic() >= self._until:
            self._finish()
            return

        if self._index + 1 >= len(frames):
            if self._loop:
                self._index = 0
                self.frame_changed.emit()
                return
            self._index = len(frames) - 1
            self._finish()
            return

        self._index += 1
        self.frame_changed.emit()

    def _finish(self):
        self._timer.stop()
        if self._hold_last:
            self._holding = True
            self.frame_changed.emit()
            return
        self.name = None
        self._holding = False
        self.frame_changed.emit()
        self.finished.emit()


class ActionFish(QWidget):
    """防拖堂页上的大肥鱼：透明背景，播完睡觉动作后定格，并轻微呼吸浮动。"""

    def __init__(self, action="sleep", size=300, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._frames = load_action_frames().get(action) or []
        self._fallback = QPixmap(ui_path("pet.png"))
        self._index = 0
        self._phase = 0.0

        frame_h = max(1, int(size * CELL_H / CELL_W))
        self.setFixedSize(int(size), frame_h)

        self._timer = QTimer(self)
        self._timer.setInterval(ACTION_LAYOUT.get(action, (0, 0, 180))[2])
        self._timer.timeout.connect(self._tick)
        if self._frames:
            self._timer.start()

        self._bob = QTimer(self)
        self._bob.setInterval(60)
        self._bob.timeout.connect(self._on_bob)
        self._bob.start()

    def _tick(self):
        if not self._frames:
            return
        if self._index + 1 < len(self._frames):
            self._index += 1
            self.update()
        else:
            self._timer.stop()

    def _on_bob(self):
        self._phase += 0.08
        if self._phase > math.pi * 2:
            self._phase -= math.pi * 2
        self.update()

    def stop(self):
        """窗口关闭时停掉两个定时器，避免隐藏后还在空转。"""
        self._timer.stop()
        self._bob.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self._frames:
            frame = self._frames[min(self._index, len(self._frames) - 1)]
            offset = int(math.sin(self._phase) * 4)
        else:
            frame = self._fallback
            offset = 0

        if frame is None or frame.isNull():
            return

        scaled = frame.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2 + offset
        painter.drawPixmap(x, y, scaled)
