"""Stable, allowlisted commands. User scripts run only after explicit opt-in."""
import runpy
from .models import SAFE_NAME


class Commands:
    def __init__(self, settings):
        self._items = {}
        self.settings = settings

    def register(self, command_id, label, callback):
        if command_id in self._items:
            raise ValueError("Duplicate command: " + command_id)
        self._items[command_id] = (label, callback)

    def unregister(self, command_id):
        self._items.pop(command_id, None)

    def catalog(self):
        items = [(k, v[0]) for k, v in self._items.items()]
        # Scripts deliberately appear even when opt-in is off, with dispatch gated.
        directory = self.settings.directory / "scripts"
        if directory.exists():
            for path in sorted(directory.glob("*.py")):
                if SAFE_NAME.fullmatch(path.stem):
                    items.append(("python:" + path.stem, "Python: " + path.stem))
        return sorted(items, key=lambda pair: pair[1].casefold())

    def execute(self, command_id):
        if command_id.startswith("python:"):
            if not self.settings.data.get("allow_custom_python"):
                raise PermissionError("Enable trusted custom Python actions in Preferences")
            name = command_id.partition(":")[2]
            if not SAFE_NAME.fullmatch(name):
                raise ValueError("Invalid Python action identifier")
            script = self.settings.directory / "scripts" / (name + ".py")
            if not script.is_file():
                raise FileNotFoundError(script)
            # Scripts execute with full user permissions. Only allow explicitly trusted local files.
            runpy.run_path(str(script), run_name="__main__")
        else:
            self._items[command_id][1]()
