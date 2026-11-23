# -*- coding: utf-8 -*-
"""桌宠配置：行走时间表与定时提醒，统一存放在 pet_config.json。

文件结构（全部字段都可省略，缺失时用默认值补齐）：

```
{
  "walk": {
    "walk_speed": 5,
    "walk_time_ranges": [
      {"start": "07:55", "end": "08:00"},
      ...
    ]
  },
  "reminders": [
    {"start": "08:00", "end": "09:20", "text": "早上好！", "duration": 6},
    {"time": "14:00", "text": "下午上课啦", "duration": 6}
  ]
}
```

约定：

- ``walk.walk_time_ranges``：桌宠只在这些时间段内散步（``start``/``end`` 用 ``HH:MM``，
  支持跨零点，如 ``22:00`` ~ ``01:00``）；空列表表示不在时间表内散步。
- ``walk.walk_speed``：每 50ms 移动的像素数（最小 1）。
- ``reminders``：桌宠气泡提醒。区间式用 ``start`` + ``end``，定点式用 ``time``；
  ``duration`` 为气泡显示秒数（默认 5）。

兼容性：

- 旧版本把行走配置放在 ``pet_walk.json``（部分版本写作 ``pet_walks.json``）、
  提醒放在 ``pet_reminders.json``。当 ``pet_config.json`` 不存在时，本模块会自动读取
  这些旧文件并合并成一份新配置写入 ``pet_config.json``（旧文件原样保留，不会被删除）。
- 也接受“扁平”格式：把 ``walk_time_ranges`` / ``walk_speed`` / ``reminders``
  直接平铺在顶层，读取时一样能识别。
- ``pet_config.json`` 不存在（或内容损坏无法解析）时自动生成默认配置。
"""
import copy
import json
import os

from .config import ui_path

PET_CONFIG_PATH = ui_path("pet_config.json")

# 旧版配置位置（只在新配置缺失时用于迁移）
LEGACY_WALK_PATHS = (ui_path("pet_walk.json"), ui_path("pet_walks.json"))
LEGACY_REMINDERS_PATH = ui_path("pet_reminders.json")

DEFAULT_WALK_SPEED = 5
DEFAULT_WALK_TIME_RANGES = [
    {"start": "07:55", "end": "08:00"},
    {"start": "08:40", "end": "08:50"},
    {"start": "09:30", "end": "09:40"},
    {"start": "10:20", "end": "10:30"},
    {"start": "11:10", "end": "11:20"},
    {"start": "12:20", "end": "12:40"},
    {"start": "14:45", "end": "15:15"},
    {"start": "16:00", "end": "17:00"},
    {"start": "17:35", "end": "18:00"},
    {"start": "19:40", "end": "20:00"},
    {"start": "20:10", "end": "20:20"},
]

DEFAULT_REMINDERS = [
    {
        "start": "08:00",
        "end": "09:20",
        "text": "早上好！试试点名器抽人吧~",
        "duration": 6,
    },
    {
        "time": "14:00",
        "text": "下午上课啦，要不要随机抽个人回答问题？",
        "duration": 6,
    },
    {
        "start": "19:30",
        "end": "21:20",
        "text": "晚自习时间到，点我抽个幸运儿吧！",
        "duration": 8,
    },
]

DEFAULT_PET_CONFIG = {
    "walk": {
        "walk_speed": DEFAULT_WALK_SPEED,
        "walk_time_ranges": DEFAULT_WALK_TIME_RANGES,
    },
    "reminders": DEFAULT_REMINDERS,
}

DEFAULT_REMINDER_DURATION = 5


def default_pet_config() -> dict:
    """返回一份全新的默认配置（深拷贝，随便改不会影响默认值）。"""
    return copy.deepcopy(DEFAULT_PET_CONFIG)


# ---------- 各字段规范化 ----------
def _as_text(value) -> str:
    return str(value).strip() if value is not None else ""


def _normalize_walk_ranges(raw):
    """把时间范围列表整理成 [{"start": ..., "end": ...}]；非列表返回 None。"""
    if not isinstance(raw, list):
        return None
    ranges = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        start = _as_text(item.get("start"))
        end = _as_text(item.get("end"))
        if not start or not end:
            continue
        entry = dict(item)
        entry["start"] = start
        entry["end"] = end
        ranges.append(entry)
    return ranges


