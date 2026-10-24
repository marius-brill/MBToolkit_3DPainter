"""Feedback implementation: pure models, release layout and real offscreen Qt UI."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile
from unittest.mock import Mock

import pytest

from MBToolkit_3DPainter.core.macros import MacroRunner, validate_macro
from MBToolkit_3DPainter.core.models import clean_config
from MBToolkit_3DPainter.core.settings import Settings


def macro(steps):
    return {"id": "example", "name": "Example", "steps": steps}


def test_macro_passes_created_layer_not_mask_effect():
    layer, effect = object(), object()
    create, mask, fill = Mock(return_value=layer), Mock(), Mock(return_value=effect)
    initial = Mock()
    runner = MacroRunner({"painter.add_fill": create, "painter.black_mask": mask,
                          "painter.mask_fill": fill}, initial)
    assert runner.run(macro(["painter.add_fill", "painter.black_mask", "painter.mask_fill"])) is layer
    mask.assert_called_once_with(layer)
    fill.assert_called_once_with(layer)
    initial.assert_not_called()


def test_macro_failure_stops_later_steps_and_releases_guard():
    fill = Mock()
    runner = MacroRunner({"painter.black_mask": Mock(side_effect=ValueError("existing mask")),
                          "painter.mask_fill": fill}, lambda: object())
    with pytest.raises(RuntimeError, match="step 1"):
        runner.run(macro(["painter.black_mask", "painter.mask_fill"]))
    fill.assert_not_called()
    assert not runner.running


@pytest.mark.parametrize("steps", [[], ["python:untrusted"], ["macro:example"], ["painter.add_fill"] * 65])
def test_macro_rejects_unsafe_or_unbounded_steps(steps):
    with pytest.raises(ValueError):
        validate_macro(macro(steps))


def test_macro_reentrancy_guard():
    runner = MacroRunner({}, lambda: None)
    runner.running = True
    with pytest.raises(RuntimeError, match="already running"):
        runner.run(macro(["painter.add_fill"]))


def test_macro_settings_roundtrip_and_migration_backup(tmp_path):
    import json
    settings = Settings(tmp_path)
    previous = {"schema_version": 1, "pie_menus": [{"id": "main", "actions": ["macro:example"]}]}
    settings.path.write_text(json.dumps(previous), encoding="utf-8")
    settings.load()
    settings.data["macros"] = [macro(["painter.add_fill"])]
    settings.save()
    assert json.loads((tmp_path / "settings.pre-v2.json").read_text()) == previous
    settings.load()
    assert settings.data["macros"][0]["steps"] == ["painter.add_fill"]
    assert clean_config(settings.data) == settings.data


def test_release_has_fixed_root_and_importable_entry(tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("build_release", root / "scripts" / "build_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    archive_path = module.build_release(tmp_path / "MBToolkit-9.9.9.zip")
    with ZipFile(archive_path) as archive:
        assert {name.split("/")[0] for name in archive.namelist()} == {"MBToolkit_3DPainter"}
        assert not any("__pycache__" in name for name in archive.namelist())
        archive.extractall(tmp_path / "installed")
    script = "import MBToolkit_3DPainter; from MBToolkit_3DPainter.core.models import default_settings; assert default_settings()['schema_version'] == 2"
    env = dict(os.environ, PYTHONPATH=str(tmp_path / "installed"))
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional real Qt UI test")
def test_real_qt_editor_offscreen(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
from types import SimpleNamespace
from unittest.mock import Mock
sys.modules["substance_painter"] = SimpleNamespace()
from PySide6 import QtWidgets, QtCore
from MBToolkit_3DPainter.core.settings import Settings
from MBToolkit_3DPainter.core.commands import Commands
from MBToolkit_3DPainter.features.pie_menus.editor import Editor
application = QtWidgets.QApplication([])
settings = Settings(sys.argv[1])
commands = Commands(settings)
commands.register("mb.fonts", "Open Font Tool", lambda: None)
commands.register("mb.blending", "Open Channel Blending", lambda: None)
commands.register("mb.preferences", "Preferences", lambda: None)
window = QtWidgets.QMainWindow()
app = SimpleNamespace(settings=settings, commands=commands, main_window=window, refresh_pie_shortcuts=Mock())
editor = Editor(app, window)
editor.show()
application.processEvents()
editor.actions.setCurrentRow(0)
editor.display_name.setText("Custom")
editor.edit_slice_name()
assert editor.menus[0]["action_names"][0] == "Custom"
before = list(editor.menus[0]["actions"])
editor.reorder_slice(0, 2)
assert editor.menus[0]["action_names"][2] == "Custom"
assert editor.menus[0]["actions"] == [before[2], before[1], before[0]]
assert editor.actions.currentRow() == 2
editor.reorder_slice(2, 0)
assert editor.menus[0]["actions"] == before
editor.reorder_slice(0, 2)
for size in ((980, 760), (1400, 960)):
    editor.resize(*size)
    geometry = []
    for tab, listing in ((0, editor.menulist), (1, editor.macro_editor.list)):
        editor.tabs.setCurrentIndex(tab)
        application.processEvents()
        buttons = [b for b in listing.parentWidget().findChildren(QtWidgets.QPushButton)
                   if b.text() in ("New", "Duplicate", "Delete")]
        assert [b.text() for b in buttons] == ["New", "Duplicate", "Delete"]
        rectangles = [(b.mapTo(editor, QtCore.QPoint()).x(), b.mapTo(editor, QtCore.QPoint()).y(),
                       b.width(), b.height()) for b in buttons]
        assert rectangles[0][1] < rectangles[1][1] < rectangles[2][1]
        geometry.append((listing.width(), listing.mapTo(editor, QtCore.QPoint()).x(), rectangles))
    assert geometry[0] == geometry[1], geometry
pie_width = editor.menulist.width()
editor.tabs.setCurrentIndex(1)
application.processEvents()
assert editor.macro_editor.list.width() == pie_width
assert not any(button.text() in ("↶", "↷") for button in editor.findChildren(QtWidgets.QPushButton))
editor.preview.grab().save(sys.argv[2])
editor.add_menu()
editor.delete_menu()
editor.macro_editor.new()
editor.macro_editor.picker.setCurrentIndex(3)
editor.macro_editor.add_step()
macro_ui = editor.macro_editor
macro_ui.picker.setCurrentIndex(5)
macro_ui.add_step()
steps_before = list(macro_ui.macros[macro_ui.current]["steps"])
model = macro_ui.steps.model()
assert model.moveRows(QtCore.QModelIndex(), 0, 1, QtCore.QModelIndex(), 3)
assert macro_ui.macros[macro_ui.current]["steps"] == steps_before[1:] + steps_before[:1]
macro_ui.steps.setCurrentRow(2)
macro_ui.move(-1)
macro_ui.picker.setCurrentIndex(0)
macro_ui.add_step()
saved_steps = [macro_ui.steps.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
               for i in range(macro_ui.steps.count())]
assert len(saved_steps) != len(set(saved_steps))
assert macro_ui.macros[macro_ui.current]["steps"] == saved_steps
editor.refresh_catalog()
assert any(ident.startswith("macro:") for ident, label in editor.command_catalog())
editor.accept()
assert app.refresh_pie_shortcuts.call_count == 1
assert settings.data["macros"]
assert settings.data["pie_menus"][0]["action_names"][2] == "Custom"
reopened = Editor(app, window)
assert reopened.macro_editor.macros[-1]["steps"] == saved_steps
reopened.macro_editor.list.setCurrentRow(len(reopened.macro_editor.macros) - 1)
reopened.macro_editor.steps.setCurrentRow(0)
reopened.macro_editor.remove_step()
reopened.reject()
assert settings.data["macros"][-1]["steps"] == saved_steps
loaded = Settings(sys.argv[1])
loaded.load()
assert loaded.data["macros"][-1]["steps"] == saved_steps
from MBToolkit_3DPainter.bootstrap import Toolkit
from PySide6 import QtGui
menu = QtWidgets.QMenu()
fake = SimpleNamespace(menu=None, main_window=window, menus={},
    settings=SimpleNamespace(data={"pie_menus": [{"name": "User...", "id": "one"}]}),
    open_pie_editor=lambda: None, features={})
fake._action = lambda parent, label, callback, *args: parent.addAction(label)
Toolkit._populate_pie_menu(fake, menu)
assert [a.text() for a in menu.actions() if not a.isSeparator()] == ["Manage Pie Menus", "User..."]
from MBToolkit_3DPainter.features.font_tool.panel import Panel
app.events = SimpleNamespace(add=lambda callback: None)
panel = Panel(app)
panel.show()
from MBToolkit_3DPainter.features.font_tool.controls import slider_from_size, size_from_slider
panel.size.setValue(.5)
assert panel.size_slider.value() == slider_from_size(.5)
panel.size_slider.setValue(slider_from_size(1))
assert panel.size.value() == size_from_slider(slider_from_size(1))
panel.grab()
panel.close()
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(root / "painter_python" / "plugins"))
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path), str(tmp_path / "pie.png")],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "pie.png").is_file()