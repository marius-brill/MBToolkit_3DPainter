"""Native-export simulation: place a whole source square inside a partial UV island."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional Qt")
@pytest.mark.parametrize("signs", [(1, 1), (-1, 1)])
def test_stencil_source_recovers_partial_coverage_without_clipping(tmp_path, signs):
    script = r'''
import sys
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
sys.modules['substance_painter']=SimpleNamespace()
from PySide6 import QtGui
from MBToolkit_3DPainter.features.font_tool import stencil as s
coverage=QtGui.QImage(2048,2048,QtGui.QImage.Format.Format_Grayscale8)
coverage.fill(0)
painter=QtGui.QPainter(coverage)
painter.fillRect(1000,300,800,1000,QtGui.QColor(255,255,255))
painter.end()
try:
    s.verify_full_coverage(coverage)
except ValueError:
    pass
else:
    raise AssertionError('Fixture must reproduce original full-square rejection')
region,extent=s.usable_region(coverage)
assert extent*2048>=128
current=[SimpleNamespace(uv_transformation=SimpleNamespace(scale=[1.,1.],offset=[0.,0.]))]
effect=SimpleNamespace(get_projection_parameters=lambda:deepcopy(current[0]),
    set_projection_parameters=lambda v:current.__setitem__(0,deepcopy(v)))
exports=[]
def export(layer,path):
    uv=current[0].uv_transformation
    cx=.5+int(sys.argv[1])*uv.offset[0]
    cy=.5+int(sys.argv[2])*uv.offset[1]
    half=.5/uv.scale[0]
    image=QtGui.QImage(2048,2048,QtGui.QImage.Format.Format_Grayscale8)
    image.fill(0)
    painter=QtGui.QPainter(image)
    from PySide6 import QtCore
    painter.setClipRect(1000,300,800,1000)
    painter.fillRect(QtCore.QRectF((cx-half)*2048,(1-cy-half)*2048,
                                 2*half*2048,2*half*2048),QtGui.QColor(255,255,255))
    painter.end()
    exports.append(path)
    return image
s.export_mask=export
b=s.place_stencil_source(object(),effect,coverage,Path.cwd())
assert b[0]>=region[0] and b[2]<=region[2]
assert b[1]>=region[1] and b[3]<=region[3]
assert len(exports)<=64
print('Partial-UV square placement exports:',len(exports))
# Exercise render_text through final crop/centering and temporary-state cleanup.
from unittest.mock import Mock
params=SimpleNamespace()
source=SimpleNamespace(get_parameters=lambda:params,set_parameters=lambda value:None)
effect.set_source=lambda channel,identifier:source
effect.set_projection_mode=lambda mode:None
class Layer:
    pass
layer=Layer()
layer.set_name=lambda name:None
layer.add_mask=lambda background:None
api=SimpleNamespace(insert_fill=Mock(side_effect=[layer,effect]),
    InsertPosition=SimpleNamespace(from_textureset_stack=lambda stack:None,inside_node=lambda *a:None),
    NodeStack=SimpleNamespace(Mask='mask'),MaskBackground=SimpleNamespace(Black='black'),
    ProjectionMode=SimpleNamespace(UV='uv'),UVWrapMode=SimpleNamespace(RepeatNone='none'),
    ScaleMode=SimpleNamespace(Factors='factors'),UVProjectionParams=lambda **kw:SimpleNamespace(**kw),
    UVTransformationParams=lambda **kw:SimpleNamespace(**kw),LayerNode=Layer,
    get_selected_nodes=lambda stack:[],set_selected_nodes=Mock(),delete_node=Mock())
s.sp.layerstack=api
s.sp.textureset=SimpleNamespace(get_active_stack=lambda:'stack')
s.sp.colormanagement=SimpleNamespace(Color=lambda *rgb:rgb)
s.sp.source=SimpleNamespace(HorizontalAlignment=SimpleNamespace(Center='center'),
    VerticalAlignment=SimpleNamespace(Middle='middle'),ResolutionOverride=lambda *a:None,
    ResolutionMode=SimpleNamespace(Custom='custom'))
native_square_export=export
def font_export(layer,path):
    if current[0].uv_transformation.scale==[1,1] and params.background_color==(1,1,1):
        image=coverage.copy()
    elif params.background_color==(1,1,1):
        image=native_square_export(layer,path)
    else:
        uv=current[0].uv_transformation
        cx=.5+int(sys.argv[1])*uv.offset[0]
        cy=.5+int(sys.argv[2])*uv.offset[1]
        size=1/uv.scale[0]
        image=QtGui.QImage(2048,2048,QtGui.QImage.Format.Format_Grayscale8)
        image.fill(0)
        painter=QtGui.QPainter(image)
        from PySide6 import QtCore
        painter.setClipRect(1000,300,800,1000)
        painter.fillRect(QtCore.QRectF((cx-size*.4)*2048,(1-cy-size*.12)*2048,
                                     size*.8*2048,size*.24*2048),QtGui.QColor(255,255,255))
        painter.end()
    path.touch()
    return image
s.export_mask=font_export
image=s.render_text(SimpleNamespace(identifier=lambda:'exact-font'),'Exact text',1,.1)
assert image.width()==2048 and image.height()==2048
assert image.pixelColor(1024,1024).red()==255
assert image.pixelColor(0,0).red()==0
api.delete_node.assert_called_once_with(layer)
api.set_selected_nodes.assert_called_once_with([])
# A hole must never be swallowed by the coarse coverage search.
painter=QtGui.QPainter(coverage)
painter.fillRect(1200,500,200,200,QtGui.QColor(0,0,0))
painter.end()
region,_=s.usable_region(coverage)
assert not (region[0]<1300/2048<region[2] and region[1]<1-600/2048<region[3])
tiny=QtGui.QImage(2048,2048,QtGui.QImage.Format.Format_Grayscale8)
tiny.fill(0)
painter=QtGui.QPainter(tiny)
painter.fillRect(100,100,40,40,QtGui.QColor(255,255,255))
painter.end()
try:
    s.usable_region(tiny)
except ValueError:
    pass
else:
    raise AssertionError('Tiny coverage must not become a blurry upscaled stencil')
'''
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root / "painter_python" / "plugins"))
    result = subprocess.run([sys.executable, "-c", script, *map(str, signs)], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr