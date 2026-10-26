"""Exercise both real package layouts in isolated Python processes."""
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("checkout", [False, True])
def test_plugin_discovery_and_lifecycle(checkout):
    root = Path(__file__).resolve().parents[1]
    package_path = root if checkout else root / "painter_python" / "plugins" / root.name
    script = r'''
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "MBToolkit_3DPainter", path / "__init__.py",
    submodule_search_locations=[str(path)])
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
assert plugin.__version__ == "0.1.0"
from MBToolkit_3DPainter.core.models import default_settings
assert set(default_settings()["features"]) == {"pie_menus", "channel_blending", "font_tool", "anchor_manager", "layer_graph"}

calls = []
class Toolkit:
    def start(self): calls.append("start")
    def stop(self): calls.append("stop")

bootstrap = ModuleType("MBToolkit_3DPainter.bootstrap")
bootstrap.Toolkit = Toolkit
sys.modules[bootstrap.__name__] = bootstrap
plugin.start_plugin()
plugin.start_plugin()
assert plugin._app is not None
plugin.close_plugin()
plugin.close_plugin()
assert plugin._app is None
assert calls == ["start", "stop"]
plugin.reload_plugin()
assert bootstrap.__name__ not in sys.modules
'''
    result = subprocess.run([sys.executable, "-I", "-c", script, str(package_path)],
                            capture_output=True, text=True, cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr