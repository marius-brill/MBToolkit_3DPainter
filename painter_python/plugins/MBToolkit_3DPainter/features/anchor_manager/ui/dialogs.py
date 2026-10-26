"""Stable-target, explicit impact dialogs. Mutations occur only after acceptance."""
from PySide6 import QtCore, QtWidgets
from ..operations import eligibility


class ReplaceDialog(QtWidgets.QDialog):
    def __init__(self, controller, slots, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Replace anchor references — impact preview")
        self.resize(850, 480)
        self.controller = controller
        self.index = controller.index
        self.slots = tuple(slots)
        self.previews = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Only checked eligible inputs change. Confirmation revalidates the current host state."))
        self.picker = QtWidgets.QComboBox()
        for anchor in sorted(self.index.anchors.values(), key=lambda a: (a.name.casefold(), a.key)):
            checks = [eligibility(self.index, slot, anchor.key) for slot in self.slots]
            eligible = any(ok for ok, _ in checks)
            self.picker.addItem(" / ".join(anchor.node.path), anchor.key)
            item = self.picker.model().item(self.picker.count() - 1)
            item.setEnabled(eligible)
            item.setToolTip("\n".join(sorted({reason for _, reason in checks})))
        layout.addWidget(self.picker)
        self.table = QtWidgets.QTreeWidget()
        self.table.setHeaderLabels(["Input / consumer", "Old source", "Proposed", "Eligibility / settings"])
        layout.addWidget(self.table, 1)
        self.summary = QtWidgets.QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                                 QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText("Confirm checked changes")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.picker.currentIndexChanged.connect(self.preview)
        enabled = next((i for i in range(self.picker.count()) if self.picker.model().item(i).isEnabled()), -1)
        self.picker.setCurrentIndex(enabled)
        self.preview()

    def preview(self):
        self.table.clear()
        target = self.picker.currentData()
        self.previews = self.controller.operations.preview(self.index, self.slots, target) if target else []
        eligible = 0
        for preview in self.previews:
            ref = preview.reference
            node = self.index.nodes[ref.slot.consumer]
            old = self.index.anchors.get(ref.anchor_key)
            item = QtWidgets.QTreeWidgetItem([" / ".join(node.path) + " → " + ref.slot.slot_id,
                                              old.name if old else "Unavailable", self.index.anchors[target].name,
                                              preview.reason])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, preview)
            if preview.eligible:
                eligible += 1
                item.setCheckState(0, QtCore.Qt.CheckState.Checked)
            else:
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.table.addTopLevelItem(item)
        self.table.resizeColumnToContents(0)
        self.summary.setText(f"{eligible} eligible / {len(self.previews) - eligible} skipped or unknown. "
                             "Channels, levels and alpha matte are preserved where readable. "
                             "Partial failures are reported; a grouped Undo is not an atomic rollback.")
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(eligible > 0)

    def selected_previews(self):
        return [self.table.topLevelItem(i).data(0, QtCore.Qt.ItemDataRole.UserRole)
                for i in range(self.table.topLevelItemCount())
                if self.table.topLevelItem(i).checkState(0) == QtCore.Qt.CheckState.Checked]


class CreateDialog(QtWidgets.QDialog):
    def __init__(self, path, sites, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create anchor — insertion preview")
        layout = QtWidgets.QFormLayout(self)
        location = QtWidgets.QLabel(path + "\nAnchor insertion respects Painter's stack constraints.")
        location.setWordWrap(True)
        layout.addRow(location)
        self.name = QtWidgets.QLineEdit("Anchor")
        self.site = QtWidgets.QComboBox()
        self.site.addItems(sites)
        layout.addRow("Name", self.name)
        layout.addRow("Insertion site", self.site)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        confirm = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        confirm.setEnabled(bool(sites))
        self.name.textChanged.connect(lambda text: confirm.setEnabled(bool(sites) and bool(text.strip())))
        if not sites:
            location.setText("Select one eligible Painter layer/effect first. No arbitrary insertion will be made.")