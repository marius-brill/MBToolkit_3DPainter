"""Exercise real glyph shaping, image output, durable import and button isolation."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional real Qt test")
def test_stencil_render_and_button_isolation(tmp_path):
    script = r'''
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.modules["substance_painter"] = SimpleNamespace()
from PySide6 import QtCore, QtGui, QtWidgets
from MBToolkit_3DPainter.features.font_tool import stencil, panel as module
app = QtWidgets.QApplication([])
QtCore.QStandardPaths.setTestModeEnabled(True)
probe = QtGui.QImage(32,32,QtGui.QImage.Format.Format_Grayscale8)
probe.fill(255)
stencil.verify_full_coverage(probe)
probe.setPixelColor(10,10,QtGui.QColor(0,0,0))
try:
    stencil.verify_full_coverage(probe)
except ValueError:
    pass
else:
    raise AssertionError("UV-clipped coverage accepted")
for dimensions in ((100,20), (20,100), (60,60)):
    source_image = QtGui.QImage(512, 512, QtGui.QImage.Format.Format_Grayscale8)
    source_image.fill(0)
    for y in range(100,100+dimensions[1]):
        for x in range(80,80+dimensions[0]):
            source_image.setPixelColor(x,y,QtGui.QColor(255,255,255))
    image = stencil.centered_image(source_image)
    assert image.format() == QtGui.QImage.Format.Format_Grayscale8
    left, top, right, bottom = 2048, 2048, -1, -1
    maximum = 0
    for y in range(2048):
        for x in range(2048):
            value = image.pixelColor(x, y).red()
            maximum = max(maximum, value)
            if value > 8:
                left, top, right, bottom = min(left,x), min(top,y), max(right,x), max(bottom,y)
    assert maximum == 255
    assert left >= 204 and top >= 204 and right <= 1843 and bottom <= 1843
    assert abs((left+right)/2 - 1023.5) <= 2
    assert abs((top+bottom)/2 - 1023.5) <= 2
    assert image.pixelColor(0,0).red() == 0
    first = stencil.retain_image(image)
    assert first.is_file()
    assert not QtGui.QImage(str(first)).isNull()
    assert stencil.retain_image(image) == first
try:
    empty = QtGui.QImage(512,512,QtGui.QImage.Format.Format_Grayscale8)
    empty.fill(0)
    stencil.centered_image(empty)
except ValueError:
    pass
else:
    raise AssertionError("Blank text accepted")

host = stencil.sp
import json
export_path = Path.cwd() / "quoted ' export.png"
def native_export(code):
    assert code.startswith("alg.mapexport.save(")
    arguments = json.loads("[" + code[len("alg.mapexport.save("):-1] + "]")
    assert arguments[0] == [123, "mask"]
    assert arguments[1] == str(export_path)
    assert arguments[2]["resolution"] == [2048,2048]
    assert "dithering" not in arguments[2]
    assert image.save(arguments[1], "PNG")
host.js = SimpleNamespace(evaluate=native_export)
exported = stencil.export_mask(SimpleNamespace(uid=lambda: 123), export_path)
assert exported.width() == 2048
host.project = SimpleNamespace(is_open=lambda: True)
host.resource = SimpleNamespace(Usage=SimpleNamespace(ALPHA="alpha"), import_project_resource=Mock())
host.layerstack = SimpleNamespace(insert_fill=Mock(), get_selected_nodes=Mock())
stencil.render_text = Mock(return_value=image)
stencil.create_stencil(None, "Imported", 1., 0.)
args = host.resource.import_project_resource.call_args.args
assert Path(args[0]).is_file() and args[1] == "alpha"
host.layerstack.insert_fill.assert_not_called()
host.layerstack.get_selected_nodes.assert_not_called()

panel = module.Panel(SimpleNamespace(events=SimpleNamespace(add=lambda fn: None)))
panel._selection_timer.stop()
panel.live_update.setChecked(False)
panel.text.setPlainText("Same input")
resource = SimpleNamespace(identifier=lambda: SimpleNamespace(url=lambda: "resource://test/font"),
                           gui_name=lambda: "Exact font")
panel.resources = [resource]
panel.font.addItem("Exact font", 0)
panel._write_selected = Mock()
panel._selected_source = Mock(side_effect=AssertionError("Must not read selected layer"))
panel.size.setValue(.7)
panel.rotation_degrees.blockSignals(True)
panel.rotation_degrees.setValue(90)
imported = Mock()
stencil.create_stencil = Mock(return_value=imported)
panel.stencil_button.click()
stencil.create_stencil.assert_called_once_with(resource, "Same input", 1., 0.)
panel._write_selected.assert_not_called()
panel._selected_source.assert_not_called()
assert panel.size.value() == .7 and panel.rotation_degrees.value() == 90
assert panel.stencil_button.isEnabled()
imported.show_in_ui.assert_called_once()
panel.dispose()
panel.close()
'''
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(root / "painter_python" / "plugins"))
    result = subprocess.run([sys.executable, "-c", script], env=env, cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr