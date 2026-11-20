#include "admin_window.h"
#include "utils.h"
#include "config.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QListWidget>
#include <QPushButton>
#include <QDialogButtonBox>
#include <QMessageBox>
#include <QInputDialog>
#include <QFileDialog>
#include <QLineEdit>
#include <QSet>
#include <QRegularExpression>

AdminWindow::AdminWindow(const QList<Record>& records, QWidget* parent)
    : QDialog(parent), tmp(records) {
    setWindowTitle("名单管理");
    resize(500, 460);

    auto* layout = new QVBoxLayout(this);

    list = new QListWidget(this);
    layout->addWidget(list, 1);

    auto* row = new QHBoxLayout();
    auto* addBtn = new QPushButton("添加", this);
    auto* delBtn = new QPushButton("删除选中", this);
    auto* importBtn = new QPushButton("导入 CSV", this);
    auto* exportBtn = new QPushButton("导出 CSV", this);
    row->addWidget(addBtn);
    row->addWidget(delBtn);
    row->addStretch(1);
    row->addWidget(importBtn);
    row->addWidget(exportBtn);
    layout->addLayout(row);

    auto* box = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel, this);
    layout->addWidget(box);
    connect(box, &QDialogButtonBox::accepted, this, &QDialog::accept);
    connect(box, &QDialogButtonBox::rejected, this, &QDialog::reject);

    connect(addBtn, &QPushButton::clicked, this, &AdminWindow::onAdd);
    connect(delBtn, &QPushButton::clicked, this, &AdminWindow::onDelete);
    connect(importBtn, &QPushButton::clicked, this, &AdminWindow::onImport);
    connect(exportBtn, &QPushButton::clicked, this, &AdminWindow::onExport);

    refresh();
}

QList<Record> AdminWindow::getRecords() const { return tmp; }

void AdminWindow::refresh() {
    list->clear();
    for (const auto& r : tmp)
        list->addItem(QString("%1  [%2]").arg(r.name, r.group));
}

void AdminWindow::onAdd() {
    bool ok = false;
    QString text = QInputDialog::getText(this, "添加成员", "输入姓名（多个用逗号分隔）：",
                                        QLineEdit::Normal, "", &ok);
    if (!ok || text.trimmed().isEmpty()) return;
    QStringList parts = text.split(QRegularExpression("[,，;；\\s]+"),
                                   Qt::SkipEmptyParts);
    QSet<QString> existing;
    for (const auto& r : tmp) existing.insert(r.name);
    for (const auto& p : parts) {
        QString n = p.trimmed();
        if (n.isEmpty() || existing.contains(n)) continue;
        tmp.append({n, AppConfig::defaultGroup()});
        existing.insert(n);
    }
    refresh();
}

void AdminWindow::onDelete() {
    auto* item = list->currentItem();
    if (!item) return;
    int row = list->row(item);
    if (row < 0 || row >= tmp.size()) return;
    tmp.removeAt(row);
    refresh();
}

void AdminWindow::onImport() {
    QString path = QFileDialog::getOpenFileName(this, "导入名单", "",
                                                "CSV 文件 (*.csv);;所有文件 (*)");
    if (path.isEmpty()) return;
    QList<Utils::CsvRecord> rows;
    QString err;
    if (!Utils::readCsv(path, rows, err)) {
        QMessageBox::warning(this, "错误", "读取失败: " + err);
        return;
    }
    QSet<QString> existing;
    for (const auto& r : tmp) existing.insert(r.name);
    int added = 0, dup = 0;
    for (const auto& r : rows) {
        if (existing.contains(r.name)) { ++dup; continue; }
        tmp.append({r.name, r.group});
        existing.insert(r.name);
        ++added;
    }
    refresh();
    QMessageBox::information(this, "完成",
        QString("新增 %1 条，跳过重复 %2 条。").arg(added).arg(dup));
}

void AdminWindow::onExport() {
    QString path = QFileDialog::getSaveFileName(this, "导出名单", "name_picker_list.csv",
                                                "CSV 文件 (*.csv)");
    if (path.isEmpty()) return;
    QList<Utils::CsvRecord> rows;
    for (const auto& r : tmp) rows.append({r.name, r.group});
    QString err;
    if (!Utils::writeCsv(path, rows, err)) {
        QMessageBox::warning(this, "错误", "写入失败: " + err);
        return;
    }
    QMessageBox::information(this, "完成", "已导出。");
}