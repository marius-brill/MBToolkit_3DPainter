"""Searchable textual workflow first; graph is an optional shared-state workspace."""
from PySide6 import QtCore, QtGui, QtWidgets
from ..index import search
from ..models import InputSlotKey
from ..operations import eligibility
from .dialogs import CreateDialog, ReplaceDialog
from .graph_view import GraphWorkspace


class Panel(QtWidgets.QWidget):
    def __init__(self, app, controller):
        super().__init__()
        self.app, self.controller = app, controller
        self.expanded = None
        self.rows = {}
        self.setStyleSheet("QTreeWidget, QTextBrowser {background:#20262D; color:#E9EEF3;} "
                           "QTreeWidget::item:selected {background:#24516A;} ")
        outer = QtWidgets.QVBoxLayout(self)
        tools = QtWidgets.QHBoxLayout()
        self.context_label = QtWidgets.QLabel("Texture set: —")
        self.context_label.setWordWrap(True)
        tools.addWidget(self.context_label, 1)
        self.stack_picker = QtWidgets.QComboBox()
        self.stack_picker.setToolTip("Active Painter texture set / stack")
        self.stack_picker.activated.connect(self.switch_stack)
        tools.addWidget(self.stack_picker)
        self.top_buttons = {}
        for title, callback in (("Refresh", controller.refresh), ("+ Create Anchor", self.create),
                                ("Expand Graph", self.expand)):
            button = QtWidgets.QPushButton(title)
            button.clicked.connect(callback)
            tools.addWidget(button)
            self.top_buttons[title] = button
        outer.addLayout(tools)
        self.splitter = QtWidgets.QSplitter()
        outer.addWidget(self.splitter, 1)
        library = QtWidgets.QWidget()
        left = QtWidgets.QVBoxLayout(library)
        self.query = QtWidgets.QLineEdit()
        self.query.setPlaceholderText("Search anchors, paths, consumers…")
        left.addWidget(self.query)
        filters = QtWidgets.QHBoxLayout()
        self.filter = QtWidgets.QComboBox()
        self.filter.addItems(["All", "Used", "Unused", "Issues"])
        self.sort = QtWidgets.QComboBox()
        self.sort.addItems(["Name", "Uses", "Stack Order", "Source Type"])
        filters.addWidget(self.filter)
        filters.addWidget(self.sort)
        left.addLayout(filters)
        self.scope = QtWidgets.QCheckBox("Selected Painter layer")
        self.scope.setToolTip("Restrict to the selected layer and its immediate anchor effects. Group-descendant scope is not yet implemented.")
        left.addWidget(self.scope)
        self.library = QtWidgets.QTreeWidget()
        self.library.setHeaderLabels(["Anchor / source", "Usage"])
        self.library.setRootIsDecorated(False)
        self.library.setMinimumWidth(180)
        self.library.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.library.customContextMenuRequested.connect(self.context_menu)
        self.library.itemSelectionChanged.connect(self.select_row)
        self.library.itemDoubleClicked.connect(lambda item, _: self.navigate(item.data(0, QtCore.Qt.ItemDataRole.UserRole)))
        left.addWidget(self.library, 1)
        self.splitter.addWidget(library)
        self.tabs = QtWidgets.QTabWidget()
        self.graph = GraphWorkspace(controller, self.navigate)
        self.tabs.addTab(self.graph, "Graph")
        self.issue_text = QtWidgets.QTextBrowser()
        self.tabs.addTab(self.issue_text, "Issues / coverage")
        self.splitter.addWidget(self.tabs)
        inspector = QtWidgets.QWidget()
        right = QtWidgets.QVBoxLayout(inspector)
        self.details = QtWidgets.QTextBrowser()
        right.addWidget(self.details)
        self.uses = QtWidgets.QTreeWidget()
        self.uses.setHeaderLabels(["Consumer / input", "Channel"])
        self.uses.setRootIsDecorated(False)
        self.uses.itemClicked.connect(lambda item, _: controller.select(item.data(0, QtCore.Qt.ItemDataRole.UserRole)))
        self.uses.itemDoubleClicked.connect(lambda item, _: self.navigate(item.data(0, QtCore.Qt.ItemDataRole.UserRole).consumer))
        right.addWidget(self.uses)
        self.actions = {}
        for title, callback in (("Go to source / consumer", self.go), ("Go to anchor", self.go_anchor),
                                ("Copy path / reference", self.copy_path), ("Rename", self.rename),
                                ("Replace…", self.replace), ("Replace All Uses…", self.replace_all),
                                ("Disconnect…", lambda: None), ("Delete Anchor…", self.delete)):
            button = QtWidgets.QPushButton(title)
            button.clicked.connect(callback)
            right.addWidget(button)
            self.actions[title] = button
        self.actions["Disconnect…"].setToolTip(controller.adapter.capabilities["disconnect"].reason)
        self.splitter.addWidget(inspector)
        self.splitter.setSizes([280, 560, 300])
        bottom = QtWidgets.QHBoxLayout()
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        bottom.addWidget(self.status, 1)
        self.auto = QtWidgets.QCheckBox("Auto refresh")
        cfg = app.settings.data["anchor_manager"]
        self.auto.setChecked(cfg["auto_refresh"])
        self.auto.toggled.connect(self.set_auto)
        bottom.addWidget(self.auto)
        copy = QtWidgets.QPushButton("Copy diagnostic")
        copy.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(controller.diagnostic()))
        bottom.addWidget(copy)
        outer.addLayout(bottom)
        self.search_timer = QtCore.QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(160)
        self.search_timer.timeout.connect(self.populate)
        self.query.textChanged.connect(lambda: self.search_timer.start())
        self.filter.currentTextChanged.connect(self.populate)
        self.sort.currentTextChanged.connect(self.populate)
        self.scope.toggled.connect(self.populate)
        self.filter.setCurrentText(cfg["filter"])
        self.sort.setCurrentText(cfg["sort"])
        self.graph.mode.setCurrentText(cfg["graph_mode"])
        self.graph.view.zoom(cfg["zoom"])
        if cfg["splitter"]:
            self.splitter.setSizes(cfg["splitter"])
        controller.changed.connect(self.populate)
        controller.selection_changed.connect(self.inspect)
        controller.state_changed.connect(self.update_status)
        for key, callback in ((QtCore.Qt.Key.Key_F2, self.rename), (QtCore.Qt.Key.Key_Delete, self.delete)):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
        self.populate()

    def set_auto(self, enabled):
        self.app.settings.data["anchor_manager"]["auto_refresh"] = enabled

    def populate(self, *_):
        index = self.controller.index
        scope = None
        if self.scope.isChecked():
            try:
                scope = self.controller.adapter.selected_key()
            except Exception:
                scope = None
            if scope is None:
                self.library.clear()
                self.inspect()
                return
        self.library.blockSignals(True)
        self.library.clear()
        self.rows = {}
        for anchor in search(index, self.query.text(), self.filter.currentText(), self.sort.currentText(), scope):
            row = QtWidgets.QTreeWidgetItem([anchor.name + " · " + anchor.node.domain, anchor.usage_label])
            row.setData(0, QtCore.Qt.ItemDataRole.UserRole, anchor.key)
            row.setToolTip(0, " / ".join(anchor.node.path))
            row.setToolTip(1, anchor.usage_label)
            self.library.addTopLevelItem(row)
            self.rows[anchor.key] = row
        self.library.resizeColumnToContents(0)
        self.library.blockSignals(False)
        self.context_label.setText("Texture set / stack: " + " / ".join(self.controller.context[1:])
                                   if self.controller.context else "Texture set: —")
        self.stack_picker.blockSignals(True)
        self.stack_picker.clear()
        try:
            for material, stack in self.controller.adapter.stack_choices():
                self.stack_picker.addItem(material + (" / " + stack if stack else ""), (material, stack))
                if self.controller.context and (material, stack) == self.controller.context[1:]:
                    self.stack_picker.setCurrentIndex(self.stack_picker.count() - 1)
        except Exception as exc:
            self.stack_picker.setToolTip(str(exc))
        self.stack_picker.blockSignals(False)
        import html
        lines = [f"{i.severity.upper()} · {i.code} · {i.confidence}: {i.evidence}" for i in index.issues]
        self.issue_text.setPlainText("Coverage: " + index.coverage.value + "\n\n" + "\n\n".join(lines))
        self.issue_text.setToolTip(html.escape("No ordering hazard is asserted without authoritative evidence."))
        self.inspect()
        self.update_status()

    def select_row(self):
        selected = self.library.selectedItems()
        if selected:
            self.controller.select(selected[0].data(0, QtCore.Qt.ItemDataRole.UserRole))

    def inspect(self):
        index, selected = self.controller.index, self.controller.selection
        self.uses.clear()
        for button in self.actions.values():
            button.setEnabled(False)
        row = self.rows.get(selected)
        self.library.blockSignals(True)
        self.library.clearSelection()
        if row:
            row.setSelected(True)
        self.library.blockSignals(False)
        self.actions["Disconnect…"].setEnabled(False)
        if selected in index.anchors:
            anchor = index.anchors[selected]
            warnings = [i.evidence for i in index.issues if i.node in (None, selected)]
            self.details.setPlainText(f"{anchor.name}\n\nOutput preview unavailable\n\n"
                                      + " / ".join(anchor.node.path) + f"\n\n{anchor.usage_label}\n\n"
                                      + "\n".join(warnings))
            for slot in index.uses.get(selected, []):
                consumer = index.nodes[slot.consumer]
                item = QtWidgets.QTreeWidgetItem([consumer.name + " → " + slot.slot_id +
                                                  (" / " + "/".join(slot.source_path) if slot.source_path else ""), slot.channel])
                item.setData(0, QtCore.Qt.ItemDataRole.UserRole, slot)
                item.setToolTip(0, " / ".join(consumer.path))
                self.uses.addTopLevelItem(item)
            self.actions["Rename"].setEnabled(True)
            self.actions["Delete Anchor…"].setEnabled(index.is_unused(selected))
            self.actions["Delete Anchor…"].setToolTip("Only confirmed unused anchors in a complete scan can be deleted; otherwise replace references in Painter first.")
            self.actions["Replace All Uses…"].setEnabled(any(
                eligibility(index, slot, target)[0] for slot in index.uses.get(selected, []) for target in index.anchors))
        elif isinstance(selected, InputSlotKey) and selected in index.references:
            ref = index.references[selected]
            consumer = index.nodes[selected.consumer]
            anchor = index.anchors.get(ref.anchor_key)
            self.details.setPlainText(f"{consumer.name}\n{' / '.join(consumer.path)}\n\n"
                                      f"Input: {selected.slot_id} / {' / '.join(selected.source_path)}\n"
                                      f"Mode: {selected.source_mode}\nTarget channel: {selected.channel}\n"
                                      f"Anchor: {anchor.name if anchor else 'Unavailable'}\n"
                                      f"Source channel: {ref.source_channel}\nMapping: {ref.channel_mapping}\n"
                                      f"{ref.status.value}: {ref.reason}")
            self.actions["Go to anchor"].setEnabled(anchor is not None)
            self.actions["Replace…"].setEnabled(any(eligibility(index, selected, target)[0] for target in index.anchors))
        elif selected in index.nodes:
            node = index.nodes[selected]
            self.details.setPlainText(node.name + "\n" + " / ".join(node.path) + "\n" + node.kind)
        else:
            self.details.setPlainText("Select an anchor or input reference.\n\n"
                                      "Usage totals are lower bounds when scan coverage is partial. "
                                      "No graph-only action is required for browsing references.")
        exists = selected in index.nodes or selected in index.references
        self.actions["Go to source / consumer"].setEnabled(exists)
        self.actions["Copy path / reference"].setEnabled(exists)
        for title in ("Replace…", "Replace All Uses…"):
            self.actions[title].setToolTip("Only proven same-chain candidates are editable. Other references remain navigable in Painter.")
        try:
            editable = self.controller.adapter.can_write() and self.controller.iterator is None
        except Exception:
            editable = False
        self.top_buttons["+ Create Anchor"].setEnabled(editable)
        for title, capability in (("Rename", "rename"), ("Delete Anchor…", "delete")):
            button = self.actions[title]
            supported = self.controller.adapter.capabilities[capability].state.value == "SUPPORTED"
            button.setEnabled(button.isEnabled() and editable and supported)
        for title in ("Replace…", "Replace All Uses…"):
            self.actions[title].setEnabled(self.actions[title].isEnabled() and editable)

    def update_status(self):
        c = self.controller
        self.status.setText(f"{c.state}\n{len(c.index.anchors)} anchors · {len(c.index.references)} known input edges · "
                            f"{c.index.scanned_nodes} scanned nodes · {len(c.index.issues)} issues"
                            + ("\n" + c.error if c.error else ""))

    def _run(self, callback):
        try:
            result = callback()
            if result and (result.failed or result.skipped):
                QtWidgets.QMessageBox.warning(self, "Operation report",
                    f"{result.completed} completed\n" + "\n".join(result.skipped + result.failed))
            return result
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Anchor Manager", str(exc))
            self.controller.request_refresh()

    def navigate(self, key):
        self._run(lambda: self.controller.navigate(key))

    def switch_stack(self, _index):
        choice = self.stack_picker.currentData()
        if choice:
            def action():
                self.controller.adapter.activate_stack(*choice)
                self.controller.refresh()
            self._run(action)

    def go(self):
        selected = self.controller.selection
        self.navigate(selected.consumer if isinstance(selected, InputSlotKey) else selected)

    def go_anchor(self):
        ref = self.controller.index.references.get(self.controller.selection)
        if ref and ref.anchor_key:
            self.navigate(ref.anchor_key)

    def copy_path(self):
        QtWidgets.QApplication.clipboard().setText(self.details.toPlainText())

    def rename(self):
        index, key = self.controller.index, self.controller.selection
        if key not in index.anchors:
            return
        name, accepted = QtWidgets.QInputDialog.getText(self, "Rename anchor", "New label", text=index.anchors[key].name)
        if not accepted:
            return
        if any(a.name.casefold() == name.strip().casefold() and a.key != key for a in index.anchors.values()):
            if QtWidgets.QMessageBox.question(self, "Duplicate label", "Another anchor has this name. Continue?") != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self._run(lambda: self.controller.apply(lambda: self.controller.operations.rename(index, key, name)))

    def create(self):
        def action():
            key = self.controller.adapter.selected_key()
            index = self.controller.index
            sites = self.controller.adapter.insertion_sites(key) if key else []
            node = index.nodes.get(key)
            if node is None:
                sites = []
            dialog = CreateDialog(" / ".join(node.path) if node else "Current Painter selection", sites, self)
            if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                return self.controller.apply(lambda: self.controller.operations.create(index, key, dialog.site.currentText(), dialog.name.text()))
        self._run(action)

    def _replace(self, slots):
        if not slots:
            return
        dialog = ReplaceDialog(self.controller, slots, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._run(lambda: self.controller.apply(lambda: self.controller.operations.replace(dialog.index, dialog.selected_previews())))

    def replace(self):
        selected = self.controller.selection
        if selected in self.controller.index.references:
            self._replace([selected])

    def replace_all(self):
        self._replace(tuple(self.controller.index.uses.get(self.controller.selection, [])))

    def delete(self):
        index, key = self.controller.index, self.controller.selection
        if key not in index.anchors:
            return
        if not index.is_unused(key):
            QtWidgets.QMessageBox.information(self, "Deletion blocked", "Known uses exist or coverage is incomplete. Replace references first; incomplete scans cannot establish unused anchors.")
            return
        anchor = index.anchors[key]
        if QtWidgets.QMessageBox.warning(self, "Delete unused anchor?",
                f"Delete {anchor.name}?\n{' / '.join(anchor.node.path)}\n"
                "0 uses in completely scanned public categories. Cancel to keep it. Use Painter Undo after deletion.",
                QtWidgets.QMessageBox.StandardButton.Ok | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel) == QtWidgets.QMessageBox.StandardButton.Ok:
            self._run(lambda: self.controller.apply(lambda: self.controller.operations.delete(index, key)))

    def context_menu(self, point):
        menu = QtWidgets.QMenu(self)
        for title in ("Go to source / consumer", "Copy path / reference", "Rename", "Replace All Uses…", "Delete Anchor…"):
            button = self.actions[title]
            action = menu.addAction(title)
            action.setEnabled(button.isEnabled())
            action.triggered.connect(button.click)
        focus = menu.addAction("Focus / Find Uses")
        focus.triggered.connect(lambda: self.graph.mode.setCurrentText("Focus"))
        menu.exec(self.library.viewport().mapToGlobal(point))

    def expand(self):
        if self.expanded is None:
            self.expanded = QtWidgets.QDialog(self)
            self.expanded.setWindowTitle("MBToolkit · Anchor Graph")
            self.expanded.resize(1100, 750)
            geometry = self.app.settings.data["anchor_manager"]["expanded_geometry"]
            if geometry:
                self.expanded.restoreGeometry(QtCore.QByteArray.fromHex(geometry.encode("ascii")))
            layout = QtWidgets.QVBoxLayout(self.expanded)
            layout.addWidget(GraphWorkspace(self.controller, self.navigate))
            self.expanded.finished.connect(self.expanded_closed)
        self.expanded.show()
        self.expanded.raise_()

    def expanded_closed(self, *_):
        if self.expanded:
            self.app.settings.data["anchor_manager"]["expanded_geometry"] = bytes(self.expanded.saveGeometry().toHex()).decode("ascii")
        self.controller.set_visible(self.isVisible())

    def showEvent(self, event):
        super().showEvent(event)
        self.controller.set_visible(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.controller.set_visible(bool(self.expanded and self.expanded.isVisible()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Narrow docks use vertical sections, with graph still available as a tab.
        self.splitter.setOrientation(QtCore.Qt.Orientation.Vertical if self.width() < 750 else QtCore.Qt.Orientation.Horizontal)

    def dispose(self):
        self.search_timer.stop()
        if self.expanded:
            self.expanded.close()
            self.expanded.deleteLater()
            self.expanded = None
        cfg = self.app.settings.data["anchor_manager"]
        cfg.update(filter=self.filter.currentText(), sort=self.sort.currentText(),
                   splitter=self.splitter.sizes(), graph_mode=self.graph.mode.currentText(),
                   zoom=self.graph.view.transform().m11())
        self.controller.dispose()
        self.app.settings.save()