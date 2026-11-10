"""Guarded Qt integration. Never replace Painter's model or edit layer data."""
from PySide6 import QtCore, QtWidgets


def row_owner(widget):
    """Find the containing native row without confusing nested folder labels."""
    parent = widget.parentWidget()
    while parent is not None:
        if parent.metaObject().className() == "Alg::ListWidget":
            return parent
        parent = parent.parentWidget()
    return None


class WidgetFilter:
    """Painter's native LayersStackView uses nested widgets, not a Qt model."""
    def __init__(self, view):
        self.view = view
        self.model = None
        self.saved = {}
        self.index = None

    def invalidate(self):
        self.index = None

    def build_index(self):
        """Visit each widget once; never rescan a folder's entire subtree per row."""
        records = {}
        pending = [(self.view, None, False)]
        while pending:
            widget, owner, in_label = pending.pop()
            kind = widget.metaObject().className()
            if kind == "Alg::ListWidget":
                records[widget] = [owner, [], None, False]
                owner, in_label = widget, False
            elif kind == "Alg::EditLabel":
                in_label = True
            if owner is not None:
                if kind == "Alg::LayerView":
                    records[owner][3] = True
                if in_label and isinstance(widget, QtWidgets.QLabel):
                    records[owner][1].append(widget)
                if isinstance(widget, QtWidgets.QToolButton) and widget.objectName() == "wrappedWidget_collapsableButton":
                    records[owner][2] = widget
            pending.extend((child, owner, in_label) for child in reversed(widget.children())
                           if isinstance(child, QtWidgets.QWidget))
        self.index = records
        return records

    def rows(self):
        return [row for row in self.view.findChildren(QtWidgets.QWidget)
                if row.metaObject().className() == "Alg::ListWidget"]

    @staticmethod
    def label(row):
        for label in row.findChildren(QtWidgets.QWidget):
            if label.metaObject().className() == "Alg::EditLabel" and row_owner(label) is row:
                return " ".join(child.text() for child in label.findChildren(QtWidgets.QLabel)).casefold()
        return ""

    @staticmethod
    def expander(row):
        for button in row.findChildren(QtWidgets.QToolButton):
            if button.objectName() == "wrappedWidget_collapsableButton" and row_owner(button) is row:
                return button
        return None

    def restore(self):
        # Restore disclosure controls first, then explicit row visibility.
        for row, (hidden, button, checked) in list(self.saved.items()):
            try:
                if button is not None and button.isChecked() != checked:
                    button.click()
            except RuntimeError:
                pass
        for row, (hidden, button, checked) in list(self.saved.items()):
            try:
                row.setVisible(not hidden)
            except RuntimeError:
                pass
        self.saved.clear()
        self.invalidate()

    def apply(self, text):
        query = text.strip().casefold()
        if not query:
            self.restore()
            return
        records = self.index if self.index is not None else self.build_index()
        rows = list(records)
        self.saved = {row: state for row, state in self.saved.items() if row in records}
        # Forward inheritance comes only from an actual match, never an ancestor
        # retained for context. Reverse propagation then adds just the parent chain.
        included = set()
        for row, (parent, labels, button, searchable) in records.items():
            if parent in included or (searchable and query in " ".join(label.text() for label in labels).casefold()):
                included.add(row)
        visible = set(included)
        expand = set()
        for row in reversed(rows):
            parent = records[row][0]
            if row in visible and parent in records:
                visible.add(parent)
                expand.add(parent)
        # Capture all state before expanding a folder changes its children's state.
        for row in rows:
            if row not in self.saved:
                button = records[row][2]
                self.saved[row] = (row.isHidden(), button, button.isChecked() if button else None)
        updates = self.view.updatesEnabled()
        self.view.setUpdatesEnabled(False)
        try:
            # Expanding may show every sibling. Finish all expansion BEFORE
            # enforcing visibility, otherwise later expansion can undo filtering.
            for row in rows:
                button = records[row][2]
                if row in expand and button is not None and not button.isHidden() and not button.isChecked():
                    button.click()
            for row in rows:
                show = row in visible
                if row.isHidden() == show:
                    row.setVisible(show)
        finally:
            self.view.setUpdatesEnabled(updates)


