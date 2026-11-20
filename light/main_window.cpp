#include "main_window.h"
#include "admin_window.h"
#include "fish_pet.h"
#include "updater.h"
#include "config.h"
#include "utils.h"

#include <QApplication>
#include <QComboBox>
#include <QSpinBox>
#include <QPushButton>
#include <QTextEdit>
#include <QListWidget>
#include <QListWidgetItem>
#include <QLabel>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QMenuBar>
#include <QMenu>
#include <QAction>
#include <QMessageBox>
#include <QProgressDialog>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QTimer>
#include <QCloseEvent>
#include <QDir>
#include <QSet>
#include <QCoreApplication>
#include <QRandomGenerator>

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
    setWindowTitle("随机点名器");
    resize(600, 380);

    buildUi();
    initMenus();

    modeCombo->addItem("全局抽取", "all");
    modeCombo->addItem("组内抽取", "single");
    modeCombo->addItem("多组抽取", "multi");

    connect(modeCombo, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &MainWindow::onModeChanged);
    connect(drawBtn, &QPushButton::clicked, this, &MainWindow::onDraw);
    connect(clearBtn, &QPushButton::clicked, this, &MainWindow::onClearResult);
    connect(adminBtn, &QPushButton::clicked, this, &MainWindow::onAdmin);

    animTimer.setInterval(70);
    connect(&animTimer, &QTimer::timeout, this, &MainWindow::onAnimTick);

    onModeChanged();
    loadData();
    refreshAll();
    initPet();

    checker = new UpdateChecker(this);
    connect(checker, &UpdateChecker::updateAvailable,
            this, &MainWindow::onUpdateAvailable);
    checker->check();
}

MainWindow::~MainWindow() {
    delete pet;
}

void MainWindow::buildUi() {
    auto* central = new QWidget(this);
    setCentralWidget(central);

    auto* mainLayout = new QVBoxLayout(central);
    mainLayout->setContentsMargins(10, 10, 10, 10);
    mainLayout->setSpacing(6);

    auto* title = new QLabel("随机抽取", central);
    title->setStyleSheet("font-size: 28px; font-weight: bold; font-family: 'Microsoft YaHei';");
    mainLayout->addWidget(title);

    auto* setBox = new QGroupBox("抽取设置", central);
    setBox->setStyleSheet(
        "QGroupBox { font-size: 16px; margin-top: 6px; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px;"
        "font-size: 18px; font-weight: bold; }"
        "QComboBox, QSpinBox { font-size: 16px; padding: 4px; }"
    );
    auto* setLayout = new QVBoxLayout(setBox);
    setLayout->setContentsMargins(10, 18, 10, 10);
    setLayout->setSpacing(8);

    auto* modeRow = new QHBoxLayout();
    auto* modeLabel = new QLabel("模式:", setBox);
    modeLabel->setStyleSheet("font-size: 18px;");
    modeCombo = new QComboBox(setBox);
    modeCombo->setMinimumHeight(35);
    auto* countLabel = new QLabel("人数:", setBox);
    countLabel->setStyleSheet("font-size: 18px;");
    countSpin = new QSpinBox(setBox);
    countSpin->setRange(1, 9999);
    countSpin->setValue(1);
    countSpin->setMinimumSize(70, 35);
    countSpin->setMaximumWidth(70);

    modeRow->addWidget(modeLabel);
    modeRow->addWidget(modeCombo, 1);
    modeRow->addWidget(countLabel);
    modeRow->addWidget(countSpin);
    setLayout->addLayout(modeRow);

    singleRow = new QWidget(setBox);
    auto* singleLayout = new QHBoxLayout(singleRow);
    singleLayout->setContentsMargins(0, 0, 0, 0);
    auto* singleLabel = new QLabel("分组:", singleRow);
    singleLabel->setStyleSheet("font-size: 18px;");
    singleCombo = new QComboBox(singleRow);
    singleCombo->setMinimumHeight(35);
    singleLayout->addWidget(singleLabel);
    singleLayout->addWidget(singleCombo, 1);
    singleRow->setVisible(false);
    setLayout->addWidget(singleRow);

    multiWidget = new QWidget(setBox);
    auto* multiLayout = new QVBoxLayout(multiWidget);
    multiLayout->setContentsMargins(0, 0, 0, 0);
    multiList = new QListWidget(multiWidget);
    multiList->setMaximumHeight(80);
    multiList->setStyleSheet("font-size: 16px;");
    multiLayout->addWidget(multiList);
    multiWidget->setVisible(false);
    setLayout->addWidget(multiWidget);

    mainLayout->addWidget(setBox);

    drawBtn = new QPushButton("开始抽取", central);
    drawBtn->setStyleSheet("font-size: 32px; padding: 8px; font-weight: bold;");
    drawBtn->setDefault(true);
    mainLayout->addWidget(drawBtn);

    display = new QTextEdit(central);
    display->setReadOnly(true);
    display->setMinimumHeight(60);
    display->setAlignment(Qt::AlignCenter);
    display->setStyleSheet(
        "font-size: 48px; font-weight: bold; color: #1a73e8;"
        "background-color: #f8f9fa; border: 1px solid #ccc; border-radius: 5px;"
    );
    mainLayout->addWidget(display, 1);

    auto* bottom = new QHBoxLayout();
    clearBtn = new QPushButton("清空结果", central);
    clearBtn->setStyleSheet("padding: 4px 8px; font-size: 18px;");
    statusLabel = new QLabel("尚未导入名单", central);
    statusLabel->setStyleSheet("color: #666; font-size: 14px;");
    adminBtn = new QPushButton("名单管理", central);
    adminBtn->setStyleSheet("padding: 4px 8px; font-size: 18px;");

    bottom->addWidget(clearBtn);
    bottom->addWidget(statusLabel, 1);
    bottom->addWidget(adminBtn);
    mainLayout->addLayout(bottom);
}

