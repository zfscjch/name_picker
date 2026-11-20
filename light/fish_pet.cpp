#include "fish_pet.h"
#include "config.h"

#include <QApplication>
#include <QLabel>
#include <QTimer>
#include <QMouseEvent>
#include <QContextMenuEvent>
#include <QMenu>
#include <QPainter>
#include <QScreen>
#include <QGuiApplication>
#include <QCoreApplication>

FishPet::FishPet(QWidget* parent) : QWidget(parent) {
    setWindowFlags(Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint | Qt::Tool);
    setAttribute(Qt::WA_TranslucentBackground);
    setCursor(Qt::PointingHandCursor);

    loadPixmap();

    QScreen* screen = QGuiApplication::primaryScreen();
    QRect g = screen ? screen->availableGeometry() : QRect(0, 0, 1280, 720);
    int shortSide = qMin(g.width(), g.height());
    int size = qBound((int)AppConfig::petSizeMin,
                     (int)(shortSide * AppConfig::petSizeRatio),
                     (int)AppConfig::petSizeMax);
    int targetWidth = size;
    int targetHeight = targetWidth * pixmap.height() / pixmap.width();
    setFixedSize(targetWidth, targetHeight);

    positionOnScreen();

    bubble = new QLabel(nullptr, Qt::ToolTip | Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint);
    bubble->setAttribute(Qt::WA_TranslucentBackground);
    bubble->setAttribute(Qt::WA_ShowWithoutActivating);
    bubble->setStyleSheet(
        "background-color: rgba(30, 30, 30, 220);"
        "color: white; border-radius: 10px;"
        "padding: 8px 14px; font-size: 15px;"
    );
    bubble->hide();

    bubbleTimer = new QTimer(this);
    bubbleTimer->setSingleShot(true);
    connect(bubbleTimer, &QTimer::timeout, bubble, &QWidget::hide);
}

FishPet::~FishPet() {
    if (bubble) bubble->deleteLater();
}

void FishPet::loadPixmap() {
    QString exeDir = QCoreApplication::applicationDirPath();
    QStringList candidates = {
        exeDir + "/pet.png",
        exeDir + "/resources/pet.png",
        ":/pet.png",
    };
    for (const auto& p : candidates) {
        if (pixmap.load(p)) return;
    }
}

void FishPet::positionOnScreen() {
    QScreen* screen = QGuiApplication::primaryScreen();
    QRect g = screen ? screen->availableGeometry() : QRect(0, 0, 1280, 720);
    move(g.right() - width() - 40, g.bottom() - height() - 40);
}

void FishPet::paintEvent(QPaintEvent*) {
    QPainter p(this);
    p.setRenderHint(QPainter::SmoothPixmapTransform, true);
    if (!pixmap.isNull())
        p.drawPixmap(rect(), pixmap.scaled(size(), Qt::KeepAspectRatio, Qt::SmoothTransformation));
}

void FishPet::mousePressEvent(QMouseEvent* e) {
    if (e->button() == Qt::LeftButton) {
        dragging = true;
        moved = false;
        dragStart = e->globalPos();
    }
}

void FishPet::mouseMoveEvent(QMouseEvent* e) {
    if (!dragging) return;
    QPoint delta = e->globalPos() - dragStart;
    if (delta.manhattanLength() > 4) moved = true;
    if (moved) {
        move(pos() + delta);
        dragStart = e->globalPos();
    }
}

void FishPet::mouseReleaseEvent(QMouseEvent* e) {
    if (e->button() == Qt::LeftButton) {
        dragging = false;
        if (!moved) emit openMainWindow();
    }
}

void FishPet::contextMenuEvent(QContextMenuEvent* e) {
    QMenu menu;
    menu.addAction("打开主窗口", this, &FishPet::openMainWindow);
    menu.addSeparator();
    menu.addAction("退出", qApp, &QApplication::quit);
    menu.exec(e->globalPos());
}

void FishPet::showBubble(const QString& text, int durationMs) {
    if (!bubble) return;
    bubble->setText(text);
    bubble->adjustSize();

    QPoint base = mapToGlobal(QPoint(0, 0));
    int bx = base.x() + width() / 2 - bubble->width() / 2;
    int by = base.y() - bubble->height() - 8;

    QScreen* screen = QGuiApplication::primaryScreen();
    QRect g = screen ? screen->availableGeometry() : QRect(0, 0, 1280, 720);
    bx = qBound(g.left(), bx, g.right() - bubble->width());
    if (by < g.top()) by = base.y() + height() + 8;

    bubble->move(bx, by);
    bubble->show();
    bubble->raise();
    if (bubbleTimer) bubbleTimer->start(durationMs);
}