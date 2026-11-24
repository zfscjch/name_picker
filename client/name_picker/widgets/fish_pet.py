# -*- coding: utf-8 -*-
"""大肥鱼桌宠：点击抽名、自由散步、摸头喂食、气泡提醒、右键菜单。"""
import os
import math
import time
import base64
import random
import datetime
import xml.etree.ElementTree as ET
from datetime import datetime as dt  # 用于 dt.now()

from PyQt5.QtCore import Qt, QTimer, QPoint, QPointF, QRect, QElapsedTimer
from PyQt5.QtGui import QColor, QCursor, QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import (
    QWidget, QMenu, QAction, QActionGroup, QMessageBox, QApplication,
)

from ..config import (
    PET_SIZE_RATIO, PET_SIZE_MIN, PET_SIZE_MAX, ui_path,
)
from ..pet_config import load_pet_config
from ..autostart import set_autostart, is_autostart_enabled
from .speech_bubble import SpeechBubble
from .pet_result import PetResultDialog
from .pet_actions import (
    ActionPlayer, CELL_H, CELL_W, load_action_frames,
)

# 行走动画的兜底节奏（pet_walk.svg 缺失时使用，与旧版 3×50ms 一帧一致）
WALK_FRAME_MS = 150
WALK_BOB_PX = 4.0
WALK_BOB_COUNT = 2.0

# 行走方式
WALK_MODE_ROAM = "roam"      # 自由散步：在桌面范围内随机换目标点
WALK_MODE_FOLLOW = "follow"  # 跟着鼠标走
WALK_MODE_STILL = "still"    # 原地待机

# 垂直方向走得比水平慢一点，看起来更像"挪"而不是"飘"
VERTICAL_SPEED_RATIO = 0.78

CHATTER_LINES = [
    "今天也要加油鸭～",
    "有人想被点到吗？",
    "休息一下，看看窗外吧",
    "我在这儿陪你～",
    "要不要抽个人玩玩？",
    "咕噜咕噜…",
    "窗外的云好像小鱼干",
    "坐久了记得起来走两步哦",
]
HOVER_LINES = ["在呢～", "要抽人吗？", "找我玩吗？", "嗯？怎么啦"]
PET_LINES = ["嘿嘿，好舒服～", "再摸一下嘛", "咕噜咕噜…", "最喜欢你啦～"]
FEED_LINES = ["小鱼干！最喜欢了～", "吃饱啦，有力气走路了！", "嗷呜——谢谢投喂！"]
TEASE_LINES = ["哇！跳这么高！", "看我表演一个鲤鱼跳龙门！"]
DROP_LINES = ["放我下来啦～", "晕乎乎的…", "下次轻一点嘛"]
WAKE_LINES = ["唔…我醒啦", "呼啊——睡得好香", "诶？要抽人了吗？"]
STUDY_LINES = ["一起学习吧～", "翻开小本本，认真模式启动！"]
DRUM_LINES = ["咚咚咚！给你来一段～", "听我敲一段小鼓！"]

# 闲置多久后开始打瞌睡（秒）：安静模式更快犯困，活泼模式慢一点
SLEEP_AFTER_SECONDS = 150
CALM_SLEEP_AFTER_SECONDS = 90

