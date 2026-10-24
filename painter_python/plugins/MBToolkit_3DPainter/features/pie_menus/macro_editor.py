"""Draft-only macro editor. Saving never executes commands."""
import uuid
from PySide6 import QtCore, QtWidgets
from ...core.macros import OPERATIONS, MAX_STEPS, validate_macro
from ...core.models import clone_config
from ...ui.common import error


class MacroEditor(QtWidgets.QWidget):
    def __init__(self, macros, parent=None):
        super().__init__(parent)
        self.macros = clone_config(macros)
        self.current = -1
        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(9, 9, 9, 9)
        outer.setSpacing(6)
        sidebar = QtWidgets.QWidget()
        sidebar.setFixedWidth(264)
        left = QtWidgets.QVBoxLayout(sidebar)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(6)
        outer.addWidget(sidebar)
        self.list = QtWidgets.QListWidget()
        left.addWidget(self.list)
        for label, callback in (("New", self.new), ("Duplicate", self.duplicate), ("Delete", self.delete)):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            left.addWidget(button)
        right = QtWidgets.QVBoxLayout()
        outer.addLayout(right, 3)
        self.name = QtWidgets.QLineEdit()
        self.description = QtWidgets.QLineEdit()
        form = QtWidgets.QFormLayout()
        form.addRow("Macro name", self.name)
        form.addRow("Description", self.description)
        right.addLayout(form)
        right.addWidget(QtWidgets.QLabel("Steps run in order. Mask steps target the last created layer.\n"
                                         "On failure later steps stop; earlier changes may remain."))
        self.steps = QtWidgets.QListWidget()
        self.steps.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.steps.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.steps.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.steps.model().rowsMoved.connect(self.sync_steps)
        self._loading_steps = False
        right.addWidget(self.steps, 1)
        self.picker = QtWidgets.QComboBox()
        self.picker.setEditable(True)
        self.picker.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.picker.completer().setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        for ident, label in OPERATIONS.items():
            self.picker.addItem(label, ident)
        right.addWidget(self.picker)
        tools = QtWidgets.QHBoxLayout()
        right.addLayout(tools)
        for label, callback in (("Add step", self.add_step), ("Remove", self.remove_step),
                                ("↑", lambda: self.move(-1)), ("↓", lambda: self.move(1)),
                                ("Validate", self.validate)):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            tools.addWidget(button)
        self.name.editingFinished.connect(self.commit)
        self.description.editingFinished.connect(self.commit)
        self.list.currentRowChanged.connect(self.select)
        self.populate()

    def commit(self):
        if 0 <= self.current < len(self.macros):
            macro = self.macros[self.current]
            macro["name"] = self.name.text().strip()[:80] or macro["id"]
            macro["description"] = self.description.text()[:500]
            self.list.item(self.current).setText(macro["name"])

    def populate(self, index=0):
        self.current = -1
        self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems([m["name"] for m in self.macros])
        self.list.setCurrentRow(min(index, len(self.macros) - 1))
        self.list.blockSignals(False)
        self.select(self.list.currentRow())

    def select(self, index):
        self.commit()
        self.current = index
        active = 0 <= index < len(self.macros)
        self.name.setEnabled(active)
        self.description.setEnabled(active)
        self._loading_steps = True
        self.steps.clear()
        macro = self.macros[index] if active else {}
        self.name.setText(macro.get("name", ""))
        self.description.setText(macro.get("description", ""))
        for step in macro.get("steps", []):
            self.append_step(step)
        self._loading_steps = False

    def append_step(self, operation):
        item = QtWidgets.QListWidgetItem(OPERATIONS.get(operation, "Missing: " + operation))
        item.setData(QtCore.Qt.ItemDataRole.UserRole, operation)
        self.steps.addItem(item)

    def sync_steps(self, *_args):
        if not self._loading_steps and 0 <= self.current < len(self.macros):
            self.macros[self.current]["steps"] = [
                self.steps.item(i).data(QtCore.Qt.ItemDataRole.UserRole) for i in range(self.steps.count())]

    def new(self):
        self.commit()
        self.macros.append({"id": "macro_" + uuid.uuid4().hex[:10], "name": "New Macro",
                            "description": "", "steps": ["painter.add_fill"]})
        self.populate(len(self.macros) - 1)

    def duplicate(self):
        self.commit()
        if self.current < 0:
            return
        macro = clone_config(self.macros[self.current])
        macro["id"] = "macro_" + uuid.uuid4().hex[:10]
        macro["name"] += " Copy"
        self.macros.append(macro)
        self.populate(len(self.macros) - 1)

    def delete(self):
        if self.current < 0:
            return
        if QtWidgets.QMessageBox.question(self, "Delete macro", "Delete this macro? Pie references may become unavailable.") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.macros.pop(self.current)
        self.populate()

    def add_step(self):
        if self.current < 0 or self.picker.currentData() not in OPERATIONS:
            return
        steps = self.macros[self.current]["steps"]
        if len(steps) >= MAX_STEPS:
            return
        steps.append(self.picker.currentData())
        self.append_step(steps[-1])

    def remove_step(self):
        row = self.steps.currentRow()
        if self.current >= 0 and row >= 0:
            self.macros[self.current]["steps"].pop(row)
            self.steps.takeItem(row)

    def move(self, delta):
        row = self.steps.currentRow()
        if self.current < 0 or row < 0:
            return
        steps = self.macros[self.current]["steps"]
        target = row + delta
        if 0 <= target < len(steps):
            steps.insert(target, steps.pop(row))
            self.steps.insertItem(target, self.steps.takeItem(row))
            self.steps.setCurrentRow(target)

    def validate(self):
        self.commit()
        try:
            if self.current < 0:
                raise ValueError("Select a macro")
            validate_macro(self.macros[self.current])
            QtWidgets.QMessageBox.information(self, "Macro validation", "Valid structure. Runtime prerequisites are checked during execution.")
        except ValueError as exc:
            error(self, "Macro validation", exc)