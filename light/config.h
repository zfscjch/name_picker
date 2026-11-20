#pragma once
#include <QString>

namespace AppConfig {
inline QString currentVersion() { return QStringLiteral("1.0.0"); }
inline QString updateApiUrl()    { return QStringLiteral("https://www.cjchcoderchat.site:8080/api/update-light"); }
inline QString defaultGroup()    { return QStringLiteral("默认组"); }

constexpr double petSizeRatio = 0.30;
constexpr int    petSizeMin   = 100;
constexpr int    petSizeMax   = 260;
}