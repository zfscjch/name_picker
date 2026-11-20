#include "updater.h"
#include "config.h"
#include "utils.h"

#include <QNetworkReply>
#include <QNetworkRequest>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <QFileInfo>
#include <QDir>
#include <QDirIterator>
#include <QProcess>
#include <QCoreApplication>
#include <QDateTime>

UpdateChecker::UpdateChecker(QObject* parent) : QObject(parent) {}

void UpdateChecker::check() {
    QNetworkRequest req(QUrl(AppConfig::updateApiUrl()));
    req.setHeader(QNetworkRequest::UserAgentHeader, "Mozilla/5.0");
    QNetworkReply* r = nam.get(req);
    connect(r, &QNetworkReply::finished, this, [this, r]() {
        r->deleteLater();
        if (r->error() != QNetworkReply::NoError) {
            emit error(r->errorString());
            return;
        }
        QJsonParseError pe;
        auto doc = QJsonDocument::fromJson(r->readAll(), &pe);
        if (pe.error != QJsonParseError::NoError) {
            emit error(pe.errorString());
            return;
        }
        auto obj = doc.object();
        QString latest = obj.value("version").toString();
        if (latest.isEmpty()) return;
        if (!Utils::isNewer(latest, AppConfig::currentVersion())) return;
        emit updateAvailable(
            latest,
            obj.value("url").toString(),
            obj.value("changelog").toString()
        );
    });
}

UpdateDownloader::UpdateDownloader(QObject* parent) : QObject(parent) {}

void UpdateDownloader::start(const QString& url) {
    cancelled = false;
    total = downloaded = 0;

    QString tmpRoot = QDir::tempPath() + "/name_picker_update_"
                    + QString::number(QDateTime::currentMSecsSinceEpoch());
    QDir().mkpath(tmpRoot);
    QString zipPath = tmpRoot + "/update.zip";

    file = new QFile(zipPath, this);
    if (!file->open(QIODevice::WriteOnly)) {
        emit error("无法创建临时文件");
        return;
    }

    QNetworkRequest req{QUrl(url)};
    req.setHeader(QNetworkRequest::UserAgentHeader, "Mozilla/5.0");
    reply = nam.get(req);

    connect(reply, &QNetworkReply::readyRead, this, [this]() {
        if (file && reply) file->write(reply->readAll());
    });
    connect(reply, &QNetworkReply::downloadProgress, this,
            [this](qint64 recv, qint64 t) {
        total = t;
        if (t > 0) emit progress(int(recv * 100 / t));
    });
    connect(reply, &QNetworkReply::finished, this, [this]() {
        if (!reply || !file) return;
        if (cancelled) {
            emit error("已取消");
            cleanup();
            return;
        }
        if (reply->error() != QNetworkReply::NoError) {
            emit error(reply->errorString());
            cleanup();
            return;
        }
        file->write(reply->readAll());
        file->close();

        QString zipPath = file->fileName();
        QString extractDir = QFileInfo(zipPath).absolutePath() + "/extracted";
        QDir().mkpath(extractDir);

        QProcess p;
        QStringList args;
        args << "-NoProfile" << "-ExecutionPolicy" << "Bypass" << "-Command"
             << QString("Expand-Archive -LiteralPath '%1' -DestinationPath '%2' -Force")
                 .arg(QDir::toNativeSeparators(zipPath),
                      QDir::toNativeSeparators(extractDir));
        p.start("powershell", args);
        if (!p.waitForStarted(10000)) {
            emit error("无法启动 PowerShell 解压");
            cleanup();
            return;
        }
        if (!p.waitForFinished(180000)) {
            p.kill();
            emit error("解压超时");
            cleanup();
            return;
        }
        if (p.exitCode() != 0) {
            QString errMsg = QString::fromLocal8Bit(p.readAllStandardError()).trimmed();
            emit error("解压失败: " + errMsg);
            cleanup();
            return;
        }

        QString exePath;
        QDirIterator it(extractDir, {"name_picker.exe"}, QDir::Files,
                        QDirIterator::Subdirectories);
        if (it.hasNext()) exePath = it.next();
        if (exePath.isEmpty()) {
            emit error("压缩包中未找到 name_picker.exe");
            cleanup();
            return;
        }
        QString newDir = QFileInfo(exePath).absolutePath();

        emit progress(100);
        emit finished(newDir);
        cleanup();
    });
}

void UpdateDownloader::cancel() {
    cancelled = true;
    if (reply) reply->abort();
}

void UpdateDownloader::cleanup() {
    if (reply) { reply->deleteLater(); reply = nullptr; }
    if (file) { file->close(); file->deleteLater(); file = nullptr; }
}

bool Updater::launchUpdater(const QString& newDir) {
    QString curExe = QCoreApplication::applicationFilePath();
    QString curDir = QFileInfo(curExe).absolutePath();
    QString exeName = QFileInfo(curExe).fileName();

    QString batPath = QDir::tempPath() + "/name_picker_updater.bat";

    QString bat;
    bat += "@echo off\r\n";
    bat += "timeout /t 1 /nobreak >nul\r\n";
    bat += ":wait\r\n";
    bat += QString("tasklist /FI \"IMAGENAME eq %1\" 2>nul | find /I \"%1\" >nul\r\n").arg(exeName);
    bat += "if not errorlevel 1 (\r\n";
    bat += "    timeout /t 1 /nobreak >nul\r\n";
    bat += "    goto wait\r\n";
    bat += ")\r\n";
    bat += QString("xcopy /E /Y /I \"%1\\*\" \"%2\\\" >nul\r\n")
             .arg(QDir::toNativeSeparators(newDir),
                  QDir::toNativeSeparators(curDir));
    bat += QString("start \"\" \"%1\"\r\n").arg(QDir::toNativeSeparators(curExe));
    bat += QString("rmdir /S /Q \"%1\" >nul 2>&1\r\n").arg(QDir::toNativeSeparators(newDir));
    bat += "del \"%~f0\"\r\n";

    QFile f(batPath);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) return false;
    f.write(bat.toLocal8Bit());
    f.close();

    QProcess::startDetached("cmd.exe", {"/c", "start", "", "/b", batPath});
    return true;
}