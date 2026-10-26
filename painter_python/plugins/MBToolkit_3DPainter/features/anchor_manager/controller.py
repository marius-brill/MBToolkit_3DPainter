"""Qt orchestration, bounded main-thread scanning and shared selection state."""
import json
import re
from time import perf_counter
from PySide6 import QtCore
from .discovery import Discovery
from .index import rebuild
from .models import GraphIndex
from .operations import Operations


class Controller(QtCore.QObject):
    changed = QtCore.Signal()
    selection_changed = QtCore.Signal()
    state_changed = QtCore.Signal()

    def __init__(self, adapter, events, settings, parent=None):
        super().__init__(parent)
        self.adapter, self.events, self.settings = adapter, events, settings
        self.operations = Operations(adapter)
        self.index = GraphIndex()
        self.selection = None
        self.context = None
        self.state = "Open a Substance 3D Painter project to inspect anchors."
        self.error = ""
        self.revision = 0
        self.visible = False
        self.disposed = False
        self.iterator = None
        self.scan = None
        self.debounce = QtCore.QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(350)
        self.debounce.timeout.connect(self.refresh)
        self.pump = QtCore.QTimer(self)
        self.pump.setInterval(0)
        self.pump.timeout.connect(self._step)
        self.poll = QtCore.QTimer(self)
        self.poll.setInterval(1000)
        self.poll.timeout.connect(self._check_context)
        self.events.add(self.request_refresh)

    def set_visible(self, visible):
        if self.disposed:
            return
        self.visible = visible
        if visible:
            self.poll.start()
            self.refresh()
        else:
            self.poll.stop()
            self.cancel()

    def cancel(self):
        self.revision += 1
        self.pump.stop()
        self.debounce.stop()
        self.iterator = self.scan = None

    def request_refresh(self):
        if self.disposed:
            return
        try:
            if self.adapter.context() != self.context:
                self.cancel()
                self.selection = None
                self.index = GraphIndex()
                self.changed.emit()
                self.selection_changed.emit()
            if self.visible and self.settings.data["anchor_manager"]["auto_refresh"]:
                self.debounce.start()
        except Exception as exc:
            self._error(exc)

    def _check_context(self):
        try:
            if self.adapter.context() != self.context:
                self.refresh()
        except Exception as exc:
            self._error(exc)

    def refresh(self):
        if self.disposed or not self.visible:
            return
        self.cancel()
        self.error = ""
        try:
            context = self.adapter.context()
            if context != self.context:
                self.selection = None
            self.context = context
            self.index = GraphIndex(revision=self.revision)
            if context is None:
                self.state = "Open a Substance 3D Painter project to inspect anchors (edition mode required)."
                self.changed.emit()
                self.state_changed.emit()
                return
            self.scan = Discovery(self.adapter, self.revision)
            self.iterator = self.scan.steps()
            self.state = "Indexing… counts are partial"
            self.changed.emit()
            self.state_changed.emit()
            self.pump.start()
        except Exception as exc:
            self._error(exc)

    def _step(self):
        start = perf_counter()
        try:
            while self.iterator is not None and perf_counter() - start < .008:
                next(self.iterator)
        except StopIteration:
            self.pump.stop()
            self.index = self.scan.index
            self.iterator = self.scan = None
            if self.selection not in self.index.nodes and self.selection not in self.index.references:
                self.selection = None
            self.state = ("No anchors found in this texture set." if not self.index.anchors else
                          f"Scan {self.index.coverage.value}")
            self.changed.emit()
            self.selection_changed.emit()
        except Exception as exc:
            self._error(exc)
        else:
            if self.scan:
                self.state = f"Indexing… {self.scan.index.scanned_nodes} nodes · counts partial"
        self.state_changed.emit()

    def _error(self, exc):
        self.cancel()
        self.error = str(exc)
        self.state = "Scan/action failed. Retry or copy diagnostic."
        self.index = GraphIndex()
        self.selection = None
        self.changed.emit()
        self.state_changed.emit()

    def select(self, identity):
        self.selection = identity
        self.selection_changed.emit()

    def navigate(self, key):
        self.adapter.navigate(key)

    def apply(self, operation):
        self.cancel()
        try:
            result = operation()
            self.index = rebuild(result.index)
            if result.created:
                self.selection = result.created
            if self.selection not in self.index.nodes and self.selection not in self.index.references:
                self.selection = None
            self.state = f"{result.completed} completed · {len(result.skipped)} skipped · {len(result.failed)} failed"
            self.changed.emit()
            self.selection_changed.emit()
            self.state_changed.emit()
            return result
        except Exception:
            self.refresh()
            raise

    def diagnostic(self):
        report = self.adapter.diagnostic()
        report.update(feature_version="0.1.0", coverage=self.index.coverage.value,
                      scanned_nodes=self.index.scanned_nodes, anchors=len(self.index.anchors),
                      references=len(self.index.references),
                      coverage_by_kind={k: v.value for k, v in self.index.coverage_by_kind.items()},
                      gaps=self.index.gaps, error=self.error)
        # Diagnostics contain project labels but no local file paths or cache UIDs.
        text = json.dumps(report, indent=2, ensure_ascii=False)
        # Exception text may contain paths even though we never query project filenames.
        return re.sub(r"[A-Za-z]:\\\\[^\"\n]*", "[local path redacted]", text)

    def dispose(self):
        self.disposed = True
        self.cancel()
        self.poll.stop()
        self.events.remove(self.request_refresh)