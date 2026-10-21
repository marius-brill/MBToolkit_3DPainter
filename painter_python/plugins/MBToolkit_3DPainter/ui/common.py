from PySide6 import QtWidgets


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def error(parent, title, exc):
    QtWidgets.QMessageBox.warning(parent, title, str(exc))
