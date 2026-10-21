"""CRUD editor for pie definitions. Changes are committed explicitly."""
import uuid
from PySide6 import QtCore, QtGui, QtWidgets
from ...core.models import MAX_PIE_ACTIONS, clone_config
from ...ui.common import error


class Editor(QtWidgets.QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("MBToolkit · Pie Menu Editor")
        self.resize(670, 460)
        self.menus = clone_config(app.settings.data["pie_menus"])
        outer = QtWidgets.QVBoxLayout(self)
        panes = QtWidgets.QHBoxLayout()
        outer.addLayout(panes, 1)
        left = QtWidgets.QVBoxLayout()
        panes.addLayout(left, 1)
        left.addWidget(QtWidgets.QLabel("Pie menus"))
        self.menulist = QtWidgets.QListWidget()
        left.addWidget(self.menulist)
        menu_tools = QtWidgets.QHBoxLayout()
        left.addLayout(menu_tools)
        for text, fn in (("New", self.add_menu), ("Duplicate", self.duplicate), ("Delete", self.delete_menu)):
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(fn)
            menu_tools.addWidget(btn)
        right = QtWidgets.QVBoxLayout()
        panes.addLayout(right, 2)
        form = QtWidgets.QFormLayout()
        right.addLayout(form)
        self.name = QtWidgets.QLineEdit()
        form.addRow("Name", self.name)
        self.shortcut = QtGui.QKeySequence()
        self.keyedit = QtWidgets.QKeySequenceEdit()
        form.addRow("Shortcut", self.keyedit)
        self.name.editingFinished.connect(self.commit_current)
        self.keyedit.keySequenceChanged.connect(lambda *_: self.commit_current())
        right.addWidget(QtWidgets.QLabel("Actions (clockwise from top)"))
        self.actions = QtWidgets.QListWidget()
        self.actions.itemChanged.connect(self.rename_action)
        self.actions.setToolTip("Double-click a feature to rename it. Clear its name to restore the default.")
        right.addWidget(self.actions, 1)
        right.addWidget(QtWidgets.QLabel("Double-click a feature to edit its display name."))
        action_line = QtWidgets.QHBoxLayout()
        right.addLayout(action_line)
        self.catalog = QtWidgets.QComboBox()
        self.catalog.setMinimumWidth(180)
        action_line.addWidget(self.catalog, 1)
        for text, fn in (("Add", self.add_action), ("Remove", self.remove_action),
                         ("↑", lambda: self.move_action(-1)), ("↓", lambda: self.move_action(1))):
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(fn)
            action_line.addWidget(btn)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Save |
                                              QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.menulist.currentRowChanged.connect(self.select_menu)
        self.current = -1
        self.populate()

    def populate(self, select=0):
        self.commit_current()
        self.current = -1
        blocked = self.menulist.blockSignals(True)
        try:
            self.menulist.clear()
            self.menulist.addItems([m["name"] for m in self.menus])
            self.menulist.setCurrentRow(min(select, len(self.menus)-1))
        finally:
            self.menulist.blockSignals(blocked)
        self.select_menu(self.menulist.currentRow())

    def select_menu(self, index):
        self.commit_current()
        self.current = index
        active = 0 <= index < len(self.menus)
        self.name.setEnabled(active)
        self.keyedit.setEnabled(active)
        self.actions.clear()
        self.catalog.clear()
        for ident, title in self.app.commands.catalog():
            self.catalog.addItem(title, ident)
        if active:
            m = self.menus[index]
            self.name.setText(m["name"])
            blocked = self.keyedit.blockSignals(True)
            try:
                self.keyedit.setKeySequence(QtGui.QKeySequence(m["shortcut"]))
            finally:
                self.keyedit.blockSignals(blocked)
            names = m.get("action_names", [])
            for i, command in enumerate(m["actions"]):
                self.append_action_item(command, names[i] if i < len(names) else "")
        else:
            self.name.clear()
            self.keyedit.clear()

    def label(self, command):
        return next((label for ident,label in self.app.commands.catalog() if ident==command),
                    "Missing: " + command)

    def append_action_item(self, command, name=""):
        item = QtWidgets.QListWidgetItem(name or self.label(command))
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
        item.setToolTip(f"Feature: {self.label(command)}\nCommand: {command}\nDouble-click to rename.")
        blocked = self.actions.blockSignals(True)
        try:
            self.actions.addItem(item)
        finally:
            self.actions.blockSignals(blocked)

    def action_names(self):
        menu = self.menus[self.current]
        names = menu.setdefault("action_names", [])
        names.extend([""] * (len(menu["actions"])-len(names)))
        return names

    def rename_action(self, item):
        if not 0 <= self.current < len(self.menus):
            return
        index = self.actions.row(item)
        if not 0 <= index < len(self.menus[self.current]["actions"]):
            return
        name = item.text().strip()[:80]
        self.action_names()[index] = name
        command = self.menus[self.current]["actions"][index]
        blocked = self.actions.blockSignals(True)
        try:
            item.setText(name or self.label(command))
        finally:
            self.actions.blockSignals(blocked)

    def commit_current(self):
        if 0 <= self.current < len(self.menus):
            m = self.menus[self.current]
            m["name"] = self.name.text().strip()[:80] or m["id"]
            m["shortcut"] = self.keyedit.keySequence().toString(QtGui.QKeySequence.SequenceFormat.PortableText)
            self.menulist.item(self.current).setText(m["name"])

    def add_menu(self):
        self.commit_current()
        self.menus.append({"id": "menu_" + uuid.uuid4().hex[:10],
                           "name": "New Pie Menu", "shortcut": "", "actions": []})
        self.populate(len(self.menus)-1)

    def duplicate(self):
        self.commit_current()
        if self.current < 0:
            return
        m = clone_config(self.menus[self.current])
        m["id"] = "menu_" + uuid.uuid4().hex[:10]
        m["name"] += " Copy"
        m["shortcut"] = ""
        self.menus.append(m)
        self.populate(len(self.menus)-1)

    def delete_menu(self):
        if self.current >= 0:
            index = self.current
            self.current = -1
            self.menus.pop(index)
            self.populate(max(0, index-1))

    def add_action(self):
        if self.current < 0 or self.catalog.currentData() is None:
            return
        values = self.menus[self.current]["actions"]
        if len(values) >= MAX_PIE_ACTIONS:
            error(self, "Pie menu", f"Maximum {MAX_PIE_ACTIONS} slices")
            return
        values.append(self.catalog.currentData())
        self.action_names()
        self.append_action_item(values[-1])

    def remove_action(self):
        i = self.actions.currentRow()
        if self.current >= 0 and i >= 0:
            self.action_names().pop(i)
            self.menus[self.current]["actions"].pop(i)
            self.actions.takeItem(i)

    def move_action(self, direction):
        i = self.actions.currentRow()
        if self.current < 0 or i < 0:
            return
        actions = self.menus[self.current]["actions"]
        j = i + direction
        if 0 <= j < len(actions):
            names = self.action_names()
            names[i], names[j] = names[j], names[i]
            actions[i], actions[j] = actions[j], actions[i]
            item = self.actions.takeItem(i)
            self.actions.insertItem(j, item)
            self.actions.setCurrentRow(j)

    def accept(self):
        self.commit_current()
        # Reject duplicated local shortcuts and obvious collisions with Painter actions.
        used = set()
        conflicts = []
        for menu in self.menus:
            seq = QtGui.QKeySequence(menu["shortcut"])
            if seq.isEmpty():
                continue
            key = seq.toString(QtGui.QKeySequence.SequenceFormat.PortableText)
            if key in used:
                conflicts.append(key)
            used.add(key)
        if conflicts:
            error(self, "Shortcut conflict", "Repeated pie shortcut: " + ", ".join(conflicts))
            return
        external = []
        for native in self.app.main_window.findChildren(QtGui.QAction):
            if native.text().startswith("MBToolkit pie:"):
                continue
            key = native.shortcut().toString(QtGui.QKeySequence.SequenceFormat.PortableText)
            if key and key in used:
                external.append(f"{key}: {native.text()}")
        if external:
            decision = QtWidgets.QMessageBox.warning(
                self, "Potential Painter shortcut conflicts",
                "These shortcut combinations appear to be used already:\n" +
                "\n".join(external[:12]) +
                "\n\nKeep the new assignments anyway? They may fail to trigger.",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if decision != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        try:
            self.app.settings.data["pie_menus"] = self.menus
            self.app.settings.save()
            self.app.refresh_pie_shortcuts()
        except Exception as exc:
            error(self, "Save pie menus", exc)
            return
        super().accept()
