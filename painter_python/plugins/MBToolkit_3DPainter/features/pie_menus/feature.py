"""Pie menu lifecycle, with app-wide QAction shortcuts owned by main window."""
from PySide6 import QtCore, QtGui
from .wheel import Wheel
from .editor import Editor
from ...ui.common import error


class Feature:
    id = "pie_menus"
    label = "Pie Menu Creator"
    def __init__(self, app):
        self.app = app
        self.shortcuts = []
        self.wheel = None

    def start(self):
        self.rebuild_shortcuts()

    def rebuild_shortcuts(self):
        self.clear_shortcuts()
        parent = self.app.main_window
        for menu in self.app.settings.data["pie_menus"]:
            if not menu["shortcut"]:
                continue
            action = QtGui.QAction(f"MBToolkit pie: {menu['name']}", parent)
            action.setShortcut(QtGui.QKeySequence(menu["shortcut"]))
            action.setShortcutContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
            action.setAutoRepeat(False)
            action.triggered.connect(lambda checked=False, id=menu["id"], shortcut=menu["shortcut"]:
                                     self.show_wheel(id, shortcut))
            parent.addAction(action)
            self.shortcuts.append(action)

    def clear_shortcuts(self):
        for action in self.shortcuts:
            self.app.main_window.removeAction(action)
            action.deleteLater()
        self.shortcuts.clear()

    def show_wheel(self, menu_id, shortcut=""):
        if self.wheel is not None and self.wheel.isVisible():
            return
        try:
            menu = next(m for m in self.app.settings.data["pie_menus"] if m["id"] == menu_id)
            if not menu["actions"]:
                raise ValueError("This pie menu has no actions")
            if self.wheel is not None:
                self.wheel.deleteLater()
            catalog = dict(self.app.commands.catalog())
            names = menu.get("action_names", [])
            actions = [(ident, (names[i] if i < len(names) else "") or catalog.get(ident, "Missing: " + ident))
                       for i, ident in enumerate(menu["actions"])]
            self.wheel = Wheel(menu["name"], actions, self.dispatch)
            if shortcut:
                self.wheel.set_hold_shortcut(shortcut)
            self.wheel.open_at_cursor()
        except Exception as exc:
            error(self.app.main_window, "Pie menu", exc)

    def dispatch(self, identifier):
        try:
            self.app.commands.execute(identifier)
        except Exception as exc:
            error(self.app.main_window, "Pie action", exc)

    def editor(self):
        Editor(self.app, self.app.main_window).exec()

    def stop(self):
        self.clear_shortcuts()
        if self.wheel is not None:
            self.wheel.close()
            self.wheel.deleteLater()
            self.wheel = None
