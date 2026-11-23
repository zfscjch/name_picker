# -*- coding: utf-8 -*-
"""主界面（抽取）。"""
import os
import random
import re
from typing import List

from PyQt5 import uic
from PyQt5.QtCore import Qt, QTimer, QUrl, QT_VERSION_STR, PYQT_VERSION_STR
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QMainWindow, QMessageBox, QProgressDialog, QListWidgetItem, QApplication, QDialog,
)

from .config import (
    DEFAULT_GROUP, DEFAULT_WEIGHT, CURRENT_VERSION, BASE_DIR, ui_path,
    ensure_default_configs,
)
from .utils import weighted_sample
from .plugins import PluginManager
from .updater import UpdateChecker, UpdateDownloader, launch_updater
from .widgets.fish_pet import FishPet
from .widgets.admin_window import AdminWindow
from .dismiss import DismissGuard

MainUIForm, _ = uic.loadUiType(ui_path("main_window.ui"))


class NamePickerUI(QMainWindow, MainUIForm):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # 首次运行没有配置文件时，自动生成默认的 pet_config.json / dismiss_config.json
        ensure_default_configs()

        # .ui 中显示区的完整样式（边框、圆角、滚动条等）；动画时只替换字号
        self._display_base_qss = self.display.styleSheet()

        self.records: List[dict] = []
        self.data_path = os.path.join(BASE_DIR, "name_picker_data.json")

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(70)
        self._anim_timer.timeout.connect(self._anim_tick)
        self._anim_pool: List[str] = []
        self._anim_final: List[str] = []
        self._anim_ticks = 0
        self._anim_total_ticks = 26

        self._progress_dialog = None
        self._downloader = None
        self._update_cancelled = False

        self._pet: FishPet = None
        self._shutting_down = False

        self.plugin_manager = PluginManager()
        self._last_plugin = None
        self._base_title = self.windowTitle()

        self.mode_combo.addItem("全局抽取", "all")
        self.mode_combo.addItem("组内抽取", "single")
        self.mode_combo.addItem("多组抽取", "multi")

        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.draw_btn.clicked.connect(self.draw)
        self.clear_result_btn.clicked.connect(self.display.clear)
        self.admin_btn.clicked.connect(self.open_admin_window)

        self.display.setAlignment(Qt.AlignCenter)

        self._on_mode_changed()
        self._auto_load()

        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.start()

        self._init_pet()

        self.dismiss_guard = DismissGuard(self)
        self.dismiss_guard.start()
        self._init_menus()

    def _init_menus(self):
        # ---- 设置菜单 ----
        action = getattr(self, "actionDismissSettings", None)
        if action is not None:
            action.triggered.connect(self.open_settings_dialog)
        else:
            try:
                menu = self.menuBar().addMenu("设置(&S)")
                menu.addAction("防拖堂设置…").triggered.connect(self.open_settings_dialog)
            except Exception:
                pass

        # ---- 帮助 / 版本菜单 ----
        about = getattr(self, "actionAbout", None)
        if about is not None:
            about.triggered.connect(self.show_about_dialog)
        else:
            try:
                menu = self.menuBar().addMenu("帮助(&H)")
                menu.addAction("版本信息…").triggered.connect(self.show_about_dialog)
            except Exception:
                pass

    def show_about_dialog(self):
        """显示当前版本与运行环境信息。"""
        import sys
        frozen = getattr(sys, "frozen", False)
        lines = [
            "随机点名器（分组版 + 桌宠）",
            "",
            f"当前版本：v{CURRENT_VERSION}",
            f"Python：{sys.version.split()[0]}",
            f"Qt：{QT_VERSION_STR} / PyQt：{PYQT_VERSION_STR}",
            f"运行方式：{'打包版（frozen）' if frozen else '源码运行'}",
        ]
        QMessageBox.information(self, "版本信息", "\n".join(lines))

    def open_settings_dialog(self):
        from .settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            try:
                self.dismiss_guard.reload_config()
            except Exception:
                pass

    # ---------- 桌宠 ----------
    def _init_pet(self):
        try:
            self._pet = FishPet(self)
            self._pet.hide()
        except Exception as e:
            print(f"初始化桌宠失败：{type(e).__name__}: {e}")
            self._pet = None

        try:
            from .autostart import set_autostart
            set_autostart(True)
        except Exception:
            pass

    def _pet_say(self, text, duration=5):
        """供插件调用的气泡接口。"""
        if self._pet:
            self._pet.show_bubble(text, duration)

    def showEvent(self, event):
        super().showEvent(event)
        if self._pet is not None and self._pet.isVisible():
            self._pet.hide_all_ui()
            self._pet.hide()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._shutting_down or self._pet is None:
            return
        if not self._pet.isVisible():
            self._pet.show()
        self._pet.raise_()

    def shutdown_app(self):
        self._shutting_down = True
        try:
            if getattr(self, "dismiss_guard", None) is not None:
                self.dismiss_guard.stop()
                self.dismiss_guard.close_silence_window()
        except Exception:
            pass
        try:
            if self._pet is not None:
                self._pet.close()
        except Exception:
            pass
        self._cleanup_threads()
        QApplication.quit()

    def _cleanup_threads(self):
        if self._anim_timer.isActive():
            self._anim_timer.stop()
        try:
            if self.update_checker and self.update_checker.isRunning():
                self.update_checker.wait(2000)
        except RuntimeError:
            pass
        try:
            if self._downloader and self._downloader.isRunning():
                self._downloader.cancel()
                self._downloader.wait(1000)
        except RuntimeError:
            pass

    # ---------- 自动更新 ----------
    def _on_mode_changed(self, _=None):
        mode = self.mode_combo.currentData()
        self.single_row.setVisible(mode == "single")
        self.multi_widget.setVisible(mode == "multi")
        if mode == "multi":
            # 列表首次显示时 Qt 才创建滚动条，重新应用一次样式表让滚动条也走 QSS
            self.multi_list.setStyleSheet(self.multi_list.styleSheet())

    def _on_update_available(self, version, url, changelog):
        msg = f"发现新版本: v{version}\n\n更新说明:\n{changelog}\n\n是否立即下载并安装更新？"
        reply = QMessageBox.question(
            self, "发现更新", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        import sys
        if not getattr(sys, "frozen", False) or os.name != "nt":
            if url:
                QDesktopServices.openUrl(QUrl(url))
            QMessageBox.information(self, "提示", "当前以源码方式运行，无法自动替换。")
            return

        if not url:
            QMessageBox.warning(self, "提示", "服务端未提供下载链接。")
            return

        self._start_auto_update(url)

    def _start_auto_update(self, url):
        self._update_cancelled = False
        self._progress_dialog = QProgressDialog("正在下载更新…", "取消", 0, 100, self)
        self._progress_dialog.setWindowTitle("自动更新")
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setAutoClose(False)
        self._progress_dialog.setAutoReset(False)
        self._progress_dialog.canceled.connect(self._cancel_update)
        self._progress_dialog.show()

        self._downloader = UpdateDownloader(url, self)
        self._downloader.progress.connect(self._on_update_progress)
        self._downloader.finished_ok.connect(self._on_update_downloaded)
        self._downloader.error_occurred.connect(self._on_update_error)
        self._downloader.start()

    def _cancel_update(self):
        self._update_cancelled = True
        if self._downloader and self._downloader.isRunning():
            self._downloader.cancel()
            self._downloader.wait(2000)
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None

    def _on_update_progress(self, p):
        if self._progress_dialog:
            self._progress_dialog.setValue(p)

    def _on_update_downloaded(self, new_dir):
        if self._progress_dialog:
            self._progress_dialog.setValue(100)
            self._progress_dialog.close()
            self._progress_dialog = None

        reply = QMessageBox.question(
            self, "更新就绪",
            "更新已下载并解压完成。\n点击“是”将立即关闭程序并完成更新（随后自动重启）。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        if not launch_updater(new_dir):
            QMessageBox.warning(self, "提示", "无法启动更新程序，请手动覆盖更新。")
            return

        self._shutting_down = True
        QApplication.quit()

    def _on_update_error(self, err):
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        if self._update_cancelled:
            self._update_cancelled = False
            return
        QMessageBox.critical(self, "更新失败", f"下载或解压更新失败：\n{err}")

    # ---------- 名单 / 分组 ----------
    def _collect_groups(self) -> List[str]:
        seen: List[str] = []
        for r in self.records:
            if r["group"] not in seen:
                seen.append(r["group"])
        return seen if seen else [DEFAULT_GROUP]

    def add_record(self, name: str, group: str = DEFAULT_GROUP, weight: float = DEFAULT_WEIGHT) -> bool:
        name = (name or "").strip()
        if not name:
            return False
        for r in self.records:
            if r["name"] == name:
                return False
        group = (group or "").strip() or DEFAULT_GROUP
        self.records.append({"name": name, "group": group, "weight": float(weight)})
        return True

    def save_data(self) -> bool:
        try:
            data = {"groups": self._collect_groups(), "records": self.records}
            with open(self.data_path, "w", encoding="utf-8") as f:
                import json
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def load_data(self):
        if not os.path.exists(self.data_path):
            return
        try:
            import json
            with open(self.data_path, encoding="utf-8") as f:
                data = json.load(f)
            self.records = []
            for r in data.get("records", []):
                name = str(r.get("name", "")).strip()
                if not name:
                    continue
                self.records.append({
                    "name": name,
                    "group": str(r.get("group", DEFAULT_GROUP)).strip() or DEFAULT_GROUP,
                    "weight": float(r.get("weight", DEFAULT_WEIGHT)),
                })
        except Exception as e:
            print(f"加载失败：{e}")

    def _refresh_all(self):
        self._refresh_groups()
        self._refresh_status()

    def _refresh_groups(self):
        groups = self._collect_groups()
        cur_single = self.single_combo.currentText()
        self.single_combo.blockSignals(True)
        self.single_combo.clear()
        self.single_combo.addItems(groups)
        idx = self.single_combo.findText(cur_single)
        if idx >= 0:
            self.single_combo.setCurrentIndex(idx)
        self.single_combo.blockSignals(False)

        checked = set()
        for i in range(self.multi_list.count()):
            it = self.multi_list.item(i)
            if it.checkState() == Qt.Checked:
                checked.add(it.text())
        self.multi_list.clear()
        for g in groups:
            item = QListWidgetItem(g)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if g in checked else Qt.Unchecked)
            self.multi_list.addItem(item)

    def _refresh_status(self):
        groups = self._collect_groups()
        if self.records:
            text = f"共 {len(self.records)} 人 | {len(groups)} 个分组"
        else:
            text = "尚未导入名单"
        plugin_text = self.plugin_manager.status_text()
        if plugin_text:
            text += f" | {plugin_text}"
        self.status_label.setText(text)

    # ---------- 抽取 ----------
    def quick_pick(self, k: int = 1):
        if not self.records:
            return None, None
        pool = [(r["name"], max(0.0, float(r["weight"]))) for r in self.records]
        available = [p for p in pool if p[1] > 0]
        if not available:
            return None, None
        k = max(1, min(int(k), len(available)))
        allowed = {n for n, _ in available}
        plugin_candidates = [dict(r) for r in self.records if r["name"] in allowed]

        names, plugin_name = self._pick_with_plugins(plugin_candidates, k, "all", [])
        if names is None:
            names = weighted_sample(pool, k)
            plugin_name = None
        return names, plugin_name

    def draw(self):
        if not self.records:
            QMessageBox.warning(self, "提示", "名单为空，请先点“名单管理”导入或添加。")
            return

        mode = self.mode_combo.currentData()
        scope_groups: List[str] = []

        if mode == "all":
            candidates = list(self.records)
        elif mode == "single":
            g = self.single_combo.currentText()
            scope_groups = [g]
            candidates = [r for r in self.records if r["group"] == g]
            if not candidates:
                QMessageBox.warning(self, "提示", f"分组[{g}]没有成员。")
                return
        else:
            selected = [
                self.multi_list.item(i).text()
                for i in range(self.multi_list.count())
                if self.multi_list.item(i).checkState() == Qt.Checked
            ]
            if not selected:
                QMessageBox.warning(self, "提示", "请至少勾选一个分组。")
                return
            scope_groups = list(selected)
            candidates = [r for r in self.records if r["group"] in selected]
            if not candidates:
                QMessageBox.warning(self, "提示", "所选分组没有成员。")
                return

        pool = [(r["name"], max(0.0, float(r["weight"]))) for r in candidates]
        available = [p for p in pool if p[1] > 0]
        if not available:
            QMessageBox.warning(self, "提示", "当前候选人的权重都为 0。")
            return

        k = self.count_spin.value()
        if k > len(available):
            QMessageBox.warning(self, "提示", f"候选人数只有 {len(available)} 人，请调整抽取人数。")
            return

        allowed = {n for n, _ in available}
        plugin_candidates = [dict(r) for r in candidates if r["name"] in allowed]
        result, used_plugin = self._pick_with_plugins(plugin_candidates, k, mode, scope_groups)

        if result is None:
            result = weighted_sample(pool, k)
            used_plugin = None

        self._last_plugin = used_plugin
        self._start_animation([n for n, _ in available], result)

    def _pick_with_plugins(self, plugin_candidates, k, mode, scope_groups):
        if not plugin_candidates:
            return None, None
        try:
            self.plugin_manager.reload_if_changed()
        except Exception:
            pass

        if not self.plugin_manager.plugins:
            return None, None

        context = {
            "mode": mode,
            "mode_text": {"all": "全局抽取", "single": "组内抽取", "multi": "多组抽取"}.get(mode, str(mode)),
            "groups": list(scope_groups),
            "count": k,
            "total_records": len(self.records),
            "candidate_count": len(plugin_candidates),
            "version": CURRENT_VERSION,
            "say": self._pet_say if self._pet else lambda text, duration=5: None,
            "hide_ui": self._pet.hide_all_ui if self._pet else lambda: None,
        }

        try:
            plugin_name, names = self.plugin_manager.try_pick(plugin_candidates, k, context)
        except Exception:
            return None, None

        if not names:
            return None, None
        return names, plugin_name

    def _apply_display_style(self, k: int):
        size = 72 if k == 1 else (48 if k <= 3 else (36 if k <= 8 else 28))
        qss = re.sub(
            r"font-size:\s*\d+px;", f"font-size: {size}px;",
            self._display_base_qss, count=1,
        )
        self.display.setStyleSheet(qss)

    def _set_display_text(self, text: str):
        self.display.setText(text)
        self.display.selectAll()
        self.display.setAlignment(Qt.AlignCenter)
        cursor = self.display.textCursor()
        cursor.clearSelection()
        self.display.setTextCursor(cursor)

    def _start_animation(self, names_pool: List[str], final_result: List[str]):
        self._anim_pool = names_pool
        self._anim_final = final_result
        self._anim_ticks = 0
        self._apply_display_style(len(final_result))
        self.display.clear()
        self.draw_btn.setEnabled(False)
        self.draw_btn.setText("抽取中…")
        self._anim_timer.start()

    def _anim_tick(self):
        self._anim_ticks += 1
        k = len(self._anim_final)
        if self._anim_ticks >= self._anim_total_ticks:
            self._anim_timer.stop()
            self._finish_animation()
            return
        if k == 1:
            self._set_display_text(random.choice(self._anim_pool))
        else:
            picks = random.sample(self._anim_pool, min(k, len(self._anim_pool)))
            self._set_display_text("\n".join(picks))

    def _finish_animation(self):
        self._set_display_text("\n".join(self._anim_final))
        self.draw_btn.setEnabled(True)
        self.draw_btn.setText("开始抽取")
        title = self._base_title or "随机点名器"
        if self._last_plugin:
            title = f"{title} — 插件：{self._last_plugin}"
        self.setWindowTitle(title)

    def closeEvent(self, event):
        self._cleanup_threads()
        super().closeEvent(event)

    def open_admin_window(self):
        dlg = AdminWindow(self, self)
        dlg.exec_()
        self._refresh_all()

    def _auto_load(self):
        self.load_data()
        self._refresh_all()