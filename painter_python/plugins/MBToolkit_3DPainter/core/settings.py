"""Cross-platform and atomic local settings storage."""
import json
import os
import tempfile
from pathlib import Path
from .models import default_settings, clean_config, clone_config
from ..metadata import NAME, VERSION


class Settings:
    def __init__(self, config_dir=None):
        if config_dir is None:
            from PySide6.QtCore import QStandardPaths
            base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
            if not base:
                raise RuntimeError("Painter could not provide a writable configuration directory")
            config_dir = Path(base) / NAME
        self.directory = Path(config_dir)
        self.path = self.directory / "settings.json"
        self.data = default_settings()

    def load(self):
        if not self.path.is_file():
            return
        try:
            self.data = clean_config(json.loads(self.path.read_text(encoding="utf-8")))
        except (ValueError, OSError, TypeError) as exc:
            # Preserve invalid/newer configs instead of overwriting them at startup.
            raise RuntimeError(f"Settings could not be loaded: {self.path}: {exc}") from exc

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        data = clean_config(self.data)
        data["plugin_version_last_run"] = VERSION
        fd, name = tempfile.mkstemp(prefix=".mbt-", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        self.data = data

    def enabled(self, feature_id):
        return self.data["features"][feature_id]["enabled"]

    def set_enabled(self, feature_id, enabled):
        if feature_id not in self.data["features"]:
            raise KeyError(feature_id)
        self.data["features"][feature_id]["enabled"] = bool(enabled)
        self.save()

    def export_to(self, filename):
        Path(filename).write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def import_from(self, filename):
        candidate = clean_config(json.loads(Path(filename).read_text(encoding="utf-8")))
        self.data = candidate
        self.save()

    def copy(self):
        return clone_config(self.data)
