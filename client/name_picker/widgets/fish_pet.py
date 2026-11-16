# -*- coding: utf-8 -*-
"""大肥鱼桌宠：点击抽名、定时走动、气泡提醒、右键菜单。"""
import os
import math
import json
import datetime
from datetime import datetime as dt  # 用于 dt.now()

from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QPainter, QPixmap, QTransform
from PyQt5.QtWidgets import (
    QWidget, QMenu, QAction, QMessageBox, QApplication,
)

from ..config import (
    PET_SIZE_RATIO, PET_SIZE_MIN, PET_SIZE_MAX, ui_path,
)
from ..autostart import set_autostart, is_autostart_enabled
from .speech_bubble import SpeechBubble
from .pet_result import PetResultDialog


class FishPet(QWidget):
    """大肥鱼桌宠。"""

    def __init__(self, owner):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.owner = owner
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        pet_size = self._calc_pet_size()
        self.setFixedSize(pet_size, pet_size)
        self.setToolTip("点我抽人｜右键菜单")

        # 1. 默认静止图片
        self.pixmap = QPixmap(ui_path("pet.png"))

        # 2. 8 帧行走图片
        self.walk_pixmaps = []
        for i in range(1, 9):
            path = ui_path(f"pet_walk_{i}.png")
            if os.path.exists(path):
                self.walk_pixmaps.append(QPixmap(path))
            else:
                self.walk_pixmaps.append(self.pixmap)

        self._walk_frame_index = 0
        self._walk_frame_tick = 0

        self._interaction_enabled = True
        self._dragging = False
        self._press_pos: QPoint = None
        self._drag_offset: QPoint = None
        self._phase = 0.0

        # 行走状态
        self._is_walking = False
        self._walk_direction = -1  # -1 左, 1 右
        self._walk_speed = 2

        self._anim = QTimer(self)
        self._anim.setInterval(60)
        self._anim.timeout.connect(self._on_anim)
        self._anim.start()

        self._walk_timer = QTimer(self)
        self._walk_timer.setInterval(50)
        self._walk_timer.timeout.connect(self._on_walk_tick)

        self._schedule_timer = QTimer(self)
        self._schedule_timer.setInterval(60000)
        self._schedule_timer.timeout.connect(self._check_walk_schedule)
        self._schedule_timer.start()

        self._bubble = None
        self._result_dialog = None
        self._last_triggered = set()
        self._last_day = -1

        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(15000)
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._reminder_timer.start()

        self._place_default()
        QTimer.singleShot(2000, self._check_reminders)
        QTimer.singleShot(3000, self._check_walk_schedule)

    # ---------- 行走逻辑 ----------
    def _check_walk_schedule(self):
        if not self._interaction_enabled or not self.isVisible():
            self._stop_walking()
            return

        config_path = ui_path("pet_walk.json")
        if not os.path.exists(config_path):
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            time_ranges = data.get("walk_time_ranges", [])
            self._walk_speed = int(data.get("walk_speed", 2))
        except Exception:
            return

        now_time = dt.now().time()
        should_walk = False

        for tr in time_ranges:
            try:
                start = dt.strptime(tr["start"], "%H:%M").time()
                end = dt.strptime(tr["end"], "%H:%M").time()
                if start <= now_time <= end:
                    should_walk = True
                    break
            except Exception:
                continue

        if should_walk and not self._is_walking:
            self._start_walking()
        elif not should_walk and self._is_walking:
            self._stop_walking()

    def _start_walking(self):
        self._is_walking = True
        self._walk_frame_index = 0
        self._walk_frame_tick = 0
        self._walk_timer.start()

    def _stop_walking(self):
        self._is_walking = False
        self._walk_timer.stop()
        self._walk_frame_index = 0
        self.update()

    def _on_walk_tick(self):
        if self._dragging:
            return

        self._walk_frame_tick += 1
        if self._walk_frame_tick >= 3:
            self._walk_frame_tick = 0
            self._walk_frame_index = (self._walk_frame_index + 1) % 8
            self.update()

        screen = QApplication.primaryScreen().availableGeometry()
        current_x = self.x()

        if self._walk_direction < 0 and current_x <= screen.left():
            self._walk_direction = 1
        elif self._walk_direction > 0 and current_x + self.width() >= screen.right():
            self._walk_direction = -1

        new_x = current_x + (self._walk_speed * self._walk_direction)
        new_x = max(screen.left(), min(new_x, screen.right() - self.width()))
        self.move(new_x, self.y())
    # --------------------------------

    @staticmethod
    def _calc_pet_size() -> int:
        try:
            geo = QApplication.primaryScreen().availableGeometry()
            short_side = min(geo.width(), geo.height())
            size = int(short_side * PET_SIZE_RATIO)
        except Exception:
            size = 160
        return max(PET_SIZE_MIN, min(PET_SIZE_MAX, size))

    def _place_default(self):
        try:
            geo = QApplication.primaryScreen().availableGeometry()
            self.move(
                geo.right() - self.width() - 40,
                geo.bottom() - self.height() - 70,
            )
        except Exception:
            self.move(200, 200)

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._bubble and self._bubble.isVisible():
            self._bubble.update_position()

    def _on_anim(self):
        self._phase += 0.10
        if self._phase > math.pi * 2:
            self._phase -= math.pi * 2
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        offset_scale = 8 if self._is_walking else 4
        offset = int(math.sin(self._phase) * offset_scale)

        current_pixmap = self.pixmap
        if self._is_walking and self.walk_pixmaps:
            current_pixmap = self.walk_pixmaps[self._walk_frame_index]

        if not current_pixmap.isNull():
            if self._walk_direction > 0 and self._is_walking:
                scaled_pixmap = current_pixmap.scaled(
                    self.width(), self.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                ).transformed(QTransform().scale(-1, 1))
            else:
                scaled_pixmap = current_pixmap.scaled(
                    self.width(), self.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
            x = (self.width() - scaled_pixmap.width()) // 2
            y = (self.height() - scaled_pixmap.height()) // 2 + offset
            painter.drawPixmap(x, y, scaled_pixmap)
        else:
            painter.drawText(self.rect(), Qt.AlignCenter, "图片缺失")

        painter.end()

    # ---------- 气泡 / 提醒 ----------
    def _check_reminders(self):
        if not self._interaction_enabled:
            return
        config_path = ui_path("pet_reminders.json")
        if not os.path.exists(config_path):
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            reminders = data.get("reminders", [])
        except Exception:
            return

        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M")

        if self._last_day != now.day:
            self._last_day = now.day
            self._last_triggered.clear()

        for item in reminders:
            text = item.get("text")
            duration = item.get("duration", 5)
            start_time = item.get("start")
            end_time = item.get("end")
            exact_time = item.get("time")

            trigger_key = f"{text}_{start_time}_{end_time}_{exact_time}"
            if trigger_key in self._last_triggered:
                continue

            matched = False
            if start_time and end_time:
                if start_time <= end_time:
                    if start_time <= current_time <= end_time:
                        matched = True
                else:
                    if current_time >= start_time or current_time <= end_time:
                        matched = True
            elif exact_time:
                if exact_time == current_time:
                    matched = True

            if matched:
                self._last_triggered.add(trigger_key)
                self.show_bubble(text, duration)
                break

    def show_bubble(self, text, duration=5):
        if self._bubble:
            self._bubble.close()
        self._bubble = SpeechBubble(text, self, duration)
        self._bubble.show_bubble()

    # ---------- 鼠标 / 菜单 ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.globalPos()
            self._drag_offset = self.pos()
            self._dragging = False

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._press_pos is None:
            return
        delta = event.globalPos() - self._press_pos
        if not self._dragging and delta.manhattanLength() > 6:
            self._dragging = True
        if self._dragging and self._drag_offset is not None:
            self.move(self._drag_offset + delta)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        was_drag = self._dragging
        self._press_pos = None
        self._drag_offset = None
        self._dragging = False
        if not was_drag and self.rect().contains(event.pos()):
            self._on_click()

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        act_draw = QAction("🎲  随机抽取一次", self)
        act_draw.setEnabled(self._interaction_enabled)
        act_draw.triggered.connect(self._do_draw)
        menu.addAction(act_draw)

        menu.addSeparator()

        act_toggle = QAction(
            "🔒  禁用交互" if self._interaction_enabled else "🔓  启用交互", self
        )
        act_toggle.triggered.connect(self._toggle_interaction)
        menu.addAction(act_toggle)

        act_auto = QAction("🚀  开机自启", self)
        act_auto.setCheckable(True)
        act_auto.setChecked(is_autostart_enabled())
        act_auto.triggered.connect(self._toggle_autostart)
        menu.addAction(act_auto)

        act_walk = QAction("🚶  立即检查走动时间", self)
        act_walk.triggered.connect(self._check_walk_schedule)
        menu.addAction(act_walk)

        menu.addSeparator()

        act_show = QAction("🪟  显示点名器", self)
        act_show.triggered.connect(self._show_main)
        menu.addAction(act_show)

        menu.addSeparator()

        act_quit = QAction("❌  退出程序", self)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        menu.exec_(event.globalPos())

    # ---------- 行为 ----------
    def _on_click(self):
        if not self._interaction_enabled:
            return
        self._do_draw()

    def _do_draw(self):
        try:
            names, plugin_name = self.owner.quick_pick(1)
        except Exception as e:
            QMessageBox.critical(None, "抽取失败", f"{type(e).__name__}: {e}")
            return

        if not names:
            if not self.owner.records:
                msg = "名单还是空的，先去「名单管理」里添加吧～"
            else:
                msg = "当前所有候选人的权重都是 0，无法抽取。"
            dialog = PetResultDialog([], None, msg)
        else:
            dialog = PetResultDialog(names, plugin_name)

        self._result_dialog = dialog
        dialog.exec_()
        self._result_dialog = None

    def hide_all_ui(self):
        if self._bubble:
            self._bubble.close()
            self._bubble = None
        if self._result_dialog:
            self._result_dialog.reject()
            self._result_dialog = None

    def _show_main(self):
        self.hide_all_ui()
        self.hide()
        self.owner.show()
        self.owner.raise_()
        self.owner.activateWindow()

    def _toggle_interaction(self):
        self._interaction_enabled = not self._interaction_enabled
        self.setWindowOpacity(1.0 if self._interaction_enabled else 0.55)
        self.setToolTip(
            "点我抽人｜右键菜单"
            if self._interaction_enabled
            else "交互已禁用（右键可重新启用）"
        )
        if not self._interaction_enabled:
            if self._bubble:
                self._bubble.close()
            self._stop_walking()

    def _toggle_autostart(self, checked: bool):
        ok = set_autostart(checked)
        if not ok and os.name == "nt":
            QMessageBox.warning(self, "提示", "设置开机自启失败（可能被安全软件拦截）。")

    def _quit(self):
        self.owner.shutdown_app()

    def closeEvent(self, event):
        if self._anim.isActive():
            self._anim.stop()
        if self._reminder_timer.isActive():
            self._reminder_timer.stop()
        if self._walk_timer.isActive():
            self._walk_timer.stop()
        if self._schedule_timer.isActive():
            self._schedule_timer.stop()
        if self._bubble:
            self._bubble.close()
        super().closeEvent(event)