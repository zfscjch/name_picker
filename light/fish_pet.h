#pragma once
#include <QWidget>
#include <QPixmap>
#include <QPoint>

class QLabel;
class QTimer;

class FishPet : public QWidget {
    Q_OBJECT
public:
    explicit FishPet(QWidget* parent = nullptr);
    ~FishPet() override;

    void showBubble(const QString& text, int durationMs = 5000);

signals:
    void openMainWindow();

protected:
    void paintEvent(QPaintEvent* e) override;
    void mousePressEvent(QMouseEvent* e) override;
    void mouseMoveEvent(QMouseEvent* e) override;
    void mouseReleaseEvent(QMouseEvent* e) override;
    void contextMenuEvent(QContextMenuEvent* e) override;

private:
    void loadPixmap();
    void positionOnScreen();

    QPixmap pixmap;
    QLabel* bubble = nullptr;
    QTimer* bubbleTimer = nullptr;
    bool dragging = false;
    bool moved = false;
    QPoint dragStart;
};