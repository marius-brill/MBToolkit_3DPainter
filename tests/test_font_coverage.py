"""Real Qt pixel/alpha and saved Fit diagnostics regression checks."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional real Qt test")
def test_fit_coverage_alpha_holes_and_diagnostics(tmp_path):
    script = r'''
import json
import sys
from types import SimpleNamespace
sys.modules["substance_painter"] = SimpleNamespace()
from PySide6 import QtGui, QtWidgets
from MBToolkit_3DPainter.features.font_tool import placement as p
app = QtWidgets.QApplication([])
def image():
    result = QtGui.QImage(16, 16, QtGui.QImage.Format.Format_ARGB32)
    result.fill(QtGui.QColor(255, 255, 255, 0))
    return result
paint, mask = image(), image()
for y in range(2, 14):
    for x in range(2, 14):
        paint.setPixelColor(x, y, QtGui.QColor(255,255,255,255))
for y in range(6, 10):
    for x in range(6, 10):
        mask.setPixelColor(x, y, QtGui.QColor(255,255,255,255))
assert p.coverage_bounds(mask) == (.375, .375, .625, .625)
assert p.coverage_overlap(paint, mask) == 1
for y in range(6, 10):
    for x in range(6, 10):
        paint.setPixelColor(x, y, QtGui.QColor(255,255,255,0))
assert p.coverage_bounds(paint) == (.125, .125, .875, .875)
assert p.coverage_overlap(paint, mask) == 0, "Bounding boxes hide a hole in the paint"
rows = [[p.coverage_value(paint,x,y) > 8 for x in range(16)] for y in range(16)]
region = p.painted_rectangle(rows, (.25,.25))
assert region != (.125,.125,.875,.875), "Recovery must avoid the hole"
mask.setPixelColor(6, 6, QtGui.QColor(255,255,255,128))
assert 127 < p.coverage_value(mask, 6, 6) < 129
try:
    p.coverage_overlap(image(), image())
except ValueError as exc:
    assert "no measurable ink" in str(exc)
else:
    raise AssertionError("Transparent white counted as ink")
from pathlib import Path
root = Path(sys.argv[1])
p.QtCore.QStandardPaths.writableLocation = lambda *_: str(root)
d = p.FitDiagnostics()
d.image("coverage", paint)
d.image("probe", mask)
d.overlap(paint, mask)
d.record(result="failed", ink_overlap=0)
assert json.loads((d.root / "last-fit.json").read_text())[-1]["result"] == "failed"
preview = QtGui.QImage(str(d.root / "last-fit-overlap.png"))
assert preview.pixelColor(7,7) == QtGui.QColor(255,0,0)
assert preview.pixelColor(3,3) == QtGui.QColor(0,255,0)
assert (d.root / "last-fit-coverage.png").is_file()
assert (d.root / "last-fit-probe.png").is_file()
p.FitDiagnostics()
assert not (d.root / "last-fit-probe.png").exists(), "Old attempts must not masquerade as current"
import os
os.environ.pop("MBTOOLKIT_FONT_DIAGNOSTICS")
assert p.FitDiagnostics().root is None
os.environ["MBTOOLKIT_FONT_DIAGNOSTICS"] = "1"
blocked = root / "not-a-directory"
blocked.write_text("blocked")
p.QtCore.QStandardPaths.writableLocation = lambda *_: str(blocked)
assert p.FitDiagnostics().root is None, "Diagnostic disk failures must not break Fit"
'''
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", MBTOOLKIT_FONT_DIAGNOSTICS="1",
               PYTHONPATH=str(root / "painter_python" / "plugins"))
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional real Qt test")
@pytest.mark.parametrize("shape", ["hole", "disconnected"])
def test_fit_recovers_zero_overlap_with_real_exported_pixels(tmp_path, shape):
    script = r'''
import json, sys
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
sp = SimpleNamespace()
sys.modules['substance_painter'] = sp
from PySide6 import QtGui
from MBToolkit_3DPainter.features.font_tool import placement as p
paint = QtGui.QImage(512,512,QtGui.QImage.Format.Format_RGB32)
paint.fill(QtGui.QColor(0,0,0))
for y in range(64,448):
    for x in range(64,448):
        covered = (not (190 <= x < 322 and 190 <= y < 322)) if sys.argv[1]=='hole' else (
            (64 <= x < 160 or 352 <= x < 448) and 190 <= y < 322)
        if covered:
            paint.setPixelColor(x,y,QtGui.QColor(255,255,255))
initial = SimpleNamespace(uv_transformation=SimpleNamespace(offset=[0.,0.],scale=[4.,4.]))
current = [deepcopy(initial)]
effect = SimpleNamespace(uid=lambda:43, get_projection_parameters=lambda:deepcopy(current[0]),
                         set_projection_parameters=lambda value:current.__setitem__(0,deepcopy(value)))
layer = SimpleNamespace(uid=lambda:42)
sp.layerstack = SimpleNamespace(get_selected_nodes=lambda stack:[layer])
sp.textureset = SimpleNamespace(get_active_stack=lambda:'stack')
exports=[]
def export(code):
    args=json.loads('['+code[len('alg.mapexport.save('):-1]+']')
    assert args[0]==[42,'mask'] and args[2]['keepAlpha'] is True
    uv=current[0].uv_transformation
    cx,cy=.5-uv.offset[0], .5+uv.offset[1]
    rx,ry=(.16 if sys.argv[1]=='hole' else .5)/abs(uv.scale[0]),.08/abs(uv.scale[1])
    image=QtGui.QImage(512,512,QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor(255,255,255,0))
    for y in range(max(0,int((1-cy-ry)*512)),min(512,int((1-cy+ry)*512))):
        for x in range(max(0,int((cx-rx)*512)),min(512,int((cx+rx)*512))):
            image.setPixelColor(x,y,QtGui.QColor(255,255,255,255))
    assert image.save(args[1])
    exports.append(Path(args[1]))
sp.js=SimpleNamespace(evaluate=export)
diagnostics=SimpleNamespace(record=lambda **kw:None,image=lambda *args:None,overlap=lambda *args:None)
offset=p.verify_placement('stack',layer,effect,p.coverage_bounds(paint),paint,diagnostics)
assert max(abs(v) for v in offset) > .05, 'Must move away from the unpainted center'
if sys.argv[1]=='disconnected':
    assert current[0].uv_transformation.scale[0] > initial.uv_transformation.scale[0]
assert all(not path.exists() for path in exports)
assert len(exports) <= 128
'''
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               PYTHONPATH=str(root / "painter_python" / "plugins"))
    result = subprocess.run([sys.executable, "-c", script, shape], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr