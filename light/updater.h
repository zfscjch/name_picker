#pragma once
#include <QObject>
#include <QNetworkAccessManager>

class QNetworkReply;
class QFile;

class UpdateChecker : public QObject {
    Q_OBJECT
public:
    explicit UpdateChecker(QObject* parent = nullptr);
    void check();

signals:
    void updateAvailable(const QString& version, const QString& url, const QString& changelog);
    void error(const QString& msg);

private:
    QNetworkAccessManager nam;
};

class UpdateDownloader : public QObject {
    Q_OBJECT
public:
    explicit UpdateDownloader(QObject* parent = nullptr);
    void start(const QString& url);
    void cancel();

signals:
    void progress(int percent);
    void finished(const QString& extractedDir);
    void error(const QString& msg);

private:
    void cleanup();

    QNetworkAccessManager nam;
    QNetworkReply* reply = nullptr;
    QFile* file = nullptr;
    qint64 total = 0;
    qint64 downloaded = 0;
    bool cancelled = false;
};

namespace Updater {
bool launchUpdater(const QString& newDir);
}