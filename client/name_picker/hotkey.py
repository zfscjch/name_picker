# -*- coding: utf-8 -*-
"""全局快捷键监听（基于 pynput，跨平台）。

pynput 的回调运行在监听线程中，不能直接操作 Qt GUI。
因此通过 pyqtSignal 将事件转发到主线程，由主线程执行真正的 GUI 操作。
"""
from PyQt5.QtCore import QThread, pyqtSignal

try:
    from pynput import keyboard
    _PYNPUT_OK = True
    _PYNPUT_ERROR = ""
except Exception as _e:          # 未安装 / 平台不支持（如无 X11 的 headless）
    keyboard = None
    _PYNPUT_OK = False
    _PYNPUT_ERROR = str(_e)


# pynput 的 GlobalHotKeys 使用尖括号语法：
#   <ctrl> <shift> <alt> <cmd>  +  普通字符
DEFAULT_HOTKEY = "<ctrl>+<shift>+o"


class HotkeyListener(QThread):
    """在后台线程中监听全局快捷键，触发时发射 triggered 信号。

    设计要点：
      - run() 中启动 pynput.GlobalHotKeys，然后阻塞轮询 _running，
        以便 stop() 能及时让线程退出；
      - _on_activated 运行在监听线程，只做 emit，不做任何 GUI 操作；
      - 所有异常通过 error_occurred 上报，不抛出到 Qt 事件循环。
    """

    triggered = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, hotkey: str = DEFAULT_HOTKEY, parent=None):
        super().__init__(parent)
        self._hotkey = (hotkey or DEFAULT_HOTKEY).strip() or DEFAULT_HOTKEY
        self._listener = None
        self._running = False

    def run(self):
        if not _PYNPUT_OK:
            self.error_occurred.emit(f"pynput 不可用：{_PYNPUT_ERROR}")
            return

        self._running = True
        try:
            hotkey_map = {self._hotkey: self._on_activated}
            self._listener = keyboard.GlobalHotKeys(hotkey_map)
            self._listener.start()
            # 阻塞等待 stop()
            while self._running:
                self.msleep(100)
        except Exception as e:
            self.error_occurred.emit(f"{type(e).__name__}: {e}")
        finally:
            self._stop_listener()

    def _on_activated(self):
        # 监听线程内：只发射信号
        self.triggered.emit()

    def _stop_listener(self):
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def stop(self):
        self._running = False
        self._stop_listener()
        self.wait(2000)

    @property
    def hotkey(self) -> str:
        return self._hotkey
