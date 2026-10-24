"""CRUD editor for pie definitions. Changes are committed explicitly."""
import uuid
from PySide6 import QtCore, QtGui, QtWidgets
from ...core.models import MAX_PIE_ACTIONS, clone_config
from ...ui.common import error
from .preview import Preview
from .macro_editor import MacroEditor


class Editor(QtWidgets.QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("MBToolkit · Pie Menu Editor")
        self.resize(1100, 800)
        self.menus = clone_config(app.settings.data["pie_menus"])
        outer = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget()
        outer.addWidget(self.tabs, 1)
        page = QtWidgets.QWidget()
        self.tabs.addTab(page, "Pie Menus")
        self.macro_editor = MacroEditor(app.settings.data.get("macros", []))
        self.tabs.addTab(self.macro_editor, "Macros")
        page_layout = QtWidgets.QVBoxLayout(page)
        page_layout.setContentsMargins(9, 9, 9, 9)
        page_layout.setSpacing(6)
        panes = QtWidgets.QHBoxLayout()
        panes.setSpacing(6)
        page_layout.addLayout(panes, 1)
        sidebar = QtWidgets.QWidget()
        sidebar.setFixedWidth(264)
        left = QtWidgets.QVBoxLayout(sidebar)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(6)
        panes.addWidget(sidebar)
        self.menulist = QtWidgets.QListWidget()
        left.addWidget(self.menulist)
        menu_tools = QtWidgets.QVBoxLayout()
        menu_tools.setSpacing(6)
        left.addLayout(menu_tools)
        for text, fn in (("New", self.add_menu), ("Duplicate", self.duplicate), ("Delete", self.delete_menu)):
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(fn)
            menu_tools.addWidget(btn)
        right = QtWidgets.QVBoxLayout()
        panes.addLayout(right, 3)
        form = QtWidgets.QFormLayout()
        right.addLayout(form)
        self.name = QtWidgets.QLineEdit()
        form.addRow("Name", self.name)
        self.shortcut = QtGui.QKeySequence()
        self.keyedit = QtWidgets.QKeySequenceEdit()
        form.addRow("Shortcut", self.keyedit)
        self.name.editingFinished.connect(self.commit_current)
        self.keyedit.keySequenceChanged.connect(lambda *_: self.commit_current())
        self.actions = QtWidgets.QListWidget()
        self.actions.hide()
        self.preview = Preview(self.actions.setCurrentRow, self.reorder_slice)
        right.addWidget(self.preview, 1, QtCore.Qt.AlignmentFlag.AlignCenter)
        self.actions.currentRowChanged.connect(self.select_slice)
        self.actions.itemChanged.connect(self.rename_action)
        self.actions.setToolTip("Double-click a feature to rename it. Clear its name to restore the default.")
        self.display_name = QtWidgets.QLineEdit()
        self.display_name.setPlaceholderText("Default function name")
        form.addRow("Slice display name", self.display_name)
        self.display_name.editingFinished.connect(self.edit_slice_name)
        search = QtWidgets.QLineEdit()
        search.setPlaceholderText("Search Painter functions, toolkit tools, macros, scripts…")
        search.textChanged.connect(self.filter_catalog)
        right.addWidget(search)
        action_line = QtWidgets.QHBoxLayout()
        right.addLayout(action_line)
        self.catalog = QtWidgets.QComboBox()
        self.catalog.setMinimumWidth(180)
        self.catalog.activated.connect(self.assign_function)
        action_line.addWidget(self.catalog, 1)
        for text, fn in (("Add slice", self.add_action), ("Remove", self.remove_action)):
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
        self.tabs.currentChanged.connect(self.refresh_catalog)
        self.populate()

    def command_catalog(self):
        items = [(ident, label) for ident, label in self.app.commands.catalog() if not ident.startswith("macro:")]
        items.extend(("macro:" + m["id"], "Macro: " + m["name"]) for m in self.macro_editor.macros)
        return sorted(items, key=lambda pair: pair[1].casefold())

    def refresh_catalog(self, *_args):
        self.macro_editor.commit()
        self.filter_catalog("")
        self.update_preview()

    def filter_catalog(self, text):
        previous = self.catalog.currentData()
        self.catalog.clear()
        for ident, label in self.command_catalog():
            if text.casefold() in (label + " " + ident).casefold():
                self.catalog.addItem(label, ident)
        index = self.catalog.findData(previous)
        if index >= 0:
            self.catalog.setCurrentIndex(index)

    def update_preview(self):
        if not 0 <= self.current < len(self.menus):
            self.preview.actions = []
            self.preview.title = "No menu"
        else:
            menu = self.menus[self.current]
            names = self.action_names()
            self.preview.title = menu["name"]
            self.preview.actions = [(ident, names[i] or self.label(ident)) for i, ident in enumerate(menu["actions"])]
        self.preview.hovered = self.actions.currentRow()
        self.preview.update()

    def select_slice(self, row):
        if self.current >= 0 and 0 <= row < len(self.menus[self.current]["actions"]):
            self.display_name.setText(self.action_names()[row])
            self.catalog.setCurrentIndex(self.catalog.findData(self.menus[self.current]["actions"][row]))
        else:
            self.display_name.clear()
        self.update_preview()

    def edit_slice_name(self):
        row = self.actions.currentRow()
        if self.current >= 0 and row >= 0:
            self.actions.item(row).setText(self.display_name.text())
            self.update_preview()

    def assign_function(self, _index):
        row = self.actions.currentRow()
        ident = self.catalog.currentData()
        if self.current >= 0 and row >= 0 and ident is not None:
            self.menus[self.current]["actions"][row] = ident
            self.update_preview()

    def reorder_slice(self, source, target):
        if self.current < 0:
            return
        names = self.action_names()
        values = self.menus[self.current]["actions"]
        names[source], names[target] = names[target], names[source]
        values[source], values[target] = values[target], values[source]
        blocked = self.actions.blockSignals(True)
        try:
            first = self.actions.takeItem(max(source, target))
            second = self.actions.takeItem(min(source, target))
            self.actions.insertItem(min(source, target), first)
            self.actions.insertItem(max(source, target), second)
        finally:
            self.actions.blockSignals(blocked)
        self.actions.setCurrentRow(target)
        self.select_slice(target)
        self.update_preview()

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
        for ident, title in self.command_catalog():
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
        self.update_preview()

    def label(self, command):
        return next((label for ident,label in self.command_catalog() if ident==command),
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
            self.update_preview()

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
        names = self.action_names()
        row = self.actions.currentRow()
        target = row + 1 if row >= 0 else len(values)
        values.insert(target, self.catalog.currentData())
        names.insert(target, "")
        self.append_action_item(values[target])
        self.actions.insertItem(target, self.actions.takeItem(self.actions.count() - 1))
        self.actions.setCurrentRow(target)
        self.update_preview()

    def remove_action(self):
        i = self.actions.currentRow()
        if self.current >= 0 and i >= 0:
            self.action_names().pop(i)
            self.menus[self.current]["actions"].pop(i)
            self.actions.takeItem(i)
            self.update_preview()

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
            self.update_preview()

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
            self.macro_editor.commit()
            previous = self.app.settings.copy()
            self.app.settings.data["pie_menus"] = self.menus
            self.app.settings.data["macros"] = self.macro_editor.macros
            self.app.settings.save()
        except Exception as exc:
            if "previous" in locals():
                self.app.settings.data = previous
            error(self, "Save pie menus", exc)
            return
        try:
            self.app.refresh_pie_shortcuts()
        except Exception as exc:
            error(self, "Settings saved, but shortcuts could not be rebuilt", exc)
        super().accept()
