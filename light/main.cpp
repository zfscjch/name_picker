#include <QApplication>
#include "main_window.h"

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    app.setApplicationName("NamePicker");
    app.setQuitOnLastWindowClosed(false);

    MainWindow w;
    w.show();
    return app.exec();
}