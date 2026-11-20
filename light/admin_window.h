#pragma once
#include <QDialog>
#include <QList>
#include "common.h"

class QListWidget;

class AdminWindow : public QDialog {
    Q_OBJECT
public:
    explicit AdminWindow(const QList<Record>& records, QWidget* parent = nullptr);
    QList<Record> getRecords() const;

private slots:
    void onAdd();
    void onDelete();
    void onImport();
    void onExport();
    void refresh();

private:
    QList<Record> tmp;
    QListWidget* list = nullptr;
};