#include "utils.h"
#include "config.h"
#include <QFile>
#include <QSet>
#include <QRegularExpression>
#include <QRandomGenerator>

namespace Utils {

QList<int> parseVersion(const QString& v) {
    QList<int> parts;
    QString s = v.trimmed();
    while (s.startsWith('v') || s.startsWith('V')) s = s.mid(1);
    static const QRegularExpression re("^(\\d+)");
    for (const QString& p : s.split('.')) {
        auto m = re.match(p);
        parts.append(m.hasMatch() ? m.captured(1).toInt() : 0);
    }
    if (parts.isEmpty()) parts.append(0);
    return parts;
}

static int cmpVersion(const QList<int>& a, const QList<int>& b) {
    int n = qMax(a.size(), b.size());
    for (int i = 0; i < n; ++i) {
        int x = (i < a.size()) ? a[i] : 0;
        int y = (i < b.size()) ? b[i] : 0;
        if (x != y) return x < y ? -1 : 1;
    }
    return 0;
}

bool isNewer(const QString& latest, const QString& current) {
    return cmpVersion(parseVersion(latest), parseVersion(current)) > 0;
}

QStringList sampleWithoutReplacement(const QStringList& pool, int k) {
    QStringList result;
    if (pool.isEmpty() || k <= 0) return result;
    QStringList copy = pool;
    k = qMin(k, copy.size());
    for (int i = 0; i < k; ++i) {
        int idx = QRandomGenerator::global()->bounded(copy.size());
        result.append(copy.takeAt(idx));
    }
    return result;
}

static QStringList splitCsvLine(const QString& line) {
    QStringList result;
    QString cur;
    bool inQuote = false;
    for (int i = 0; i < line.size(); ++i) {
        QChar c = line[i];
        if (inQuote) {
            if (c == '"') {
                if (i + 1 < line.size() && line[i + 1] == '"') { cur += '"'; ++i; }
                else inQuote = false;
            } else cur += c;
        } else {
            if (c == '"') inQuote = true;
            else if (c == ',') { result << cur; cur.clear(); }
            else cur += c;
        }
    }
    result << cur;
    return result;
}

static const QSet<QString>& headerWords() {
    static const QSet<QString> s = {
        "name", "姓名", "名字", "group", "组", "分组", "班级"
    };
    return s;
}

bool readCsv(const QString& path, QList<CsvRecord>& out, QString& err) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) { err = f.errorString(); return false; }
    QByteArray data = f.readAll();
    if (data.startsWith("\xEF\xBB\xBF")) data = data.mid(3);
    QString text = QString::fromUtf8(data);

    out.clear();
    for (QString line : text.split('\n')) {
        if (line.endsWith('\r')) line.chop(1);
        if (line.trimmed().isEmpty()) continue;
        QStringList cols = splitCsvLine(line);
        if (cols.isEmpty()) continue;
        QString name = cols[0].trimmed();
        if (name.isEmpty()) continue;
        if (headerWords().contains(name.toLower())) continue;
        QString group = cols.size() > 1 ? cols[1].trimmed() : QString();
        if (group.isEmpty() || headerWords().contains(group.toLower()))
            group = AppConfig::defaultGroup();
        out.append({name, group});
    }
    return true;
}

bool writeCsv(const QString& path, const QList<CsvRecord>& records, QString& err) {
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        err = f.errorString();
        return false;
    }
    f.write("\xEF\xBB\xBF");
    f.write(QStringLiteral("姓名,分组\n").toUtf8());
    auto esc = [](const QString& sIn) {
        if (sIn.contains(',') || sIn.contains('"') || sIn.contains('\n')) {
            QString s = sIn;
            s.replace("\"", "\"\"");
            return "\"" + s + "\"";
        }
        return sIn;
    };
    for (const auto& r : records)
        f.write((esc(r.name) + "," + esc(r.group) + "\n").toUtf8());
    return true;
}

}