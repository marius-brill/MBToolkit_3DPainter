"""Inline creation popup, scope tabs and disposable refresh lifecycle."""
from PySide6 import QtCore, QtWidgets
from .canvas import View
from .model import Layout, Snapshot, TYPES, ROOT, search, REORDER_REASON


class Browser(QtWidgets.QDialog):
    dismissed = QtCore.Signal()

    def __init__(self, panel, scope, selected):
        super().__init__(panel, QtCore.Qt.WindowType.Popup | QtCore.Qt.WindowType.FramelessWindowHint)
        self.panel, self.scope, self.selected = panel, scope, selected
        self.chosen = None
        self.resource = None
        self.resource_type = None
        self.resources = []
        self.setWindowTitle("Add Node")
        self.resize(430, 340)
        outer = QtWidgets.QVBoxLayout(self)
        self.query = QtWidgets.QLineEdit()
        self.query.setPlaceholderText("Search nodes… folder, black mask, generator, levels")
        outer.addWidget(self.query)
        self.list = QtWidgets.QListWidget()
        outer.addWidget(self.list)
        self.reason = QtWidgets.QLabel()
        self.reason.setWordWrap(True)
        outer.addWidget(self.reason)
        self.query.textChanged.connect(self.populate)
        self.query.returnPressed.connect(self.choose)
        self.list.itemClicked.connect(lambda _item: self.choose())
        self.list.itemActivated.connect(lambda _item: self.choose())
        self.query.installEventFilter(self)
        self.populate()
        self.query.setFocus()

    def populate(self):
        self.list.clear()
        self.reason.hide()
        if self.resource_type:
            for index, resource in enumerate(self.resources):
                if self.query.text().casefold() in resource.gui_name().casefold():
                    row = QtWidgets.QListWidgetItem(resource.gui_name())
                    row.setData(QtCore.Qt.ItemDataRole.UserRole, index)
                    self.list.addItem(row)
            if self.list.count():
                self.list.setCurrentRow(0)
            else:
                self.reason.setText("No matching resources")
                self.reason.show()
            return
        for item in search(self.query.text()):
            reason = self.panel.adapter.reason(item, self.panel.snapshot, self.scope, self.selected)
            if reason:
                continue
            row = QtWidgets.QListWidgetItem(item.name)
            row.setData(QtCore.Qt.ItemDataRole.UserRole, item.id)
            row.setToolTip(reason or ("Choose a resource before insertion" if item.resource else "Add " + item.name))
            self.list.addItem(row)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.reason.setText("No matching nodes available here")
            self.reason.show()

    def eventFilter(self, watched, event):
        if self.isVisible():
            if event.type() == QtCore.QEvent.Type.MouseButtonPress:
                if not self.frameGeometry().contains(event.globalPosition().toPoint()):
                    self.reject()
                    return True
            elif event.type() == QtCore.QEvent.Type.ApplicationDeactivate:
                self.reject()
            elif watched is self and event.type() == QtCore.QEvent.Type.WindowDeactivate:
                self.reject()
        if watched is self.query and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() in (QtCore.Qt.Key.Key_Down, QtCore.Qt.Key.Key_Up):
                delta = 1 if event.key() == QtCore.Qt.Key.Key_Down else -1
                self.list.setCurrentRow(max(0, min(self.list.count() - 1, self.list.currentRow() + delta)))
                return True
            if event.key() == QtCore.Qt.Key.Key_Backspace and not self.query.text() and self.resource_type:
                self.resource_type = None
                self.query.setPlaceholderText("Search nodes…")
                self.populate()
                return True
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        super().showEvent(event)
        QtWidgets.QApplication.instance().installEventFilter(self)

    def hideEvent(self, event):
        QtWidgets.QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)
        self.dismissed.emit()

    def mousePressEvent(self, event):
        if not self.rect().contains(event.position().toPoint()):
            self.reject()
            event.accept()
            return
        super().mousePressEvent(event)

    def choose(self):
        row = self.list.currentItem()
        if row:
            if self.resource_type:
                self.chosen = self.resource_type
                self.resource = self.resources[row.data(QtCore.Qt.ItemDataRole.UserRole)].identifier()
                self.accept()
                return
            item = TYPES[row.data(QtCore.Qt.ItemDataRole.UserRole)]
            if not self.panel.adapter.reason(item, self.panel.snapshot, self.scope, self.selected):
                if item.resource:
                    try:
                        self.resources = self.panel.adapter.resources(item.resource)
                    except Exception as exc:
                        self.reason.setText("Cannot list resources: " + str(exc))
                        self.reason.show()
                        return
                    self.resource_type = item
                    self.query.setPlaceholderText("Search " + item.name + " resources… (Backspace to return)")
                    self.query.clear()
                    self.populate()
                    self.query.setFocus()
                    return
                self.chosen = item
                self.accept()


