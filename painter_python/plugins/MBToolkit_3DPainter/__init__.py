"""Adobe Substance 3D Painter plugin entry point."""
from .metadata import VERSION as __version__

__all__ = ["__version__", "start_plugin", "close_plugin", "reload_plugin"]

_app = None


def start_plugin():
    global _app
    if _app is None:
        from .bootstrap import Toolkit
        instance = Toolkit()
        try:
            instance.start()
        except Exception:
            instance.stop()
            raise
        _app = instance


def close_plugin():
    global _app
    if _app is not None:
        try:
            _app.stop()
        finally:
            _app = None


def reload_plugin():
    """Called by Painter between close_plugin and start_plugin on package reload."""
    import sys
    prefix = __name__ + "."
    # Children must reload after a full teardown. Fresh modules avoid stale Qt types.
    for name in sorted((n for n in sys.modules if n.startswith(prefix)),
                       key=lambda n: n.count("."), reverse=True):
        sys.modules.pop(name, None)