void MainWindow::initMenus() {
    auto* helpMenu = menuBar()->addMenu("帮助(&H)");
    helpMenu->addAction("版本信息…", this, &MainWindow::onAbout);
    auto* appMenu = menuBar()->addMenu("程序(&A)");
    appMenu->addAction("退出", qApp, &QApplication::quit);
}

void MainWindow::initPet() {
    pet = new FishPet();
    pet->hide();
    connect(pet, &FishPet::openMainWindow, this, &MainWindow::showAndRaise);
}

void MainWindow::showAndRaise() {
    show();
    raise();
    activateWindow();
}

void MainWindow::showEvent(QShowEvent* e) {
    QMainWindow::showEvent(e);
    if (pet && pet->isVisible()) pet->hide();
}

void MainWindow::hideEvent(QHideEvent* e) {
    QMainWindow::hideEvent(e);
    if (shuttingDown || !pet) return;
    if (!pet->isVisible()) pet->show();
    pet->raise();
}

void MainWindow::closeEvent(QCloseEvent* e) {
    cleanupThreads();
    QMainWindow::closeEvent(e);
}

void MainWindow::cleanupThreads() {
    animTimer.stop();
    if (downloader) downloader->cancel();
}

void MainWindow::onModeChanged() {
    QString mode = modeCombo->currentData().toString();
    singleRow->setVisible(mode == "single");
    multiWidget->setVisible(mode == "multi");
}

void MainWindow::onDraw() {
    if (records.isEmpty()) {
        QMessageBox::warning(this, "提示", "名单为空，请先点“名单管理”导入或添加。");
        return;
    }

    QString mode = modeCombo->currentData().toString();
    QList<Record> candidates;

    if (mode == "all") {
        candidates = records;
    } else if (mode == "single") {
        QString g = singleCombo->currentText();
        for (const auto& r : records)
            if (r.group == g) candidates.append(r);
        if (candidates.isEmpty()) {
            QMessageBox::warning(this, "提示", QString("分组[%1]没有成员。").arg(g));
            return;
        }
    } else {
        QSet<QString> selected;
        for (int i = 0; i < multiList->count(); ++i) {
            auto* it = multiList->item(i);
            if (it->checkState() == Qt::Checked) selected.insert(it->text());
        }
        if (selected.isEmpty()) {
            QMessageBox::warning(this, "提示", "请至少勾选一个分组。");
            return;
        }
        for (const auto& r : records)
            if (selected.contains(r.group)) candidates.append(r);
        if (candidates.isEmpty()) {
            QMessageBox::warning(this, "提示", "所选分组没有成员。");
            return;
        }
    }

    QStringList pool;
    for (const auto& r : candidates) pool << r.name;

    int k = countSpin->value();
    if (k > pool.size()) {
        QMessageBox::warning(this, "提示",
            QString("候选人数只有 %1 人，请调整抽取人数。").arg(pool.size()));
        return;
    }

    QStringList result = Utils::sampleWithoutReplacement(pool, k);
    startAnimation(pool, result);
}

