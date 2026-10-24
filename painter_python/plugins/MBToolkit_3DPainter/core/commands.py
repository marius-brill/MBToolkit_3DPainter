"""Stable, allowlisted commands. User scripts run only after explicit opt-in."""
import runpy
from .models import SAFE_NAME


class Commands:
    def __init__(self, settings):
        self._items = {}
        self.settings = settings
        self.macro_runner = None
        self.native_provider = None

    def register(self, command_id, label, callback):
        if command_id in self._items:
            raise ValueError("Duplicate command: " + command_id)
        self._items[command_id] = (label, callback)

    def unregister(self, command_id):
        self._items.pop(command_id, None)

    def catalog(self):
        items = [(k, v[0]) for k, v in self._items.items()]
        items.extend(("macro:" + m["id"], "Macro: " + m["name"])
                     for m in self.settings.data.get("macros", []))
        if self.native_provider is not None:
            items.extend(self.native_provider.catalog())
        # Scripts deliberately appear even when opt-in is off, with dispatch gated.
        directory = self.settings.directory / "scripts"
        if directory.exists():
            for path in sorted(directory.glob("*.py")):
                if SAFE_NAME.fullmatch(path.stem):
                    items.append(("python:" + path.stem, "Python: " + path.stem))
        return sorted(items, key=lambda pair: pair[1].casefold())

    def execute(self, command_id):
        if command_id.startswith("macro:"):
            macro = next((m for m in self.settings.data.get("macros", [])
                          if m["id"] == command_id.partition(":")[2]), None)
            if macro is None or self.macro_runner is None:
                raise ValueError("This macro is unavailable")
            return self.macro_runner.run(macro)
        if command_id.startswith("native:"):
            if self.native_provider is None:
                raise ValueError("Native Painter actions are unavailable")
            return self.native_provider.execute(command_id)
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
            if command_id not in self._items:
                raise ValueError("Command is unavailable: " + command_id)
            return self._items[command_id][1]()