class TreeFilter:
    """Hide rows in a view, retaining ancestors and matching-folder contents."""
    def __init__(self, view):
        self.view = view
        self.model = view.model()
        self.saved = {}

    def restore(self):
        if self.view.model() is not self.model:
            self.saved.clear()
            return
        for index, (hidden, expanded) in self.saved.items():
            if index.isValid():
                self.view.setRowHidden(index.row(), index.parent(), hidden)
                self.view.setExpanded(QtCore.QModelIndex(index), expanded)
        self.saved.clear()

    def apply(self, text):
        query = text.strip().casefold()
        if not query:
            self.restore()
            return
        if self.view.model() is not self.model:
            return
        # Do not retain invalidated rows after a model reset or removal.
        self.saved = {key: state for key, state in self.saved.items() if key.isValid()}

        def visit(parent, inherited=False):
            any_visible = False
            for row in range(self.model.rowCount(parent)):
                index = self.model.index(row, 0, parent)
                key = QtCore.QPersistentModelIndex(index)
                if key not in self.saved:
                    self.saved[key] = (self.view.isRowHidden(row, parent), self.view.isExpanded(index))
                label = index.data(QtCore.Qt.ItemDataRole.DisplayRole)
                match = query in str(label or "").casefold()
                children = visit(index, inherited or match)
                visible = inherited or match or children
                self.view.setRowHidden(row, parent, self.saved[key][0] or not visible)
                if children and visible:
                    self.view.setExpanded(index, True)
                any_visible = any_visible or (visible and not self.saved[key][0])
            return any_visible

        self.view.setUpdatesEnabled(False)
        try:
            visit(self.view.rootIndex())
        finally:
            self.view.setUpdatesEnabled(True)


class LayerSearch(QtCore.QObject):
    """Attach only to an unambiguous native Layers dock with a Qt tree."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.dock = None
        self.view = None
        self.field = None
        self.filter = None
        self.connections = []
        self.status = "Waiting for a compatible native Layers panel"
        self.poll = QtCore.QTimer(self)
        self.poll.setInterval(1000)
        self.poll.timeout.connect(self.discover)
        self.refresh = QtCore.QTimer(self)
        self.refresh.setSingleShot(True)
        self.refresh.setInterval(0)
        self.refresh.timeout.connect(self.apply)

    def start(self):
        self.discover()
        self.poll.start()

    def discover(self):
        try:
            if self.view is not None:
                if isinstance(self.filter, WidgetFilter):
                    self.view.objectName()  # Check that Painter has not destroyed it.
                    self.filter.invalidate()
                    if self.field.text().strip():
                        self.apply()
                    return
                if self.view.model() is self.filter.model:
                    return
        except RuntimeError:
            pass
        self.detach()
        candidates = []
        for dock in self.window.findChildren(QtWidgets.QDockWidget):
            name = dock.objectName().casefold()
            title = dock.windowTitle().replace("&", "").strip().casefold()
            if name.startswith("mbtoolkit"):
                continue
            # No fuzzy title matching: e.g. Layer Graph must never be targeted.
            if title != "layers" and name not in {"layers", "layersdock", "layerstack", "layerstackdock", "layersstackview"}:
                continue
            content = dock.widget()
            if content is None or not isinstance(QtWidgets.QWidget.layout(content), QtWidgets.QVBoxLayout):
                continue
            if content.metaObject().className() == "Alg::LayersStackView":
                lists = [widget for widget in content.findChildren(QtWidgets.QWidget)
                         if widget.metaObject().className() == "Alg::ListView" and row_owner(widget) is None]
                if len(lists) == 1:
                    candidates.append((dock, content, lists[0]))
                continue
            trees = content.findChildren(QtWidgets.QTreeView)
            if len(trees) == 1 and trees[0].model() is not None:
                candidates.append((dock, content, trees[0]))
        if len(candidates) != 1:
            self.status = "Native Layers layout unsupported or ambiguous; no UI changed"
            return
        self.dock, content, self.view = candidates[0]
        self.filter = (WidgetFilter(self.view) if content.metaObject().className() == "Alg::LayersStackView"
                       else TreeFilter(self.view))
        self.field = QtWidgets.QLineEdit(content)
        self.field.setObjectName("MBToolkit_LayerSearch")
        self.field.setPlaceholderText("Search layers and folders…")
        self.field.setClearButtonEnabled(True)
        self.field.setMaximumHeight(24)
        self.field.setToolTip("Filter layer and folder names, not effects. Matches include their children. "
                              "This does not change layer visibility or rendering.")
        QtWidgets.QWidget.layout(content).insertWidget(0, self.field)
        self.field.textChanged.connect(self.apply)
        self.field.show()
        if isinstance(self.filter, TreeFilter):
            model = self.filter.model
            for name in ("dataChanged", "rowsInserted", "rowsRemoved", "rowsMoved", "modelReset", "layoutChanged"):
                signal = getattr(model, name)
                signal.connect(self.schedule)
                self.connections.append((signal, self.schedule))
        self.status = "Attached to native Layers " + ("widget list" if isinstance(self.filter, WidgetFilter) else "tree")

    def schedule(self, *_):
        self.refresh.start()

    def apply(self, *_):
        try:
            if self.field is not None:
                self.filter.apply(self.field.text())
        except RuntimeError:
            # Painter may destroy/rebuild its tree on a workspace change.
            self.detach()

    def detach(self):
        self.refresh.stop()
        for signal, slot in self.connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self.connections.clear()
        if self.filter is not None:
            try:
                self.filter.restore()
            except RuntimeError:
                pass
        if self.field is not None:
            try:
                self.field.hide()
                self.field.deleteLater()
            except RuntimeError:
                pass
        self.dock = self.view = self.field = self.filter = None

    def stop(self):
        self.poll.stop()
        self.detach()