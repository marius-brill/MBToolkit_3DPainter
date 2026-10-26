"""Optional dock using the toolkit's single-owner lifecycle."""
import substance_painter as sp
from ...core.feature import DockFeature


class Feature(DockFeature):
    id = "layer_graph"
    label = "MBToolkit · Layer Graph (Prototype)"

    def create_panel(self):
        from .adapter import Adapter
        from .panel import Panel
        return Panel(self.app, Adapter(sp, lambda: self.app.events.project_epoch))