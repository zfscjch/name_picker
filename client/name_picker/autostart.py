# -*- coding: utf-8 -*-
"""Windows 开机自启。"""
import os
import sys

from .config import AUTOSTART_KEY, get_entry_script


def _app_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable
    return f'"{pyw}" "{get_entry_script()}"'


def set_autostart(enable: bool) -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
    except ImportError:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_ALL_ACCESS,
        )
    except OSError as e:
        print(f"打开自启注册表失败：{e}")
        return False
    try:
        if enable:
            winreg.SetValueEx(key, AUTOSTART_KEY, 0, winreg.REG_SZ, _app_command())
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_KEY)
            except FileNotFoundError:
                pass
        return True
    except OSError as e:
        print(f"设置开机自启失败：{e}")
        return False
    finally:
        try:
            winreg.CloseKey(key)
        except OSError:
            pass


def is_autostart_enabled() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ,
        )
        try:
            winreg.QueryValueEx(key, AUTOSTART_KEY)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False