void MainWindow::startAnimation(const QStringList& pool, const QStringList& final) {
    animPool = pool;
    animFinal = final;
    animTicks = 0;
    applyDisplayStyle(final.size());
    display->clear();
    drawBtn->setEnabled(false);
    drawBtn->setText("抽取中…");
    animTimer.start();
}

void MainWindow::onAnimTick() {
    ++animTicks;
    int k = animFinal.size();
    if (animTicks >= animTotalTicks) {
        animTimer.stop();
        onFinishAnim();
        return;
    }
    if (k == 1) {
        setDisplayText(animPool.at(QRandomGenerator::global()->bounded(animPool.size())));
    } else {
        QStringList picks;
        QStringList copy = animPool;
        int take = qMin(k, copy.size());
        for (int i = 0; i < take; ++i) {
            int idx = QRandomGenerator::global()->bounded(copy.size());
            picks.append(copy.takeAt(idx));
        }
        setDisplayText(picks.join("\n"));
    }
}

void MainWindow::onFinishAnim() {
    setDisplayText(animFinal.join("\n"));
    drawBtn->setEnabled(true);
    drawBtn->setText("开始抽取");
}

void MainWindow::setDisplayText(const QString& text) {
    display->setText(text);
    display->selectAll();
    display->setAlignment(Qt::AlignCenter);
    auto cursor = display->textCursor();
    cursor.clearSelection();
    display->setTextCursor(cursor);
}

void MainWindow::applyDisplayStyle(int k) {
    int size = (k == 1) ? 72 : (k <= 3 ? 48 : (k <= 8 ? 36 : 28));
    display->setStyleSheet(QString(
        "font-size: %1px; font-weight: bold; color: #1a73e8;"
        "background-color: #f8f9fa; border: 1px solid #ccc; border-radius: 5px;"
    ).arg(size));
}

void MainWindow::onClearResult() {
    display->clear();
}

void MainWindow::onAdmin() {
    AdminWindow dlg(records, this);
    if (dlg.exec() == QDialog::Accepted) {
        records = dlg.getRecords();
        saveData();
        refreshAll();
    }
}

void MainWindow::onAbout() {
    QString runtime;
#if defined(Q_OS_WIN)
    runtime = "Windows";
#else
    runtime = "非 Windows";
#endif
    QString info = QString(
        "随机点名器（C++ 轻量版）\n\n"
        "当前版本：v%1\n"
        "Qt 版本：%2\n"
        "运行平台：%3"
    ).arg(AppConfig::currentVersion(), QString::fromLatin1(qVersion()), runtime);
    QMessageBox::information(this, "版本信息", info);
}

QString MainWindow::dataPath() const {
    return QCoreApplication::applicationDirPath() + "/name_picker_data.json";
}

void MainWindow::loadData() {
    QFile f(dataPath());
    if (!f.open(QIODevice::ReadOnly)) return;
    QJsonParseError pe;
    auto doc = QJsonDocument::fromJson(f.readAll(), &pe);
    if (pe.error != QJsonParseError::NoError) return;
    auto obj = doc.object();
    records.clear();
    for (const auto& v : obj.value("records").toArray()) {
        auto r = v.toObject();
        QString name = r.value("name").toString().trimmed();
        if (name.isEmpty()) continue;
        QString group = r.value("group").toString().trimmed();
        if (group.isEmpty()) group = AppConfig::defaultGroup();
        records.append({name, group});
    }
}

void MainWindow::saveData() {
    QJsonObject obj;
    QJsonArray arr;
    for (const auto& r : records) {
        QJsonObject o;
        o["name"] = r.name;
        o["group"] = r.group;
        arr.append(o);
    }
    obj["records"] = arr;
    QFile f(dataPath());
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return;
    f.write(QJsonDocument(obj).toJson(QJsonDocument::Indented));
}

QStringList MainWindow::currentGroups() const {
    QStringList seen;
    for (const auto& r : records)
        if (!seen.contains(r.group)) seen << r.group;
    if (seen.isEmpty()) seen << AppConfig::defaultGroup();
    return seen;
}