class ResourcePicker(QtWidgets.QDialog):
    def __init__(self, resources, parent):
        super().__init__(parent)
        self.resources, self.chosen = resources, None
        self.setWindowTitle("Choose Resource")
        self.resize(480, 500)
        outer = QtWidgets.QVBoxLayout(self)
        self.query = QtWidgets.QLineEdit()
        self.query.setPlaceholderText("Search resource names…")
        outer.addWidget(self.query)
        self.list = QtWidgets.QListWidget()
        outer.addWidget(self.list)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.choose)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.query.textChanged.connect(self.populate)
        self.list.itemDoubleClicked.connect(lambda _row: self.choose())
        self.populate()

    def populate(self):
        self.list.clear()
        query = self.query.text().casefold()
        for index, resource in enumerate(self.resources):
            if query in resource.gui_name().casefold():
                row = QtWidgets.QListWidgetItem(resource.gui_name())
                row.setData(QtCore.Qt.ItemDataRole.UserRole, index)
                row.setToolTip(resource.identifier().url())
                self.list.addItem(row)
        if self.list.count():
            self.list.setCurrentRow(0)

    def choose(self):
        row = self.list.currentItem()
        if row:
            self.chosen = self.resources[row.data(QtCore.Qt.ItemDataRole.UserRole)].identifier()
            self.accept()