def _normalize_reminders(raw):
    """把提醒列表整理成可用的 dict 列表；非列表返回 None。"""
    if not isinstance(raw, list):
        return None
    reminders = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = _as_text(item.get("text"))
        if not text:
            continue
        entry = dict(item)
        entry["text"] = text

        has_range = bool(_as_text(entry.get("start")) and _as_text(entry.get("end")))
        if has_range:
            entry["start"] = _as_text(entry.get("start"))
            entry["end"] = _as_text(entry.get("end"))
            entry.pop("time", None)
        elif _as_text(entry.get("time")):
            entry["time"] = _as_text(entry.get("time"))
        else:
            # 既没有区间也没有定点时间，这条提醒永远不会触发
            continue

        try:
            entry["duration"] = max(1, int(float(entry.get("duration", DEFAULT_REMINDER_DURATION))))
        except (TypeError, ValueError):
            entry["duration"] = DEFAULT_REMINDER_DURATION
        reminders.append(entry)
    return reminders


def _normalize_walk(raw) -> dict:
    """整理 walk 段；缺失/非法字段用默认值补齐。"""
    walk = {
        "walk_speed": DEFAULT_WALK_SPEED,
        "walk_time_ranges": copy.deepcopy(DEFAULT_WALK_TIME_RANGES),
    }
    if not isinstance(raw, dict):
        return walk

    try:
        walk["walk_speed"] = max(1, int(float(raw.get("walk_speed"))))
    except (TypeError, ValueError):
        pass

    ranges = _normalize_walk_ranges(raw.get("walk_time_ranges"))
    if ranges is not None:
        # 显式写了空列表就是“不想散步”，尊重用户选择
        walk["walk_time_ranges"] = ranges
    return walk


def _normalize_config(data: dict) -> dict:
    """把任意历史格式的配置整理成标准结构。"""
    walk_raw = data.get("walk")
    if not isinstance(walk_raw, dict):
        # 扁平格式：walk_time_ranges / walk_speed 直接放在顶层
        walk_raw = {
            "walk_speed": data.get("walk_speed"),
            "walk_time_ranges": data.get("walk_time_ranges"),
        }
    reminders_raw = data.get("reminders")
    reminders = _normalize_reminders(reminders_raw)
    return {
        "walk": _normalize_walk(walk_raw),
        "reminders": (
            copy.deepcopy(DEFAULT_REMINDERS) if reminders is None else reminders
        ),
    }


def _is_legacy_layout(data: dict) -> bool:
    """是否是旧版 / 扁平结构（需要写回成统一格式）。"""
    if not isinstance(data.get("walk"), dict):
        return True
    return False


# ---------- 文件读写 ----------
def _read_json_file(path: str):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _backup_broken_config() -> None:
    """配置损坏时先备份，避免直接覆盖掉用户原来的内容。"""
    backup = PET_CONFIG_PATH + ".bak"
    try:
        if not os.path.exists(backup):
            os.replace(PET_CONFIG_PATH, backup)
    except Exception:
        pass


def _config_from_legacy_files() -> dict:
    """从旧的 pet_walk(.s).json / pet_reminders.json 拼出配置；都没有就用默认值。"""
    cfg = default_pet_config()

    for path in LEGACY_WALK_PATHS:
        legacy_walk = _read_json_file(path)
        if isinstance(legacy_walk, dict):
            cfg["walk"] = _normalize_walk(
                {
                    "walk_speed": legacy_walk.get("walk_speed"),
                    "walk_time_ranges": legacy_walk.get("walk_time_ranges"),
                }
            )
            break

    legacy_reminders = _read_json_file(LEGACY_REMINDERS_PATH)
    if isinstance(legacy_reminders, dict):
        legacy_reminders = legacy_reminders.get("reminders")
    reminders = _normalize_reminders(legacy_reminders)
    if reminders is not None:
        cfg["reminders"] = reminders

    return cfg


def save_pet_config(cfg: dict) -> bool:
    """把配置写入 pet_config.json，成功返回 True。"""
    try:
        folder = os.path.dirname(PET_CONFIG_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(PET_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_pet_config() -> dict:
    """读取桌宠配置；文件缺失/损坏会自动生成（缺新配置时先迁移旧文件）。"""
    if os.path.exists(PET_CONFIG_PATH):
        data = _read_json_file(PET_CONFIG_PATH)
        if isinstance(data, dict):
            cfg = _normalize_config(data)
            if _is_legacy_layout(data):
                # 旧版 / 扁平结构：顺手写回统一格式
                save_pet_config(cfg)
            return cfg
        # 内容损坏：备份后重新生成
        _backup_broken_config()

    cfg = _config_from_legacy_files()
    save_pet_config(cfg)
    return cfg


def ensure_pet_config() -> bool:
    """确保 pet_config.json 存在；缺失时自动生成（能迁移就迁移）。"""
    if os.path.exists(PET_CONFIG_PATH):
        return True
    return save_pet_config(_config_from_legacy_files())
