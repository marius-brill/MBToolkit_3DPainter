"""Best-effort bridge to uniquely named QActions; never inspect private methods."""
from PySide6 import QtGui


class NativeActions:
    def __init__(self, window):
        self.window = window

    def _actions(self):
        groups = {}
        for action in self.window.findChildren(QtGui.QAction):
            name = action.objectName()
            label = action.text().replace("&", "").strip()
            if not name or not label or action.isSeparator() or action.menu() is not None:
                continue
            if label.startswith("MBToolkit") or name.startswith("MBToolkit"):
                continue
            groups.setdefault(name, []).append((label, action))
        return {"native:" + name: values[0] for name, values in groups.items() if len(values) == 1}

    def catalog(self):
        return [(key, "Native (host-dependent): " + label + (" [unavailable]" if not action.isEnabled() else ""))
                for key, (label, action) in self._actions().items()]

    def execute(self, identifier):
        entry = self._actions().get(identifier)
        if entry is None:
            raise ValueError("Painter action is missing or ambiguous in this host version")
        _label, action = entry
        if not action.isEnabled():
            raise ValueError("Painter action is disabled in the current context")
        action.trigger()