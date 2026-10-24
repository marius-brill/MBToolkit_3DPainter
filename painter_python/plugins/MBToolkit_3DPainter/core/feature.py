"""Disposable dock-based feature."""
import substance_painter as sp


class DockFeature:
    id = None
    label = None
    def __init__(self, app):
        self.app = app
        self.panel = None
        self.dock = None

    def start(self):
        self.panel = self.create_panel()
        self.panel.setWindowTitle(self.label)
        self.panel.setObjectName("MBToolkit_" + self.id)
        self.dock = sp.ui.add_dock_widget(self.panel, sp.ui.UIMode.Edition)
        self.dock.hide()

    def create_panel(self):
        raise NotImplementedError

    def show(self):
        if self.dock is None:
            return
        self.dock.show()
        self.dock.raise_()
        if hasattr(self.panel, "refresh"):
            self.panel.refresh()

    def stop(self):
        if self.panel:
            self.app.events.remove(getattr(self.panel, "request_refresh", None))
            if hasattr(self.panel, "dispose"):
                self.panel.dispose()
            # Painter owns the dock and its content: only remove through Painter API.
            try:
                sp.ui.delete_ui_element(self.panel)
            finally:
                self.panel = None
                self.dock = None
