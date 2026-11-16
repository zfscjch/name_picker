# -*- coding: utf-8 -*-
"""名单管理窗口（独立窗口）。"""
import os
import re

from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QMessageBox, QInputDialog, QFileDialog, QLineEdit, QDialogButtonBox,
)

from ..config import ADMIN_PASSWORD, DEFAULT_GROUP, ui_path
from ..utils import read_csv_names, read_xlsx_columns, save_csv
from .weight_dialog import WeightDialog

AdminUIForm, _ = uic.loadUiType(ui_path("admin_window.ui"))


class AdminWindow(QDialog, AdminUIForm):
    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.owner = owner

        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.browse_btn.clicked.connect(self.browse_file)
        self.imp_btn.clicked.connect(self.import_file)
        self.add_btn.clicked.connect(self.add_manual)
        self.del_btn.clicked.connect(self.delete_selected)
        self.clear_btn.clicked.connect(self.clear_all)
        self.weight_btn.clicked.connect(self.open_weight_dialog)
        self.buttonBox.button(QDialogButtonBox.Close).setText("关闭")
        self.buttonBox.rejected.connect(self.accept)

        self._refresh()

    def _refresh(self):
        recs = self.owner.records
        self.table.setRowCount(len(recs))
        for i, rec in enumerate(recs):
            self.table.setItem(i, 0, QTableWidgetItem(rec["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(rec["group"]))
            self.table.setItem(i, 2, QTableWidgetItem(f"{rec['weight']:.2f}"))

        groups = self.owner._collect_groups()
        self.status_label.setText(f"共 {len(recs)} 人 | {len(groups)} 个分组")

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择名单文件", "",
            "名单文件 (*.xlsx *.xlsm *.csv);;Excel (*.xlsx *.xlsm);;CSV (*.csv)",
        )
        if path:
            self.path_edit.setText(path)

    def add_manual(self):
        text = self.manual_names.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入姓名！")
            return
        group = self.manual_group.text().strip() or DEFAULT_GROUP
        parts = re.split(r"[,，、;；\n\r]+", text)
        names = [p.strip() for p in parts if p.strip()]
        if not names:
            QMessageBox.warning(self, "提示", "没有可用的姓名。")
            return

        added = skipped = 0
        for n in names:
            if self.owner.add_record(n, group):
                added += 1
            else:
                skipped += 1

        if added:
            self.manual_names.clear()
            self.owner.save_data()
            self._refresh()

        msg = f"已添加 {added} 人"
        if skipped:
            msg += f"，跳过 {skipped} 个已存在姓名"
        QMessageBox.information(self, "结果", msg)

    def import_file(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "提示", "请先选择文件！")
            return
        if not os.path.exists(path):
            QMessageBox.critical(self, "错误", "文件不存在！")
            return

        csv_out = None
        if path.lower().endswith(".csv"):
            ok, data = read_csv_names(path)
        else:
            name_col = self.name_col_edit.text().strip() or "A"
            group_col = self.group_col_edit.text().strip() or None
            ok, data = read_xlsx_columns(path, name_col, group_col)
            csv_out = os.path.splitext(path)[0] + "_名单.csv"

        if not ok:
            QMessageBox.critical(self, "错误", f"读取失败：\n{data}")
            return
        if not data:
            QMessageBox.warning(self, "提示", "未读到任何内容！")
            return

        added = skipped = 0
        for name, group in data:
            if self.owner.add_record(name, group):
                added += 1
            else:
                skipped += 1

        self.owner.save_data()
        self._refresh()

        if csv_out:
            try:
                save_csv(csv_out, self.owner.records)
            except Exception as e:
                print(f"导出 CSV 失败：{e}")

        msg = f"导入 {added} 人"
        if skipped:
            msg += f"，跳过 {skipped} 个重复姓名"
        if csv_out:
            msg += f"\n\n名单 CSV 已保存到：\n{csv_out}"
        QMessageBox.information(self, "完成", msg)

    def delete_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要删除的行。")
            return
        if QMessageBox.question(self, "确认", f"确定删除 {len(rows)} 条记录吗？") != QMessageBox.Yes:
            return
        recs = self.owner.records
        for r in rows:
            if 0 <= r < len(recs):
                del recs[r]
        self.owner.save_data()
        self._refresh()

    def clear_all(self):
        if not self.owner.records:
            return
        if QMessageBox.question(self, "确认", "确定清空全部名单吗？此操作不可恢复。") != QMessageBox.Yes:
            return
        self.owner.records.clear()
        self.owner.save_data()
        self._refresh()

    def open_weight_dialog(self):
        recs = self.owner.records
        if not recs:
            QMessageBox.warning(self, "提示", "名单为空。")
            return
        pwd, ok = QInputDialog.getText(
            self, "后台验证", "请输入管理密码：", QLineEdit.Password,
        )
        if not ok:
            return
        if not ADMIN_PASSWORD in pwd: # 特殊密码判断方法，防止被偷看
            QMessageBox.critical(self, "验证失败", "密码错误！")
            return

        dlg = WeightDialog(recs, self)
        if dlg.exec_() == QDialog.Accepted:
            new_weights = dlg.get_weights()
            for r in recs:
                if r["name"] in new_weights:
                    r["weight"] = new_weights[r["name"]]
            self.owner.save_data()
            self._refresh()
            QMessageBox.information(self, "成功", "权重已更新并保存。")