class Notice(QtWidgets.QLabel):
    """Transient canvas overlay; never reserves graph layout space."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: #293746; color: #E9EEF3; padding: 10px; border-radius: 4px;")
        self.timeout = QtCore.QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.hide)
        self.hide()

    def setText(self, text):
        super().setText(text)
        self.setFixedWidth(max(180, min(650, self.parentWidget().width() - 32)))
        self.adjustSize()
        self.move(16, 16)
        self.show()
        self.raise_()
        self.timeout.start(6500)


class Panel(QtWidgets.QWidget):
    def __init__(self, app, adapter):
        super().__init__()
        self.app, self.adapter = app, adapter
        self.snapshot, self.layout = Snapshot(), Layout()
        self.disposed = False
        self.native_reorder = None
        self.native_reorder_busy = False
        self.refreshing = False
        self.inspected = None
        self.modal_depth = 0
        self.pending_refresh = False
        self.resize(1200, 760)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        outer.addWidget(self.tabs)
        self.status = Notice(self)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.refresh)
        self.poll = QtCore.QTimer(self)
        self.poll.setInterval(1000)
        self.poll.timeout.connect(self.check_context)
        self.app.events.add(self.request_refresh)
        self.open_scope(ROOT)

    def view(self):
        return self.tabs.currentWidget()

    def open_scope(self, scope):
        if scope != ROOT and not self.snapshot.valid_scope(scope):
            return
        for index in range(self.tabs.count()):
            if self.tabs.widget(index).scope == scope:
                self.tabs.setCurrentIndex(index)
                return
        view = View(self, scope)
        self.tabs.addTab(view, self.snapshot.title(scope))
        self.tabs.setCurrentWidget(view)
        view.rebuild()
        view.fit()

    def close_tab(self, index):
        if self.tabs.widget(index).scope != ROOT:
            widget = self.tabs.widget(index)
            self.tabs.removeTab(index)
            widget.deleteLater()

    def tab_changed(self, _index):
        view = self.view()
        if view is None:
            return
        scope, path = view.scope, []
        while scope != ROOT:
            node = self.snapshot.nodes.get(scope[0])
            if node is None:
                break
            path.append(node.name + " / " + scope[1].title())
            scope = node.scope
        self.tabs.setTabToolTip(self.tabs.currentIndex(), "Texture Set" + (" > " + " > ".join(reversed(path)) if path else ""))
        view.selection_changed()

    def request_refresh(self):
        if self.disposed:
            return
        self.pending_refresh = True
        if self.isVisible() and not self.modal_depth:
            self.timer.start()

    def check_context(self):
        if self.disposed or self.modal_depth:
            return
        try:
            if self.adapter.context() != self.snapshot.context:
                # A stale drag must not indefinitely defer project/stack invalidation.
                for index in range(self.tabs.count()):
                    view = self.tabs.widget(index)
                    view.cancel_connection()
                    view.cancel_layout_drag()
                self.refresh()
        except Exception as exc:
            self.status.setText("Context check failed: " + str(exc))

    def refresh(self):
        if self.disposed or self.refreshing:
            return
        if self.native_reorder_busy:
            self.pending_refresh = True
            return
        if any(self.tabs.widget(i).connection_drag is not None or self.tabs.widget(i).layout_drag
               for i in range(self.tabs.count())):
            self.pending_refresh = True
            return
        if self.modal_depth:
            self.pending_refresh = True
            return
        self.timer.stop()
        self.refreshing = True
        self.pending_refresh = False
        try:
            snapshot = self.adapter.scan()
            changed = snapshot.context != self.snapshot.context
            self.snapshot = snapshot
            if changed:
                self.layout = Layout()
                for index in reversed(range(self.tabs.count())):
                    self.close_tab(index)
            self.layout.prune(snapshot)
            for index in reversed(range(self.tabs.count())):
                view = self.tabs.widget(index)
                if not snapshot.valid_scope(view.scope):
                    self.close_tab(index)
                else:
                    self.tabs.setTabText(index, snapshot.title(view.scope))
                    view.rebuild()
            if not snapshot.context:
                self.status.setText("Open an editable Painter project.")
            if changed:
                self.view().fit()
            self.tab_changed(self.tabs.currentIndex())
        except Exception as exc:
            # Do not leave actionable stale cards after an unreadable hierarchy.
            self.snapshot = Snapshot()
            for index in reversed(range(self.tabs.count())):
                self.close_tab(index)
            self.view().rebuild()
            self.inspect(None)
            self.status.setText("Layer Graph refresh failed; editing disabled. Retry Refresh. " + str(exc))
        finally:
            self.refreshing = False

    def mutate(self, callback):
        try:
            result = callback()
        except Exception as exc:
            self.refresh()
            self.status.setText("Operation failed: " + str(exc))
            return None
        self.refresh()
        return result

    def arrange(self, view):
        if self.disposed or self.refreshing or self.modal_depth or view.connection_drag is not None or view.layout_drag:
            return
        if self.snapshot.context is None or not self.snapshot.valid_scope(view.scope):
            return
        self.layout.arrange(view.scope)
        view.rebuild()
        self.status.setText("Arranged this graph by evaluation order. Painter layers and material are unchanged.")

    def exec_dialog(self, dialog):
        self.modal_depth += 1
        try:
            if isinstance(dialog, Browser):
                # QDialog.exec() makes even a Popup modal on some embedded hosts,
                # preventing outside widgets from receiving click-away events.
                loop = QtCore.QEventLoop(self)
                dialog.finished.connect(loop.quit)
                dialog.dismissed.connect(loop.quit)
                dialog.setWindowModality(QtCore.Qt.WindowModality.NonModal)
                dialog.show()
                if dialog.isVisible():
                    loop.exec()
                loop.deleteLater()
                return dialog.result()
            return dialog.exec()
        finally:
            self.modal_depth -= 1
            dialog.deleteLater()
            if self.pending_refresh:
                self.request_refresh()

    def input_text(self, title, label, text):
        dialog = QtWidgets.QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setTextValue(text)
        accepted = self.exec_dialog(dialog) == QtWidgets.QDialog.DialogCode.Accepted
        return dialog.textValue(), accepted

    def add(self):
        view = self.view()
        ids = view.selected_ids()
        self.browser(view, view.mapToScene(view.viewport().rect().center()), ids[0] if len(ids) == 1 else None)

    def browser(self, view, position, selected=None, scope_override=None):
        # Capture immutable context/scope before any modal can outlive its target.
        if selected not in self.snapshot.nodes:
            selected = None
        context, scope = self.snapshot.context, scope_override or view.scope
        if scope_override is None and selected in self.snapshot.nodes:
            scope = self.snapshot.nodes[selected].scope
        dialog = Browser(self, scope, selected)
        anchor = view.viewport().mapToGlobal(view.mapFromScene(position))
        screen = self.screen().availableGeometry()
        dialog.move(max(screen.left(), min(anchor.x(), screen.right() - dialog.width())),
                    max(screen.top(), min(anchor.y(), screen.bottom() - dialog.height())))
        if self.exec_dialog(dialog) != QtWidgets.QDialog.DialogCode.Accepted:
            return
        item = dialog.chosen
        if item.id == "frame":
            self.frame(view)
            return
        resource = dialog.resource
        uid = self.mutate(lambda: self.adapter.create(item, context, scope, selected, resource))
        if uid and item.category == "Masks":
            self.open_scope((uid, "mask"))
        elif uid and uid in self.snapshot.nodes:
            self.layout.positions[(scope, uid)] = (position.x(), position.y())
            view.rebuild()
            if uid in view.cards:
                view.scene().clearSelection()
                view.cards[uid].setSelected(True)

    def toggle(self, uid):
        if uid not in self.snapshot.nodes:
            return
        ancestors = set()
        owner = self.snapshot.nodes[uid].scope[0]
        while owner in self.snapshot.nodes and owner not in ancestors:
            ancestors.add(owner)
            owner = self.snapshot.nodes[owner].scope[0]
        if uid in self.layout.expanded:
            self.layout.expanded.intersection_update(ancestors)
        else:
            self.layout.expanded.intersection_update(ancestors)
            self.layout.expanded.update(ancestors | {uid})
        for index in range(self.tabs.count()):
            self.tabs.widget(index).rebuild()

    def frame(self, view):
        ids = [uid for uid in view.selected_ids() if self.snapshot.nodes[uid].scope == view.scope]
        if not ids:
            self.status.setText("Select nodes in this scope before creating a frame.")
            return
        chain = self.snapshot.members(view.scope)
        indices = sorted(chain.index(uid) for uid in ids)
        if indices != list(range(indices[0], indices[-1] + 1)):
            self.status.setText("Select consecutive nodes to frame: collapsing scattered nodes would misrepresent composition order.")
            return
        context = self.snapshot.context
        name, ok = self.input_text("Graph Frame", "Frame name:", "Frame")
        if context != self.adapter.context():
            self.request_refresh()
            return
        if ok and name.strip():
            try:
                for uid in ids:
                    p = view.cards[uid].pos()
                    self.layout.positions[(view.scope, uid)] = (p.x(), p.y())
                self.layout.frame(view.scope, ids, name.strip()[:100])
                view.rebuild()
            except ValueError as exc:
                self.status.setText(str(exc))

    def rename_frame(self, frame):
        name, ok = self.input_text("Rename Frame", "Name:", frame.name)
        if ok and name.strip():
            frame.name = name.strip()[:100]
            self.view().rebuild()

    def remove_frame(self, uid):
        self.layout.frames.pop(uid, None)
        self.view().rebuild()

    def navigate(self, uid, domain="content"):
        try:
            self.adapter.navigate(uid, self.snapshot.context, domain)
            self.status.setText("Selected in Painter. Use native Properties for resource and procedural parameters.")
        except Exception as exc:
            self.status.setText("Navigation failed: " + str(exc))

    def reorder_native(self, uid):
        node = self.snapshot.nodes.get(uid)
        if node is None or self.disposed:
            return
        try:
            self.adapter.navigate(uid, self.snapshot.context, node.scope[1])
            self.status.setText("Selected in Painter. " + REORDER_REASON +
                                " Keep referenced anchors below their consumers. Use Refresh if needed.")
        except Exception as exc:
            self.status.setText("Navigation failed: " + str(exc))

    def reorder_selection_native(self, selected):
        if self.disposed:
            return
        try:
            ordered = self.adapter.navigate_many(selected, self.snapshot.context)
            self.status.setText(f"Selected {len(ordered)} nodes in Painter's native order. " + REORDER_REASON +
                                " Keep referenced anchors below their consumers.")
        except Exception as exc:
            self.status.setText("Navigation failed: " + str(exc))

    def select_native(self, uid, domain="content"):
        """A user click selects Painter content/mask without graph navigation or a toast."""
        if self.disposed or self.refreshing:
            return
        try:
            self.adapter.navigate(uid, self.snapshot.context, domain)
        except Exception as exc:
            self.status.setText("Selection failed: " + str(exc))

    def preview_mask(self, uid):
        """Use a uniquely identified native action, never guess a private host API."""
        from PySide6 import QtGui
        try:
            self.adapter.navigate(uid, self.snapshot.context, "mask")
            window = self.adapter.sp.ui.get_main_window()
            labels = {"view mask", "show mask", "mask view", "solo mask", "isolate mask"}
            actions = [action for action in window.findChildren(QtGui.QAction)
                       if action.isEnabled() and action.menu() is None and
                       action.text().replace("&", "").strip().casefold() in labels]
            if len(actions) != 1:
                raise ValueError("No unique native mask-preview action is exposed by this Painter build. "
                                 "Use Alt + click on the native Layers mask thumbnail.")
            actions[0].trigger()
        except Exception as exc:
            self.status.setText("Mask preview unavailable: " + str(exc))

    def edit_connection(self, uid, target, side, scope, context):
        if self.native_reorder_busy:
            self.status.setText("Wait for the native reorder to finish")
            return
        if target is not None:
            from .ordering import connection_move
            from .native_drag import start
            try:
                plan = connection_move(self.adapter.scan(), uid, target, side, context, scope)
                if not plan.noop:
                    from . import native_effect_order
                    if scope[1] in ("content", "mask") and native_effect_order.available(self.adapter.sp):
                        native_effect_order.move(self.adapter, plan)
                        if uid in self.adapter.disconnected:
                            self.adapter.reconnect(uid, target, side, context, scope)
                        self.status.setText("Native effect order updated (experimental)")
                        self.request_refresh()
                        return
                    self.native_reorder_busy = True

                    def completed(error):
                        self.native_reorder_busy = False
                        self.native_reorder = None
                        if self.disposed:
                            return
                        if not error and uid in self.adapter.disconnected:
                            try:
                                self.adapter.reconnect(uid, target, side, context, scope)
                            except Exception as exc:
                                error = str(exc)
                        self.status.setText(error or "Native layer order updated")
                        self.request_refresh()

                    try:
                        self.native_reorder = start(self.adapter, plan, self, completed)
                    except Exception:
                        self.native_reorder_busy = False
                        raise
                    return
            except Exception as exc:
                self.status.setText(str(exc))
                self.request_refresh()
                return
        if target is None:
            self.mutate(lambda: self.adapter.disconnect(uid, context))
        else:
            self.mutate(lambda: self.adapter.reconnect(uid, target, side, context, scope))

    def rename(self, uid):
        context = self.snapshot.context
        node = self.snapshot.nodes[uid]
        name, ok = self.input_text("Rename Node", "Name:", node.name)
        if ok:
            self.mutate(lambda: self.adapter.rename(uid, context, name))

    def delete(self, uid):
        context = self.snapshot.context
        node = self.snapshot.nodes[uid]
        dialog = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, "Delete Node", "Delete '" + node.name +
                                      "' in Painter? Its child layers, mask and effects are also removed. "
                                      "Use Painter Undo to restore.",
                                      QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No, self)
        dialog.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
        answer = self.exec_dialog(dialog)
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            self.mutate(lambda: self.adapter.delete(uid, context))

    def inspect(self, uid):
        self.inspected = uid

    def toggle_enabled(self, uid):
        node = self.snapshot.nodes.get(uid)
        if node is None:
            return
        context, value = self.snapshot.context, not node.visible
        # Do not delete a QGraphicsItem while its mouse event is being dispatched.
        QtCore.QTimer.singleShot(0, lambda: None if self.disposed else self.mutate(
            lambda: self.adapter.visibility(uid, context, value)))

    def delete_selected(self, view):
        if self.modal_depth or self.disposed:
            return
        ids = view.selected_ids()
        frames = set()
        for item in view.scene().selectedItems():
            frame = getattr(item, "frame", None)
            if frame:
                frames.add(frame.id)
            uid = getattr(item, "uid", "")
            if uid.startswith("@frame:"):
                frames.add(uid[7:])
        if not ids and not frames:
            return
        selected = set(ids)
        roots = []
        for uid in ids:
            parent = self.snapshot.nodes[uid].scope[0]
            while parent and parent not in selected:
                parent = self.snapshot.nodes[parent].scope[0]
            if not parent:
                roots.append(uid)
        context = self.snapshot.context
        if roots:
            names = ", ".join(self.snapshot.nodes[uid].name for uid in roots)
            dialog = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, "Delete Nodes",
                                          "Delete " + names + " in Painter? Child layers, masks and effects are also removed. "
                                          "Use Painter Undo to restore.",
                                          QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No, self)
            dialog.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
            if self.exec_dialog(dialog) != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            def remove():
                # Resolve every target before the first mutation, then group the undo entry.
                for uid in roots:
                    self.adapter.resolve(uid, context)
                with self.adapter.transaction("Layer Graph: delete selection"):
                    for uid in roots:
                        self.adapter.delete(uid, context)
            self.mutate(remove)
        for uid in frames:
            self.layout.frames.pop(uid, None)
        if frames:
            self.refresh()

    def channel_popup(self, uid):
        node = self.snapshot.nodes.get(uid)
        if node is None:
            return
        context = self.snapshot.context
        try:
            channels = self.adapter.blending(uid, context)
            if not channels:
                self.status.setText("This node has no channel blending controls.")
                return
            modes = self.adapter.blend_modes()
        except Exception as exc:
            self.status.setText("Channel controls unavailable: " + str(exc))
            return
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(node.name + " · Channel Blending")
        form = QtWidgets.QFormLayout(dialog)
        channel = QtWidgets.QComboBox()
        opacity = QtWidgets.QDoubleSpinBox()
        opacity.setRange(0, 100)
        opacity.setSuffix(" %")
        opacity.setDecimals(1)
        blend = QtWidgets.QComboBox()
        for mode in modes:
            blend.addItem(getattr(mode, "name", str(mode)), mode)
        for ch, value, mode in channels:
            channel.addItem(getattr(ch, "name", str(ch) if ch is not None else "Mask"), (ch, value, mode))
        def changed():
            _ch, value, mode = channel.currentData()
            opacity.setValue(value * 100)
            blend.setCurrentIndex(blend.findData(mode))
        channel.currentIndexChanged.connect(changed)
        changed()
        form.addRow("Channel", channel)
        form.addRow("Opacity", opacity)
        form.addRow("Blend", blend)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if self.exec_dialog(dialog) == QtWidgets.QDialog.DialogCode.Accepted:
            self.mutate(lambda: self.adapter.set_blending(uid, context, channel.currentData()[0],
                                                        opacity.value() / 100, blend.currentData()))

    def showEvent(self, event):
        super().showEvent(event)
        if not self.disposed:
            self.poll.start()
            self.refresh()

    def hideEvent(self, event):
        self.timer.stop()
        self.poll.stop()
        super().hideEvent(event)

    def dispose(self):
        self.disposed = True
        if self.native_reorder is not None:
            self.native_reorder("Layer Graph closed during native reorder")
        self.timer.stop()
        self.poll.stop()
        self.status.timeout.stop()
        self.app.events.remove(self.request_refresh)