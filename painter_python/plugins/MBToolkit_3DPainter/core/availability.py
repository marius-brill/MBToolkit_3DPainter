"""Prototype packages are available in checkouts, never required by releases."""
from pathlib import Path


PROTOTYPES = {
    "anchor_manager": ("Anchor Manager (Prototype)", "mb.anchors"),
    "layer_graph": ("Layer Graph (Prototype)", "mb.layer_graph"),
}


def available_prototypes():
    """Check package presence without importing host or prototype dependencies.

    Actual import errors in a present prototype must propagate, not be hidden.
    """
    features = Path(__file__).resolve().parents[1] / "features"
    return tuple(fid for fid in PROTOTYPES if (features / fid / "__init__.py").is_file())