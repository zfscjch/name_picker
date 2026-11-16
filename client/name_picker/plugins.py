# -*- coding: utf-8 -*-
"""插件系统：从 plugins/ 目录动态加载 pick() 函数。"""
import os
import sys
import importlib.util
from typing import List

from .config import BASE_DIR

PLUGIN_DIR = os.path.join(BASE_DIR, "plugins")

EXAMPLE_PLUGIN_CODE = '''# -*- coding: utf-8 -*-
"""示例插件 —— 复制 / 修改本文件即可自定义抽取逻辑。"""
import random

PLUGIN_NAME = "示例插件（默认不生效）"
PRIORITY = 0
DESCRIPTION = "演示插件接口，默认不接管抽取"

def should_use(context):
    return False

def pick(candidates, k, context):
    return None
'''


class PluginEntry:
    def __init__(self, name, priority, path, filename, pick, should_use, description):
        self.name = name
        self.priority = priority
        self.path = path
        self.filename = filename
        self.pick = pick
        self.should_use = should_use
        self.description = description


class PluginManager:
    def __init__(self, plugin_dir: str = PLUGIN_DIR):
        self.dir = plugin_dir
        self.plugins: List[PluginEntry] = []
        self.errors: List[str] = []
        self._snapshot = None
        self._prepare_dir()
        self.reload()

    def _prepare_dir(self):
        try:
            os.makedirs(self.dir, exist_ok=True)
            example = os.path.join(self.dir, "example_plugin.py")
            if not os.path.exists(example):
                with open(example, "w", encoding="utf-8") as f:
                    f.write(EXAMPLE_PLUGIN_CODE)
        except Exception:
            pass
        if self.dir not in sys.path:
            sys.path.insert(0, self.dir)

    def _scan(self) -> dict:
        snap = {}
        try:
            for fn in sorted(os.listdir(self.dir)):
                if not fn.endswith(".py") or fn.startswith("_"):
                    continue
                try:
                    snap[fn] = os.path.getmtime(os.path.join(self.dir, fn))
                except OSError:
                    pass
        except OSError:
            pass
        return snap

    def reload_if_changed(self) -> bool:
        if self._scan() != self._snapshot:
            self.reload()
            return True
        return False

    def reload(self):
        self._snapshot = self._scan()
        self.plugins = []
        self.errors = []
        for fn in self._snapshot:
            entry = self._load_one(fn)
            if entry is not None:
                self.plugins.append(entry)
        self.plugins.sort(key=lambda p: p.priority, reverse=True)

    def _load_one(self, filename: str):
        path = os.path.join(self.dir, filename)
        modname = "_name_picker_plugin_" + os.path.splitext(filename)[0]
        try:
            spec = importlib.util.spec_from_file_location(modname, path)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[modname] = module
            spec.loader.exec_module(module)

            pick = getattr(module, "pick", None)
            if not callable(pick):
                return None
            try:
                priority = float(getattr(module, "PRIORITY", 0) or 0)
            except (TypeError, ValueError):
                priority = 0.0
            should_use = getattr(module, "should_use", None)
            if not callable(should_use):
                should_use = None
            name = str(getattr(module, "PLUGIN_NAME", "") or os.path.splitext(filename)[0])
            desc = str(getattr(module, "DESCRIPTION", "") or "")
            return PluginEntry(name, priority, path, filename, pick, should_use, desc)
        except Exception as e:
            self.errors.append(str(e))
            sys.modules.pop(modname, None)
            return None

    def try_pick(self, candidates, k, context):
        if k <= 0 or not candidates:
            return None, None
        allowed = {c.get("name") for c in candidates}
        for entry in self.plugins:
            if entry.should_use is not None:
                try:
                    if not entry.should_use(dict(context)):
                        continue
                except Exception:
                    continue
            try:
                raw = entry.pick([dict(c) for c in candidates], k, dict(context))
            except Exception:
                continue
            if raw is None:
                continue
            names = self._validate(raw, allowed, k)
            if names is None:
                continue
            return entry.name, names
        return None, None

    @staticmethod
    def _validate(raw, allowed, k):
        if not isinstance(raw, (list, tuple)):
            return None
        names = []
        for item in raw:
            if not isinstance(item, str):
                return None
            n = item.strip()
            if not n:
                return None
            names.append(n)
        if len(names) != k or len(set(names)) != k:
            return None
        for n in names:
            if n not in allowed:
                return None
        return names

    def status_text(self) -> str:
        if not self.plugins:
            return ""
        text = f"插件 {len(self.plugins)} 个"
        if self.errors:
            text += f"（{len(self.errors)} 个加载失败）"
        return text