# 安静模式：走得更慢、待机动作更慢、随机说话与打招呼更少
CALM_SPEED_FACTOR = 0.65
CALM_IDLE_FRAME_SECONDS = 2.4
ACTIVE_IDLE_FRAME_SECONDS = 0.6

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def load_walk_animation():
    """读取 pet_walk.svg 的行走序列图与节奏；失败时退回 pet_walk_*.png。

    返回 dict：
      strip:      QPixmap | None  横向序列图（SVG 内嵌，60fps 已烘焙补间）
      frames:     list[QPixmap]   序列图缺失时的单帧列表（PNG 回退）
      count:      int             序列帧数
      frame_size: (w, h)          单帧尺寸
      frame_ms:   float           每帧毫秒
      bob_px / bob_count: float   步态起伏参数
    """
    svg_path = ui_path("pet_walk.svg")

    if os.path.exists(svg_path):
        try:
            root = ET.parse(svg_path).getroot()
            for node in root.iter(f"{{{_SVG_NS}}}image"):
                href = node.get(_XLINK_HREF) or node.get("href") or ""
                head, _, payload = href.partition(",")
                if not head.startswith("data:image/png;base64") or not payload:
                    continue
                strip = QPixmap()
                if not strip.loadFromData(base64.b64decode(payload), "PNG"):
                    continue

                count = int(float(root.get("data-frames", 1)))
                frame_w = int(float(root.get("data-frame-width", 0))) or (
                    strip.width() // max(1, count)
                )
                frame_h = int(float(root.get("data-frame-height", 0))) or strip.height()
                if count <= 0 or frame_w <= 0 or frame_h <= 0:
                    continue
                if strip.width() < count * frame_w or strip.height() < frame_h:
                    continue

                return {
                    "strip": strip,
                    "frames": [],
                    "count": count,
                    "frame_size": (frame_w, frame_h),
                    "frame_ms": max(5.0, float(root.get("data-frame-ms", 1000.0 / 60))),
                    "bob_px": max(0.0, float(root.get("data-bob-px", WALK_BOB_PX))),
                    "bob_count": max(0.0, float(root.get("data-bob-count", WALK_BOB_COUNT))),
                }
        except Exception:
            pass

    frames = []
    for i in range(1, 9):
        path = ui_path(f"pet_walk_{i}.png")
        if os.path.exists(path):
            frames.append(QPixmap(path))

    return {
        "strip": None,
        "frames": frames,
        "count": len(frames),
        "frame_size": (frames[0].width(), frames[0].height()) if frames else (0, 0),
        "frame_ms": float(WALK_FRAME_MS),
        "bob_px": WALK_BOB_PX,
        "bob_count": WALK_BOB_COUNT,
    }


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
        self.setToolTip("左键抽人｜中键摸摸头｜右键菜单")

        # 1. 默认静止图片
        self.pixmap = QPixmap(ui_path("pet.png"))

        # 2. 行走动画：优先读 pet_walk.svg（60fps 序列图 + 节奏），失败退回 8 张 PNG
        walk = load_walk_animation()
        self._walk_strip = walk["strip"]
        self._walk_frames = walk["frames"]
        self._walk_frame_count = walk["count"]
        self._walk_frame_size = walk["frame_size"]
        self._walk_frame_ms = float(walk["frame_ms"])
        self._bob_px = float(walk["bob_px"])
        self._bob_count = float(walk["bob_count"])
        if self._walk_frame_size[0] <= 0 or self._walk_frame_size[1] <= 0:
            # 行走素材缺失时也要保证动作帧有地方画
            self._walk_frame_size = (CELL_W, CELL_H)

        # 2.5 动作帧（All.webp 拆包）：待机 / 招手 / 睡觉 / 学习 / 敲鼓 / 举鱼
        self._action_frames = load_action_frames()
        self._actions = ActionPlayer(self)
        self._actions.frame_changed.connect(self.update)
        self._actions.finished.connect(self._on_action_finished)
        self._sleeping = False
        self._last_interaction = time.monotonic()

        # 3. 行走状态：位置用浮点累积，避免 16ms 定时器下四舍五入抖动
        self._walk_frame_pos = 0.0
        self._walk_x = float(self.x())
        self._walk_y = float(self.y())
        self._walk_last_ms = 0
        self._walk_clock = QElapsedTimer()
        self._walk_mode = WALK_MODE_ROAM
        self._is_walking = False   # 行走会话（受时间表控制）
        self._is_moving = False    # 当前是否在迈步（False = 原地休息）
        self._facing = -1          # 面朝方向：-1 左，1 右
        self._walk_speed = 2       # 每 50ms 的像素（来自 pet_config.json 的 walk.walk_speed）
        self._walk_boost_until = 0.0
        self._walk_override_until = 0.0
        self._target: QPointF = None
        self._pause_until = 0.0
        self._follow_resting = False

        # 4. 互动 / 特效状态
        self._interaction_enabled = True
        self._calm = True          # 默认安静一点，避免平时太活跃
        self._chatter_enabled = True
        self._dragging = False
        self._press_pos: QPoint = None
        self._drag_offset: QPoint = None
        self._phase = 0.0
        self._hearts = []
        self._jump_started = None
        self._jump_peak = 0.0
        self._jump_duration = 0.55
        self._hover_started = None
        self._hover_cooldown_until = 0.0
        self._drop_cooldown_until = 0.0

        self._bubble = None
        self._result_dialog = None
        self._last_triggered = set()
        self._last_day = -1

        # 5. 定时器
        self._anim = QTimer(self)
        self._anim.setInterval(60)
        self._anim.timeout.connect(self._on_anim)
        self._anim.start()

        self._walk_timer = QTimer(self)
        self._walk_timer.setTimerType(Qt.PreciseTimer)
        self._walk_timer.setInterval(16)  # ≈60fps，帧间补间才顺
        self._walk_timer.timeout.connect(self._on_walk_tick)

        self._fx_timer = QTimer(self)
        self._fx_timer.setTimerType(Qt.PreciseTimer)
        self._fx_timer.setInterval(16)
        self._fx_timer.timeout.connect(self._on_fx_tick)

        self._chatter_timer = QTimer(self)
        self._chatter_timer.setInterval(60000)
        self._chatter_timer.timeout.connect(self._maybe_chatter)
        self._chatter_timer.start()

        # 闲置太久会打瞌睡；任何互动都会把它叫醒
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setInterval(30000)
        self._sleep_timer.timeout.connect(self._maybe_sleep)
        self._sleep_timer.start()

        self._schedule_timer = QTimer(self)
        self._schedule_timer.setInterval(60000)
        self._schedule_timer.timeout.connect(self._check_walk_schedule)
        self._schedule_timer.start()

        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(15000)
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._reminder_timer.start()

        self._place_default()
        QTimer.singleShot(2000, self._check_reminders)
        QTimer.singleShot(3000, self._check_walk_schedule)

    # ---------- 行走：时间表与模式 ----------
    def _load_walk_config(self):
        """读取 pet_config.json 的 walk 段，返回时间范围列表。

        配置缺失时会由 pet_config 自动生成默认文件，因此正常情况下一定有值。
        """
        try:
            walk = load_pet_config().get("walk") or {}
        except Exception:
            return None
        try:
            self._walk_speed = max(1, int(walk.get("walk_speed", 2)))
        except (TypeError, ValueError):
            self._walk_speed = 2
        ranges = walk.get("walk_time_ranges")
        return ranges if isinstance(ranges, list) else None

    def _walk_allowed(self, time_ranges) -> bool:
        if not self._interaction_enabled or not self.isVisible():
            return False
        if self._walk_mode == WALK_MODE_STILL:
            return False
        # 用户主动开了学习模式，就让它安静学会儿，别按时间表拉去散步
        if self._actions.name == "study":
            return False
        # 跟着鼠标是用户明确打开的模式，不受走动时间表限制
        if self._walk_mode == WALK_MODE_FOLLOW:
            return True
        if time.monotonic() < self._walk_override_until:
            return True
        if time_ranges is None:
            return False

        now_time = dt.now().time()
        for tr in time_ranges:
            try:
                start = dt.strptime(tr["start"], "%H:%M").time()
                end = dt.strptime(tr["end"], "%H:%M").time()
                if start <= end:
                    if start <= now_time <= end:
                        return True
                elif now_time >= start or now_time <= end:  # 跨零点的时间段
                    return True
            except Exception:
                continue
        return False

    def _check_walk_schedule(self):
        time_ranges = self._load_walk_config()
        if self._walk_allowed(time_ranges):
            if not self._is_walking:
                self._start_walking()
        elif self._is_walking:
            self._stop_walking()

    def _start_walking(self):
        self._wake_up(say=False)
        self._actions.stop()
        self._is_walking = True
        self._is_moving = self._walk_mode == WALK_MODE_FOLLOW
        self._facing = -1
        self._walk_frame_pos = 0.0
        self._walk_x = float(self.x())
        self._walk_y = float(self.y())
        self._target = None
        self._follow_resting = False
        if self._calm:
            self._pause_until = time.monotonic() + random.uniform(0.8, 1.8)
        else:
            self._pause_until = time.monotonic() + random.uniform(0.2, 0.6)
        self._walk_clock.start()
        self._walk_last_ms = 0
        self._walk_timer.start()
        self.update()

    def _stop_walking(self):
        self._is_walking = False
        self._is_moving = False
        self._walk_timer.stop()
        self._walk_frame_pos = 0.0
        self.update()

    def _current_speed(self) -> float:
        speed = float(self._walk_speed)
        if self._calm:
            speed *= CALM_SPEED_FACTOR
        if time.monotonic() < self._walk_boost_until:
            speed *= 1.6
        return speed

    def _sync_position(self, screen):
        max_x = max(screen.left(), screen.right() - self.width())
        max_y = max(screen.top(), screen.bottom() - self.height())
        x = min(max(self._walk_x, float(screen.left())), float(max_x))
        y = min(max(self._walk_y, float(screen.top())), float(max_y))
        self._walk_x = float(x)
        self._walk_y = float(y)
        self.move(int(round(x)), int(round(y)))

    def _pick_roam_target(self) -> QPointF:
        screen = QApplication.primaryScreen().availableGeometry()
        max_x = max(screen.left(), screen.right() - self.width())
        max_y = max(screen.top(), screen.bottom() - self.height())
        fallback = QPointF(self._walk_x, self._walk_y)
        for _ in range(10):
            x = random.uniform(float(screen.left()), float(max_x))
            y = random.uniform(float(screen.top()), float(max_y))
            fallback = QPointF(x, y)
            if math.hypot(x - self._walk_x, y - self._walk_y) >= self.width() * 0.9:
                break
        return fallback

    def _advance_frame(self, dt):
        if self._walk_frame_count > 0 and self._walk_frame_ms > 0:
            # 安静模式下步伐放慢，避免“慢速平移 + 正常步频”的滑步感
            rate = CALM_SPEED_FACTOR if self._calm else 1.0
            self._walk_frame_pos = (
                self._walk_frame_pos + dt / self._walk_frame_ms * rate
            ) % self._walk_frame_count

    def _step_towards_target(self, dt) -> bool:
        """朝 _target 走一步；走到则返回 True。"""
        target = self._target
        if target is None:
            return True
        screen = QApplication.primaryScreen().availableGeometry()
        step = self._current_speed() * dt / 50.0
        dx = target.x() - self._walk_x
        dy = target.y() - self._walk_y
        dist = math.hypot(dx, dy)
        if dist <= max(1.5, step):
            self._walk_x = target.x()
            self._walk_y = target.y()
            self._sync_position(screen)
            return True

        ux, uy = dx / dist, dy / dist
        if abs(ux) > 0.15:
            self._facing = 1 if ux > 0 else -1
        self._walk_x += ux * step
        self._walk_y += uy * step * VERTICAL_SPEED_RATIO
        self._sync_position(screen)
        return False

    def _tick_roam(self, dt, now):
        if self._is_moving:
            arrived = self._step_towards_target(dt)
            self._advance_frame(dt)
            if arrived:
                self._is_moving = False
                self._walk_frame_pos = 0.0
                if self._calm:
                    self._pause_until = now + random.uniform(1.8, 4.5)
                else:
                    self._pause_until = now + random.uniform(0.8, 2.4)
        elif now >= self._pause_until:
            # 安静模式下有时干脆多站一会儿，不急着赶路
            if self._calm and random.random() < 0.3:
                self._pause_until = now + random.uniform(3.0, 6.0)
                return
            self._target = self._pick_roam_target()
            self._is_moving = True
            self._walk_frame_pos = 0.0

    def _follow_target(self) -> QPointF:
        """鼠标位置换算成"宠物左上角目标"，并夹在屏幕内。"""
        cursor = QCursor.pos()
        screen = QApplication.primaryScreen().availableGeometry()
        max_x = max(screen.left(), screen.right() - self.width())
        max_y = max(screen.top(), screen.bottom() - self.height())
        x = min(max(cursor.x() - self.width() / 2.0, float(screen.left())), float(max_x))
        y = min(max(cursor.y() - self.height() / 2.0, float(screen.top())), float(max_y))
        return QPointF(x, y)

    def _tick_follow(self, dt, now):
        cursor = QCursor.pos()
        target = self._follow_target()
        center_x = self._walk_x + self.width() / 2.0
        center_y = self._walk_y + self.height() / 2.0
        cursor_dist = math.hypot(cursor.x() - center_x, cursor.y() - center_y)
        target_dist = math.hypot(target.x() - self._walk_x, target.y() - self._walk_y)

        if self._follow_resting:
            # 有回差，避免在鼠标旁边反复起步/停步
            if cursor_dist > 190.0 and now >= self._pause_until:
                self._follow_resting = False
                self._is_moving = True
                self._walk_frame_pos = 0.0
            else:
                self._is_moving = False
                return

        self._target = target
        arrived = self._step_towards_target(dt)
        if arrived or cursor_dist <= 120.0 or target_dist <= 1.0:
            self._follow_resting = True
            self._is_moving = False
            self._walk_frame_pos = 0.0
            self._pause_until = now + 0.4
            return

        self._advance_frame(dt)

    def _on_walk_tick(self):
        now_ms = self._walk_clock.elapsed()
        dt = now_ms - self._walk_last_ms
        self._walk_last_ms = now_ms

        if self._dragging:
            # 拖拽时同步起点，松手后从当前位置继续走
            self._is_moving = False
            self._walk_x = float(self.x())
            self._walk_y = float(self.y())
            return
        if self._result_dialog is not None:
            # 抽名结果对话框打开时先站住，别在屏幕上来回走
            self._is_moving = False
            return
        if self._action_blocking():
            # 睡觉 / 学习 / 敲鼓 / 举鱼时先不走路
            self._is_moving = False
            return

        # 用真实时间推进，定时器抖动不会让脚步忽快忽慢
        dt = max(0.0, min(float(dt), 100.0))
        now = time.monotonic()
        if self._walk_mode == WALK_MODE_FOLLOW:
            self._tick_follow(dt, now)
        else:
            self._tick_roam(dt, now)
        self.update()

    # ---------- 互动 ----------
    def _say(self, text, duration=4.0):
        if not self._interaction_enabled or not self.isVisible():
            return
        if self._result_dialog is not None:
            return
        self.show_bubble(text, duration)

    def _maybe_chatter(self):
        if self._sleeping or not self._chatter_enabled or not self._interaction_enabled:
            return
        if not self.isVisible() or self._dragging or self._result_dialog is not None:
            return
        if self._bubble is not None and self._bubble.isVisible():
            return
        if self._calm:
            # 安静模式：不在走路时说话，而且要闲置一阵才偶尔冒一句
            if self._is_walking or self._is_moving:
                return
            if time.monotonic() - self._last_interaction < 30:
                return
            if random.random() > 0.03:
                return
        elif random.random() > 0.16:
            return
        self._say(random.choice(CHATTER_LINES), 4.0)

    # ---------- 动作：招手 / 睡觉 / 学习 / 敲鼓 / 举鱼 ----------
    def _touch(self):
        """记录最近一次互动时间，用于判断要不要打瞌睡。"""
        self._last_interaction = time.monotonic()

    def _action_blocking(self) -> bool:
        """这些动作播放时先别走路，否则会一边学习一边平移。"""
        return self._actions.name in ("sleep", "study", "drum", "fish")

    def _on_action_finished(self):
        self._pause_until = time.monotonic() + 0.4
        self.update()

    def _maybe_sleep(self):
        if self._sleeping or not self._interaction_enabled or not self.isVisible():
            return
        if self._dragging or self._result_dialog is not None or self._is_walking:
            return
        if self._actions.name:
            return
        threshold = CALM_SLEEP_AFTER_SECONDS if self._calm else SLEEP_AFTER_SECONDS
        if time.monotonic() - self._last_interaction < threshold:
            return
        if self._actions.play("sleep", loop=False, hold_last=True):
            self._sleeping = True
            self._say("呼…" if self._calm else "呼…好困…", 2.0 if self._calm else 2.5)

    def _wake_up(self, say=True):
        if not self._sleeping:
            return
        self._sleeping = False
        self._actions.stop()
        self._touch()
        if say:
            self._say(random.choice(WAKE_LINES), 2.5)

    def _play_drum(self):
        if not self._interaction_enabled:
            return
        self._wake_up(say=False)
        self._touch()
        if self._actions.play("drum", loop=True, duration_ms=3500):
            self._say(random.choice(DRUM_LINES), 2.6)

    def _toggle_study(self):
        if not self._interaction_enabled:
            return
        self._touch()
        if self._actions.name == "study":
            self._actions.stop()
            self._say("学习结束，休息一下～", 2.5)
            self._check_walk_schedule()
            return
        self._wake_up(say=False)
        if self._actions.play("study", loop=True):
            self._say(random.choice(STUDY_LINES), 3.0)

    def _pet_head(self):
        if not self._interaction_enabled:
            return
        self._wake_up(say=False)
        self._touch()
        self._say(random.choice(PET_LINES), 3.0)
        self._spawn_hearts(5)
        self.jump(14)

    def _feed_pet(self):
        if not self._interaction_enabled:
            return
        self._wake_up(say=False)
        self._touch()
        self._say(random.choice(FEED_LINES), 3.5)
        self._spawn_hearts(8)
        self._walk_boost_until = time.monotonic() + 45.0
        self._actions.play("fish", loop=True, duration_ms=3200)
        self.jump(10)

    def _tease_pet(self):
        if not self._interaction_enabled:
            return
        self._wake_up(say=False)
        self._touch()
        self._say(random.choice(TEASE_LINES), 3.0)
        self._spawn_hearts(3)
        self.jump(22)

    def _set_chatter(self, enabled):
        self._chatter_enabled = bool(enabled)

    def _set_calm(self, enabled):
        self._calm = bool(enabled)
        self._touch()
        if self._calm:
            self._say("嗯，我安静一点～", 2.5)
        else:
            self._say("好耶，活泼起来！", 2.5)
        self.update()

    def _begin_leg(self):
        """立刻迈出下一步：漫步先抽一个目标点，跟随则直接追鼠标。"""
        self._walk_frame_pos = 0.0
        self._is_moving = True
        if self._walk_mode != WALK_MODE_FOLLOW:
            self._target = self._pick_roam_target()

    def _set_walk_mode(self, mode):
        self._wake_up(say=False)
        self._touch()
        if mode != WALK_MODE_STILL and self._actions.name == "study":
            self._actions.stop()
        self._walk_mode = mode
        self._follow_resting = False
        self._target = None
        self._pause_until = 0.0
        if mode == WALK_MODE_STILL:
            self._stop_walking()
            self._say("那我就在这儿待着～", 2.5)
            return
        if mode == WALK_MODE_FOLLOW:
            self._say("要跟着你啦～", 2.5)
        self._check_walk_schedule()
        if self._is_walking:
            self._begin_leg()

    def _walk_now(self):
        self._wake_up(say=False)
        self._touch()
        if self._actions.name == "study":
            self._actions.stop()
        if self._walk_mode == WALK_MODE_STILL:
            self._walk_mode = WALK_MODE_ROAM
        self._walk_override_until = time.monotonic() + 60.0
        self._check_walk_schedule()
        if self._is_walking:
            self._begin_leg()
        self._say("走两步～", 2.5)

    def _finish_drag(self):
        self._touch()
        screen = QApplication.primaryScreen().availableGeometry()
        self._walk_x = float(self.x())
        self._walk_y = float(self.y())
        self._sync_position(screen)
        self._target = None
        self._is_moving = False
        self._pause_until = time.monotonic() + 0.6
        now = time.monotonic()
        if now >= self._drop_cooldown_until and random.random() < 0.35:
            self._drop_cooldown_until = now + 30.0
            self._say(random.choice(DROP_LINES), 3.0)

    # ---------- 特效：跳跃 / 爱心 ----------
    def jump(self, peak=16.0, duration=0.55):
        self._jump_started = time.monotonic()
        self._jump_peak = float(peak)
        self._jump_duration = max(0.15, float(duration))
        self._fx_timer.start()
        self.update()

    def _jump_offset(self) -> int:
        if self._jump_started is None:
            return 0
        progress = (time.monotonic() - self._jump_started) / self._jump_duration
        if progress >= 1.0:
            self._jump_started = None
            return 0
        # 抛物线：起跳-最高点-落下
        return -int(round(self._jump_peak * 4.0 * progress * (1.0 - progress)))

    def _spawn_hearts(self, count=5):
        now = time.monotonic()
        width, height = self.width(), self.height()
        for _ in range(count):
            self._hearts.append({
                "x": width * random.uniform(0.34, 0.66),
                "y": height * random.uniform(0.18, 0.36),
                "vx": random.uniform(-16.0, 16.0),
                "vy": random.uniform(-48.0, -30.0),
                "born": now,
                "life": random.uniform(0.9, 1.4),
                "scale": random.uniform(4.5, 7.5),
            })
        self._fx_timer.start()
        self.update()

    def _on_fx_tick(self):
        now = time.monotonic()
        if self._hearts:
            self._hearts = [h for h in self._hearts if now - h["born"] < h["life"]]
        if self._jump_started is not None and now - self._jump_started >= self._jump_duration:
            self._jump_started = None
        self.update()
        if self._jump_started is None and not self._hearts:
            self._fx_timer.stop()

    def _paint_hearts(self, painter):
        if not self._hearts:
            return
        now = time.monotonic()
        painter.save()
        painter.setPen(Qt.NoPen)
        for heart in self._hearts:
            progress = (now - heart["born"]) / heart["life"]
            if progress >= 1.0:
                continue
            x = heart["x"] + heart["vx"] * progress + math.sin(progress * 9.0) * 3.0
            y = heart["y"] + heart["vy"] * progress
            scale = heart["scale"] * (0.7 + 0.5 * progress)
            painter.setOpacity(1.0 - progress)
            painter.setBrush(QColor(255, 108, 142))
            path = QPainterPath()
            path.moveTo(x, y + 0.35 * scale)
            path.cubicTo(
                x - 0.9 * scale, y - 0.35 * scale,
                x - 0.45 * scale, y - 1.05 * scale,
                x, y - 0.45 * scale,
            )
            path.cubicTo(
                x + 0.45 * scale, y - 1.05 * scale,
                x + 0.9 * scale, y - 0.35 * scale,
                x, y + 0.35 * scale,
            )
            painter.drawPath(path)
        painter.restore()

    # ---------- 行走绘制 ----------
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
        self._walk_x = float(self.x())
        self._walk_y = float(self.y())

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._bubble and self._bubble.isVisible():
            self._bubble.update_position()

    def showEvent(self, event):
        super().showEvent(event)
        self._walk_x = float(self.x())
        self._walk_y = float(self.y())
        QTimer.singleShot(0, self._check_walk_schedule)

    def _on_anim(self):
        self._phase += 0.10
        if self._phase > math.pi * 2:
            self._phase -= math.pi * 2
        self._track_cursor()
        self.update()

    def _track_cursor(self):
        """空闲时面朝鼠标；悬停一会儿会打个招呼。"""
        if not self._interaction_enabled or self._dragging or self._result_dialog is not None:
            self._hover_started = None
            return

        cursor = QCursor.pos()
        inside = self.rect().contains(self.mapFromGlobal(cursor))
        now = time.monotonic()

        if inside:
            if self._hover_started is None:
                self._hover_started = now
            elif self._sleeping and now - self._hover_started >= (1.2 if self._calm else 0.6):
                # 睡着了被盯着看一会儿就会醒
                self._hover_started = None
                self._hover_cooldown_until = now + 45.0
                self._wake_up(say=True)
            elif now - self._hover_started >= (1.8 if self._calm else 1.2) and now >= self._hover_cooldown_until:
                self._hover_started = None
                self._hover_cooldown_until = now + (180.0 if self._calm else 45.0)
                if not self._calm and not self._is_walking and not self._actions.name:
                    self._actions.play("wave", loop=False)
                    self._touch()
                    self._say(random.choice(HOVER_LINES), 3.0)
                else:
                    self._say(random.choice(HOVER_LINES), 3.0)
        else:
            self._hover_started = None

        if self._is_walking and self._is_moving:
            return
        center = self.mapToGlobal(self.rect().center())
        if cursor.x() < center.x() - 12:
            facing = -1
        elif cursor.x() > center.x() + 12:
            facing = 1
        else:
            facing = self._facing
        if facing != self._facing:
            self._facing = facing
            self.update()

    def _walk_bob(self):
        """按步态相位做上下起伏：每轮循环两次，左右脚各一次。"""
        if self._bob_px <= 0 or self._walk_frame_count <= 0:
            return 0
        phase = (self._walk_frame_pos % self._walk_frame_count) / self._walk_frame_count
        wave = 0.5 - 0.5 * math.cos(2.0 * math.pi * self._bob_count * phase)
        return int(round(-self._bob_px * wave))

    def _walk_target_rect(self, offset):
        """按 KeepAspectRatio 把单帧铺到窗口里，居中并叠加起伏。"""
        frame_w, frame_h = self._walk_frame_size
        if frame_w <= 0 or frame_h <= 0:
            return QRect(0, 0, 0, 0)
        scale = min(self.width() / frame_w, self.height() / frame_h)
        width = max(1, int(round(frame_w * scale)))
        height = max(1, int(round(frame_h * scale)))
        return QRect(
            (self.width() - width) // 2,
            (self.height() - height) // 2 + offset,
            width,
            height,
        )

    def _paint_walk_frame(self, painter, index, offset):
        if self._walk_frame_count <= 0:
            return
        index %= self._walk_frame_count
        target = self._walk_target_rect(offset)

        painter.save()
        if self._facing > 0:  # 向右走时水平镜像
            painter.translate(self.width(), 0)
            painter.scale(-1, 1)

        if self._walk_strip is not None and not self._walk_strip.isNull():
            frame_w, frame_h = self._walk_frame_size
            source = QRect(index * frame_w, 0, frame_w, frame_h)
            painter.drawPixmap(target, self._walk_strip, source)
        elif self._walk_frames:
            pixmap = self._walk_frames[index % len(self._walk_frames)]
            if not pixmap.isNull():
                painter.drawPixmap(target, pixmap, pixmap.rect())
        painter.restore()

    def _paint_walking(self, painter, offset):
        count = self._walk_frame_count
        if count <= 0:
            return
        self._paint_walk_frame(painter, int(self._walk_frame_pos), offset)

    def _draw_action_frame(self, painter, frame, offset):
        """画 All.webp 拆出来的动作帧（招手/睡觉/学习/敲鼓/举鱼）。"""
        if frame is None or frame.isNull():
            return
        target = self._walk_target_rect(offset)
        painter.save()
        if self._facing > 0:
            painter.translate(self.width(), 0)
            painter.scale(-1, 1)
        painter.drawPixmap(target, frame, frame.rect())
        painter.restore()

    def _paint_idle(self, painter, offset):
        # 有动作帧时用 All.webp 里的站立待机（会眨眼、轻微晃动）
        frames = self._action_frames.get("idle") if self._action_frames else None
        if frames:
            interval = CALM_IDLE_FRAME_SECONDS if self._calm else ACTIVE_IDLE_FRAME_SECONDS
            index = int(time.monotonic() / interval) % len(frames)
            self._draw_action_frame(painter, frames[index], offset)
            return

        # 动作表缺失时退回 pet.png
        if self.pixmap.isNull():
            painter.drawText(self.rect(), Qt.AlignCenter, "图片缺失")
            return
        scaled_pixmap = self.pixmap.scaled(
            self.width(), self.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        x = (self.width() - scaled_pixmap.width()) // 2
        y = (self.height() - scaled_pixmap.height()) // 2 + offset

        painter.save()
        if self._facing > 0:
            painter.translate(self.width(), 0)
            painter.scale(-1, 1)
        painter.drawPixmap(x, y, scaled_pixmap)
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        offset = self._jump_offset()
        action_frame = self._actions.current()
        if self._actions.name and action_frame is not None:
            # 睡觉 / 学习 / 敲鼓 / 举鱼 / 招手：优先显示动作帧
            if self._actions.name == "sleep":
                offset += int(math.sin(self._phase) * (1 if self._calm else 2))  # 睡着后轻轻呼吸
            self._draw_action_frame(painter, action_frame, offset)
        elif self._is_walking and self._walk_frame_count:
            if self._is_moving:
                offset += self._walk_bob()
                self._paint_walking(painter, offset)
            else:
                # 走路中途的小憩：用待机动作，避免和躺着的 pet.png 来回跳变
                offset += int(math.sin(self._phase) * (1 if self._calm else 2))
                self._paint_idle(painter, offset)
        else:
            offset += int(math.sin(self._phase) * (1 if self._calm else 4))
            self._paint_idle(painter, offset)
        self._paint_hearts(painter)

        painter.end()

    # ---------- 气泡 / 提醒 ----------
    def _check_reminders(self):
        if not self._interaction_enabled:
            return
        try:
            reminders = load_pet_config().get("reminders") or []
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
        try:
            seconds = max(1, int(float(duration)))
        except (TypeError, ValueError):
            seconds = 5
        self._bubble = SpeechBubble(text, self, seconds)
        self._bubble.show_bubble()

    # ---------- 鼠标 / 菜单 ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._wake_up(say=False)
            self._touch()
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
        if event.button() == Qt.MiddleButton:
            if self.rect().contains(event.pos()):
                self._pet_head()
            return
        if event.button() != Qt.LeftButton:
            return
        was_drag = self._dragging
        self._press_pos = None
        self._drag_offset = None
        self._dragging = False
        if was_drag:
            self._finish_drag()
            return
        if self.rect().contains(event.pos()):
            self._on_click()

    def contextMenuEvent(self, event):
        self._wake_up(say=False)
        self._touch()
        menu = self._build_context_menu()
        menu.exec_(event.globalPos())
        menu.deleteLater()

    def _build_context_menu(self):
        menu = QMenu()
        enabled = self._interaction_enabled

        act_draw = QAction("🎲  随机抽取一次", menu)
        act_draw.setEnabled(enabled)
        act_draw.triggered.connect(self._do_draw)
        menu.addAction(act_draw)

        menu.addSeparator()

        for text, handler in (
            ("💗  摸摸头", self._pet_head),
            ("🐟  喂小鱼干", self._feed_pet),
            ("🤸  跳一下", self._tease_pet),
            ("🥁  敲一段", self._play_drum),
        ):
            act = QAction(text, menu)
            act.setEnabled(enabled)
            act.triggered.connect(handler)
            menu.addAction(act)

        study_active = self._actions.name == "study"
        act_study = QAction(
            "📚  结束学习" if study_active else "📚  陪我学习", menu
        )
        act_study.setEnabled(enabled)
        act_study.triggered.connect(self._toggle_study)
        menu.addAction(act_study)

        menu.addSeparator()

        roam_menu = menu.addMenu("🧭  散步方式")
        roam_menu.setEnabled(enabled)
        group = QActionGroup(menu)
        group.setExclusive(True)
        for text, mode in (
            ("自由散步（全屏乱逛）", WALK_MODE_ROAM),
            ("跟着鼠标走", WALK_MODE_FOLLOW),
            ("原地待机", WALK_MODE_STILL),
        ):
            act = QAction(text, menu)
            act.setCheckable(True)
            act.setChecked(self._walk_mode == mode)
            act.setEnabled(enabled)
            act.triggered.connect(lambda _checked=False, m=mode: self._set_walk_mode(m))
            group.addAction(act)
            roam_menu.addAction(act)

        act_now = QAction("🚶  现在就走走（60 秒）", menu)
        act_now.setEnabled(enabled)
        act_now.triggered.connect(self._walk_now)
        roam_menu.addAction(act_now)

        act_talk = QAction("💬  随机说话", menu)
        act_talk.setCheckable(True)
        act_talk.setChecked(self._chatter_enabled)
        act_talk.setEnabled(enabled)
        act_talk.toggled.connect(self._set_chatter)
        menu.addAction(act_talk)

        act_calm = QAction("🌙  安静模式", menu)
        act_calm.setCheckable(True)
        act_calm.setChecked(self._calm)
        act_calm.setEnabled(enabled)
        act_calm.toggled.connect(self._set_calm)
        menu.addAction(act_calm)

        menu.addSeparator()

        act_toggle = QAction(
            "🔒  禁用交互" if enabled else "🔓  启用交互", menu
        )
        act_toggle.triggered.connect(self._toggle_interaction)
        menu.addAction(act_toggle)

        act_auto = QAction("🚀  开机自启", menu)
        act_auto.setCheckable(True)
        act_auto.setChecked(is_autostart_enabled())
        act_auto.triggered.connect(self._toggle_autostart)
        menu.addAction(act_auto)

        menu.addSeparator()

        act_show = QAction("🪟  显示点名器", menu)
        act_show.triggered.connect(self._show_main)
        menu.addAction(act_show)

        menu.addSeparator()

        act_quit = QAction("❌  退出程序", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        return menu

    # ---------- 行为 ----------
    def _on_click(self):
        if not self._interaction_enabled:
            return
        self._do_draw()

    def _do_draw(self):
        self._wake_up(say=False)
        self._touch()
        self._actions.stop()
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
        self._pause_until = time.monotonic() + 0.4

    def hide_all_ui(self):
        self._wake_up(say=False)
        self._actions.stop()
        self._stop_walking()
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
            "左键抽人｜中键摸摸头｜右键菜单"
            if self._interaction_enabled
            else "交互已禁用（右键可重新启用）"
        )
        if not self._interaction_enabled:
            if self._bubble:
                self._bubble.close()
            self._hearts = []
            self._jump_started = None
            self._fx_timer.stop()
            self._wake_up(say=False)
            self._actions.stop()
            self._stop_walking()
            self.update()
        else:
            self._touch()
            self._check_walk_schedule()

    def _toggle_autostart(self, checked: bool):
        ok = set_autostart(checked)
        if not ok and os.name == "nt":
            QMessageBox.warning(self, "提示", "设置开机自启失败（可能被安全软件拦截）。")

    def _quit(self):
        self.owner.shutdown_app()

    def closeEvent(self, event):
        for timer in (
            self._anim, self._reminder_timer, self._walk_timer,
            self._schedule_timer, self._fx_timer, self._chatter_timer,
            self._sleep_timer,
        ):
            if timer.isActive():
                timer.stop()
        self._actions.stop()
        if self._bubble:
            self._bubble.close()
        super().closeEvent(event)
