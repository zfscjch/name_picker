# -*- coding: utf-8 -*-
"""自动更新：检查、下载、替换。"""
import os
import sys
import json
import tempfile
import urllib.request
import zipfile
import subprocess

from PyQt5.QtCore import QThread, pyqtSignal

from .config import CURRENT_VERSION, UPDATE_API_URL
from .utils import parse_version


class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str, str)  # version, url, changelog
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            req = urllib.request.Request(
                UPDATE_API_URL, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            latest_ver = data.get("version")
            download_url = data.get("url") or ""
            changelog = data.get("changelog") or "无更新说明"
            if latest_ver and parse_version(latest_ver) > parse_version(CURRENT_VERSION):
                self.update_available.emit(latest_ver, download_url, changelog)
        except Exception as e:
            print(f"检查更新失败: {e}")
            self.error_occurred.emit(str(e))


class UpdateDownloader(QThread):
    progress = pyqtSignal(int)
    finished_ok = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            tmp_root = tempfile.mkdtemp(prefix="name_picker_update_")
            zip_path = os.path.join(tmp_root, "update.zip")

            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0) or 0)
                downloaded = 0
                with open(zip_path, "wb") as f:
                    while True:
                        if self._cancelled:
                            self.error_occurred.emit("已取消")
                            return
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self.progress.emit(min(99, int(downloaded * 100 / total)))
            self.progress.emit(99)

            extract_dir = os.path.join(tmp_root, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)

            new_dir = None
            target_exe = (
                os.path.basename(sys.executable).lower()
                if getattr(sys, "frozen", False)
                else "name_picker.exe"
            )
            for dirpath, _, filenames in os.walk(extract_dir):
                for fn in filenames:
                    if fn.lower() == target_exe or fn.lower() == "name_picker.exe":
                        new_dir = dirpath
                        break
                if new_dir:
                    break

            if not new_dir:
                self.error_occurred.emit("压缩包中未找到 name_picker.exe")
                return
            self.progress.emit(100)
            self.finished_ok.emit(new_dir)
        except Exception as e:
            self.error_occurred.emit(f"{type(e).__name__}: {e}")


def launch_updater(new_dir: str) -> bool:
    if not getattr(sys, "frozen", False):
        return False

    cur_exe = sys.executable
    cur_dir = os.path.dirname(cur_exe)
    exe_name = os.path.basename(cur_exe)
    bat_path = os.path.join(tempfile.gettempdir(), "name_picker_updater.bat")
    bat_encoding = "mbcs" if os.name == "nt" else "utf-8"

    script = (
        "@echo off\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        ":wait_loop\r\n"
        f'tasklist /FI "IMAGENAME eq {exe_name}" 2>nul | find /I "{exe_name}" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "    timeout /t 1 /nobreak >nul\r\n"
        "    goto wait_loop\r\n"
        ")\r\n"
        f'xcopy /E /Y /I "{new_dir}\\*" "{cur_dir}\\" >nul\r\n'
        f'start "" "{cur_exe}"\r\n'
        f'rmdir /S /Q "{new_dir}" >nul 2>&1\r\n'
        'del "%~f0"\r\n'
    )

    try:
        with open(bat_path, "w", encoding=bat_encoding, newline="") as f:
            f.write(script)
    except Exception:
        return False

    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", "/b", bat_path],
            creationflags=creationflags,
            close_fds=True,
        )
        return True
    except Exception:
        return False