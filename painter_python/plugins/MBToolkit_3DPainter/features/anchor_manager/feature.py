"""Integration with the existing dock/menu/settings lifecycle."""
import substance_painter as sp
from ...core.feature import DockFeature


class Feature(DockFeature):
    id = "anchor_manager"
    label = "MBToolkit · Anchor Manager"

    def create_panel(self):
        from .controller import Controller
        from .painter_adapter import PainterAdapter
        from .ui.manager_panel import Panel
        adapter = PainterAdapter(sp, lambda: self.app.events.project_epoch)
        controller = Controller(adapter, self.app.events, self.app.settings)
        panel = Panel(self.app, controller)
        controller.setParent(panel)
        return panel

    def show(self):
        if self.dock is not None and self.dock.isVisible():
            self.dock.hide()
        else:
            super().show()