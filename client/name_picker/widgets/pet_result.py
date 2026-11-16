# -*- coding: utf-8 -*-
"""桌宠抽名结果对话框（置顶）。"""
from typing import List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox,
)


class PetResultDialog(QDialog):
    """桌宠抽名结果对话框（置顶）。"""

    def __init__(self, names: List[str], plugin_name: str = None, message: str = None):
        super().__init__(None, Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("点名结果")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        title = QLabel("🎉 抽中啦" if names else "🤔 提示")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1a73e8;")
        layout.addWidget(title)

        if names:
            text = "\n".join(names)
            size = 46 if len(names) == 1 else (32 if len(names) <= 3 else 22)
        else:
            text = message or "（名单为空或全部权重为 0）"
            size = 16

        name_label = QLabel(text)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setStyleSheet(
            f"font-size: {size}px; font-weight: bold; color: #0b5cad;"
            "background: #eef5ff; border-radius: 10px; padding: 18px 10px;"
        )
        layout.addWidget(name_label)

        if plugin_name:
            p = QLabel(f"由插件「{plugin_name}」抽取")
            p.setAlignment(Qt.AlignCenter)
            p.setStyleSheet("color: #8a8a8a; font-size: 12px;")
            layout.addWidget(p)

        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.button(QDialogButtonBox.Ok).setText("好的")
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)