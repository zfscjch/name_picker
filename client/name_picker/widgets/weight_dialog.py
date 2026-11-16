# -*- coding: utf-8 -*-
"""权重管理对话框（需要密码才能进入）。"""
from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QMessageBox, QDialogButtonBox,
)

from ..config import DEFAULT_WEIGHT, ui_path

WeightUIForm, _ = uic.loadUiType(ui_path("weight_dialog.ui"))


class WeightDialog(QDialog, WeightUIForm):
    def __init__(self, records, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.records = records

        self.range_combo.addItem("全部人员", "all")
        self.range_combo.addItem("当前选中行", "selected")
        self.range_combo.addItem("指定分组", "group")
        self.range_combo.currentIndexChanged.connect(self._on_range_changed)
        self.table.setRowCount(len(self.records))

        seen = []
        for r in self.records:
            if r["group"] not in seen:
                seen.append(r["group"])
        self.batch_group.addItems(seen)

        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        for i, r in enumerate(self.records):
            ni = QTableWidgetItem(r["name"])
            ni.setFlags(ni.flags() & ~Qt.ItemIsEditable)
            gi = QTableWidgetItem(r["group"])
            gi.setFlags(gi.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, ni)
            self.table.setItem(i, 1, gi)
            self.table.setItem(i, 2, QTableWidgetItem(f"{r['weight']:.2f}"))

        self.apply_btn.clicked.connect(self.apply_batch)
        self.reset_all_btn.clicked.connect(self.reset_all)
        self.reset_sel_btn.clicked.connect(self.reset_selected)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("保存")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def _on_range_changed(self, _):
        self.group_row.setVisible(self.range_combo.currentData() == "group")

    def apply_batch(self):
        try:
            v = max(0.0, float(self.batch_value.text()))
        except ValueError:
            QMessageBox.warning(self, "提示", "请输入有效的权重数值。")
            return

        scope = self.range_combo.currentData()
        if scope == "all":
            targets = list(range(len(self.records)))
        elif scope == "selected":
            targets = sorted({i.row() for i in self.table.selectedIndexes()})
            if not targets:
                QMessageBox.information(self, "提示", "请先在表格中选中要替换的行。")
                return
        else:
            g = self.batch_group.currentText()
            targets = [i for i, r in enumerate(self.records) if r["group"] == g]
            if not targets:
                QMessageBox.information(self, "提示", f"分组[{g}]没有成员。")
                return

        for i in targets:
            self.table.setItem(i, 2, QTableWidgetItem(f"{v:.2f}"))

        scope_text = {
            "all": "全部人员",
            "selected": "选中行",
            "group": f"分组[{self.batch_group.currentText()}]",
        }[scope]
        QMessageBox.information(
            self, "完成",
            f"已把 {scope_text} 共 {len(targets)} 条记录的权重替换为 {v:.2f}",
        )

    def reset_all(self):
        for i in range(self.table.rowCount()):
            self.table.setItem(i, 2, QTableWidgetItem("1.00"))

    def reset_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "提示", "请先选中要重置的行。")
            return
        for r in rows:
            self.table.setItem(r, 2, QTableWidgetItem("1.00"))

    def get_weights(self) -> dict:
        result = {}
        for i, r in enumerate(self.records):
            item = self.table.item(i, 2)
            try:
                w = float(item.text()) if item else DEFAULT_WEIGHT
            except (ValueError, TypeError):
                w = DEFAULT_WEIGHT
            result[r["name"]] = max(0.0, w)
        return result