void MainWindow::refreshAll() {
    refreshGroups();
    refreshStatus();
}

void MainWindow::refreshGroups() {
    QStringList groups = currentGroups();

    QString cur = singleCombo->currentText();
    singleCombo->blockSignals(true);
    singleCombo->clear();
    singleCombo->addItems(groups);
    int idx = singleCombo->findText(cur);
    if (idx >= 0) singleCombo->setCurrentIndex(idx);
    singleCombo->blockSignals(false);

    QSet<QString> checked;
    for (int i = 0; i < multiList->count(); ++i) {
        auto* it = multiList->item(i);
        if (it->checkState() == Qt::Checked) checked.insert(it->text());
    }
    multiList->clear();
    for (const QString& g : groups) {
        auto* it = new QListWidgetItem(g, multiList);
        it->setFlags(it->flags() | Qt::ItemIsUserCheckable);
        it->setCheckState(checked.contains(g) ? Qt::Checked : Qt::Unchecked);
    }
}

void MainWindow::refreshStatus() {
    QStringList groups = currentGroups();
    QString text = records.isEmpty()
        ? QString("尚未导入名单")
        : QString("共 %1 人 | %2 个分组").arg(records.size()).arg(groups.size());
    statusLabel->setText(text);
}

void MainWindow::onUpdateAvailable(const QString& version, const QString& url,
                                   const QString& changelog) {
    QString msg = QString(
        "发现新版本: v%1\n\n更新说明:\n%2\n\n是否立即下载并安装更新？"
    ).arg(version, changelog);
    auto reply = QMessageBox::question(this, "发现更新", msg,
                                       QMessageBox::Yes | QMessageBox::No,
                                       QMessageBox::Yes);
    if (reply != QMessageBox::Yes) return;
    if (url.isEmpty()) {
        QMessageBox::warning(this, "提示", "服务端未提供下载链接。");
        return;
    }
    startAutoUpdate(url);
}

void MainWindow::startAutoUpdate(const QString& url) {
    updateCancelled = false;
    progressDlg = new QProgressDialog("正在下载更新…", "取消", 0, 100, this);
    progressDlg->setWindowTitle("自动更新");
    progressDlg->setWindowModality(Qt::WindowModal);
    progressDlg->setMinimumDuration(0);
    progressDlg->setAutoClose(false);
    progressDlg->setAutoReset(false);
    connect(progressDlg, &QProgressDialog::canceled, this, &MainWindow::onCancelUpdate);
    progressDlg->show();

    downloader = new UpdateDownloader(this);
    connect(downloader, &UpdateDownloader::progress, this, &MainWindow::onUpdateProgress);
    connect(downloader, &UpdateDownloader::finished, this, &MainWindow::onUpdateDownloaded);
    connect(downloader, &UpdateDownloader::error, this, &MainWindow::onUpdateError);
    downloader->start(url);
}

void MainWindow::onCancelUpdate() {
    updateCancelled = true;
    if (downloader) downloader->cancel();
    if (progressDlg) {
        progressDlg->close();
        progressDlg->deleteLater();
        progressDlg = nullptr;
    }
}

void MainWindow::onUpdateProgress(int percent) {
    if (progressDlg) progressDlg->setValue(percent);
}

void MainWindow::onUpdateDownloaded(const QString& newDir) {
    if (progressDlg) {
        progressDlg->setValue(100);
        progressDlg->close();
        progressDlg->deleteLater();
        progressDlg = nullptr;
    }

    auto reply = QMessageBox::question(this, "更新就绪",
        "更新已下载并解压完成。\n"
        "点击“是”将立即关闭程序并完成更新（随后自动重启）。",
        QMessageBox::Yes | QMessageBox::No, QMessageBox::Yes);
    if (reply != QMessageBox::Yes) return;

    if (!Updater::launchUpdater(newDir)) {
        QMessageBox::warning(this, "提示", "无法启动更新程序，请手动覆盖更新。");
        return;
    }

    shuttingDown = true;
    qApp->quit();
}

void MainWindow::onUpdateError(const QString& err) {
    if (progressDlg) {
        progressDlg->close();
        progressDlg->deleteLater();
        progressDlg = nullptr;
    }
    if (updateCancelled) {
        updateCancelled = false;
        return;
    }
    QMessageBox::critical(this, "更新失败", "下载或解压更新失败：\n" + err);
}