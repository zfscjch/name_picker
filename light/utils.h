#pragma once
#include <QString>
#include <QStringList>
#include <QList>

namespace Utils {

struct CsvRecord { QString name; QString group; };

QList<int> parseVersion(const QString& v);
bool isNewer(const QString& latest, const QString& current);

QStringList sampleWithoutReplacement(const QStringList& pool, int k);

bool readCsv(const QString& path, QList<CsvRecord>& out, QString& err);
bool writeCsv(const QString& path, const QList<CsvRecord>& records, QString& err);

}