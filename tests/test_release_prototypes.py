"""Distribution boundaries and optional prototype registration."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
NAME = "MBToolkit_3DPainter"
PROTOTYPES = {"anchor_manager", "layer_graph"}


def build(destination):
    spec = importlib.util.spec_from_file_location("build_release", ROOT / "scripts" / "build_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_release(destination)


def test_release_excludes_prototype_code_and_guides(tmp_path):
    with ZipFile(build(tmp_path / "release.zip")) as archive:
        names = archive.namelist()
        for fid in PROTOTYPES:
            assert not any(name.startswith(f"{NAME}/features/{fid}/") for name in names)
            assert f"{NAME}/docs/{fid.upper()}.md" not in names
        archive.extractall(tmp_path / "installed")
    script = '''
from MBToolkit_3DPainter.core.availability import available_prototypes
from MBToolkit_3DPainter.core.models import clean_config, default_settings
assert available_prototypes() == ()
assert set(default_settings()['features']) == {'pie_menus', 'channel_blending', 'font_tool', 'layer_search'}
old = {'features': {fid: {'enabled': True} for fid in ('anchor_manager', 'layer_graph')}}
assert not {'anchor_manager', 'layer_graph'} & clean_config(old)['features'].keys()
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path,
                            env=dict(os.environ, PYTHONPATH=str(tmp_path / "installed")),
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional real Qt integration")
@pytest.mark.parametrize("present", [(), ("anchor_manager",), ("layer_graph",), ("anchor_manager", "layer_graph")])
def test_packaged_startup_menus_preferences_and_commands(tmp_path, present):
    installed = tmp_path / "installed"
    with ZipFile(build(tmp_path / "release.zip")) as archive:
        archive.extractall(installed)
    for fid in present:
        shutil.copytree(ROOT / "painter_python" / "plugins" / NAME / "features" / fid,
                        installed / NAME / "features" / fid, ignore=shutil.ignore_patterns("__pycache__"))
    script = r'''
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from PySide6 import QtWidgets
sys.modules['substance_painter'] = SimpleNamespace(ui=Mock())
from MBToolkit_3DPainter import bootstrap
from MBToolkit_3DPainter.core.availability import available_prototypes, PROTOTYPES
from MBToolkit_3DPainter.core.settings import Settings
from MBToolkit_3DPainter.ui.preferences import Preferences
application = QtWidgets.QApplication([])
window = QtWidgets.QMainWindow()
bootstrap.sp.ui.get_main_window.return_value = window
bootstrap.compatible = lambda: True
bootstrap.NativeActions = lambda window: None
settings = Settings(sys.argv[1])
# Exercise old saved prototype flags without starting real host-dependent panels.
settings.path.write_text('{"features":{"anchor_manager":{"enabled":true},"layer_graph":{"enabled":true},'
                         '"pie_menus":{"enabled":false},"font_tool":{"enabled":false},'
                         '"channel_blending":{"enabled":false},"layer_search":{"enabled":false}}}')
bootstrap.Settings = lambda: settings
app = bootstrap.Toolkit()
app.events = Mock()
app.reconcile_features = Mock()
app.start()
expected = set(sys.argv[2:])
assert set(available_prototypes()) == expected
assert set(app.features) & PROTOTYPES.keys() == expected
assert set(app.menus) & PROTOTYPES.keys() == expected
commands = dict(app.commands.catalog())
for fid, (label, command) in PROTOTYPES.items():
    assert (command in commands) == (fid in expected)
    if fid in expected:
        app.show_feature = Mock()
        app.commands.execute(command)
        app.show_feature.assert_called_once_with(fid)
dialog = Preferences(app, window)
assert set(dialog.toggles) & PROTOTYPES.keys() == expected
dialog.close()
app.reconcile_features = bootstrap.Toolkit.reconcile_features.__get__(app)
for fid in expected:
    app.features[fid].start = Mock()
    app.features[fid].stop = Mock()
app.reconcile_features()
assert app.active == expected
app.stop()
assert app.active == set()
'''
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path), *present], cwd=tmp_path,
                            env=dict(os.environ, PYTHONPATH=str(installed), QT_QPA_PLATFORM="offscreen"),
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_source_archive_excludes_prototypes(tmp_path):
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("Requires a Git checkout")
    destination = tmp_path / "source.zip"
    result = subprocess.run(["git", "archive", "--worktree-attributes", "--format=zip",
                             f"--output={destination}", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with ZipFile(destination) as archive:
        names = archive.namelist()
    for fid in PROTOTYPES:
        assert not any(name.startswith(f"painter_python/plugins/{NAME}/features/{fid}/") for name in names)
        assert f"docs/{fid.upper()}.md" not in names
    assert "tests/test_anchor_manager.py" not in names
    assert "tests/test_layer_graph.py" not in names
    assert "scripts/build_release.py" in names