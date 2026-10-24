"""Real Qt coverage normalization, padded rows, threshold fidelity and timing."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional Qt")
def test_coverage_buffers_match_original_pixel_thresholds_and_report_timing(tmp_path):
    script = r'''
import sys, random, time
from types import SimpleNamespace
sys.modules['substance_painter']=SimpleNamespace()
from PySide6 import QtGui
from MBToolkit_3DPainter.features.font_tool.pixels import Coverage
from MBToolkit_3DPainter.features.font_tool.placement import coverage_value
rng=random.Random(44)
for fmt in (QtGui.QImage.Format.Format_ARGB32, QtGui.QImage.Format.Format_ARGB32_Premultiplied,
            QtGui.QImage.Format.Format_RGBA8888, QtGui.QImage.Format.Format_RGB32,
            QtGui.QImage.Format.Format_Grayscale8):
    image=QtGui.QImage(17,13,fmt)
    for y in range(13):
        for x in range(17):
            image.setPixelColor(x,y,QtGui.QColor(*(rng.randrange(256) for _ in range(4))))
    pixels=Coverage(image)
    assert len(pixels.data)==17*13
    for y in range(13):
        for x in range(17):
            original=coverage_value(image,x,y)
            actual=pixels.data[y*17+x]
            assert (actual>8)==(original>8), (fmt,original,actual)
            assert abs(actual-original)<=1.01
    assert pixels.overlap(pixels)==1
image=QtGui.QImage(512,512,QtGui.QImage.Format.Format_RGB32)
image.fill(QtGui.QColor(0,0,0))
painter=QtGui.QPainter(image)
painter.fillRect(100,150,280,120,QtGui.QColor(255,255,255))
painter.end()
start=time.perf_counter()
for _ in range(5):
    assert Coverage(image).bounds()==(100/512,1-270/512,380/512,1-150/512)
print('Five buffer bounds scans seconds:',round(time.perf_counter()-start,4))
pixels=Coverage(image)
start=time.perf_counter()
pixels.overlap(pixels)
print('One cached overlap seconds:',round(time.perf_counter()-start,4))
'''
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root / "painter_python" / "plugins"))
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)