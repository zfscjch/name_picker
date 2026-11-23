# -*- coding: utf-8 -*-
"""全局配置：常量、路径、版本号、入口脚本探测。"""
import os
import sys

# ============ 可自行修改的配置 ============
ADMIN_PASSWORD = "eoferror"      # 后台管理密码（调整权重需要）
DEFAULT_WEIGHT = 1.0             # 默认权重
DEFAULT_GROUP = "默认组"         # 默认分组名
HEADER_WORDS = {"name", "姓名", "名字", "group", "组", "分组", "班级"}
AUTOSTART_KEY = "NamePickerPet"  # 开机自启注册表键名

PET_SIZE_RATIO = 0.3             # 桌宠边长 = 屏幕短边 × 该比例
PET_SIZE_MIN = 100
PET_SIZE_MAX = 260
# =========================================

if getattr(sys, "frozen", False):
    # onedir 打包：BASE_DIR 与 exe 同级
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 源码：本文件位于 <project_root>/name_picker/config.py
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ui_path(filename: str) -> str:
    """返回 .ui / .png / .json 等资源路径（打包后优先用 _MEIPASS）。"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(BASE_DIR, filename)


CONFIG = {
    "version": "1.1.8",
    "update_api_url": "https://www.cjchcoderchat.site:8080/api/update" if not os.path.exists(os.path.join(BASE_DIR, "plugins", "schedule_booster.py")) \
        else "https://www.cjchcoderchat.site:8080/api/update?pre-release=1",
}
CURRENT_VERSION = CONFIG["version"]
UPDATE_API_URL = CONFIG["update_api_url"]


def ensure_default_configs() -> None:
    """首次运行且没有配置文件时，自动生成默认的 pet_config.json / dismiss_config.json。

    生成失败（例如目录只读）不影响程序启动：各模块读取时都会退回内置默认值。
    """
    try:
        from .pet_config import ensure_pet_config
        ensure_pet_config()
    except Exception:
        pass
    try:
        from .dismiss import ensure_dismiss_config
        ensure_dismiss_config()
    except Exception:
        pass


def get_entry_script() -> str:
    """返回入口脚本的绝对路径，用于开机自启注册表命令行。

    兼容两种启动方式：
      - python name_picker.py            -> 直接返回该文件路径
      - python -m name_picker            -> 返回同目录的 name_picker.py（如果存在）
    """
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if main_file:
        main_file = os.path.abspath(main_file)
        if os.path.basename(main_file) == "__main__.py":
            wrapper = os.path.join(BASE_DIR, "name_picker.py")
            if os.path.exists(wrapper):
                return wrapper
        return main_file
    return os.path.abspath(sys.argv[0])