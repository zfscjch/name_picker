#pragma once
#include <QMainWindow>
#include <QTimer>
#include <QList>
#include "common.h"

class QComboBox;
class QSpinBox;
class QPushButton;
class QTextEdit;
class QListWidget;
class QLabel;
class QProgressDialog;
class FishPet;
class UpdateChecker;
class UpdateDownloader;

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() override;

    void showAndRaise();
    QStringList currentGroups() const;

protected:
    void showEvent(QShowEvent* e) override;
    void hideEvent(QHideEvent* e) override;
    void closeEvent(QCloseEvent* e) override;

private slots:
    void onModeChanged();
    void onDraw();
    void onAnimTick();
    void onFinishAnim();
    void onClearResult();
    void onAdmin();
    void onAbout();
    void onUpdateAvailable(const QString& version, const QString& url, const QString& changelog);
    void onUpdateProgress(int percent);
    void onUpdateDownloaded(const QString& newDir);
    void onUpdateError(const QString& err);
    void onCancelUpdate();

private:
    void buildUi();
    void initMenus();
    void initPet();
    void loadData();
    void saveData();
    void refreshGroups();
    void refreshStatus();
    void refreshAll();
    void startAnimation(const QStringList& pool, const QStringList& final);
    void setDisplayText(const QString& text);
    void applyDisplayStyle(int k);
    void cleanupThreads();
    void startAutoUpdate(const QString& url);
    QString dataPath() const;

    QComboBox* modeCombo = nullptr;
    QSpinBox* countSpin = nullptr;
    QWidget* singleRow = nullptr;
    QComboBox* singleCombo = nullptr;
    QWidget* multiWidget = nullptr;
    QListWidget* multiList = nullptr;
    QPushButton* drawBtn = nullptr;
    QTextEdit* display = nullptr;
    QPushButton* clearBtn = nullptr;
    QPushButton* adminBtn = nullptr;
    QLabel* statusLabel = nullptr;

    QList<Record> records;

    QTimer animTimer;
    QStringList animPool;
    QStringList animFinal;
    int animTicks = 0;
    static constexpr int animTotalTicks = 26;

    FishPet* pet = nullptr;
    bool shuttingDown = false;

    UpdateChecker* checker = nullptr;
    UpdateDownloader* downloader = nullptr;
    QProgressDialog* progressDlg = nullptr;
    bool updateCancelled = false;
};