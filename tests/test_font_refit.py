"""Refit reuses only a recognized mask and rolls its projection back on failure."""
from copy import deepcopy
import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import test_regressions


@pytest.fixture
def painter_host(monkeypatch):
    yield from test_regressions.host_modules.__wrapped__(monkeypatch)


@pytest.mark.parametrize("failure", [False, True, "custom"])
@pytest.mark.parametrize("select_effect", [False, True])
def test_refit_preserves_source_mask_and_prior_projection(painter_host, monkeypatch, failure, select_effect):
    host_modules = painter_host
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    class PaintLayer:
        pass
    class FillEffect:
        pass
    class SourceFont:
        pass
    layer, effect, source = PaintLayer(), FillEffect(), SourceFont()
    layer.uid = lambda: 42
    layer.has_mask = lambda: True
    layer.mask_effects = lambda: [effect]
    layer.add_mask, layer.remove_mask = Mock(), Mock()
    effect.uid = lambda: 43
    effect.get_parent = lambda: layer
    effect.get_name = lambda: "Custom" if failure == "custom" else "MB Text Mask"
    effect.get_source = lambda: source
    effect.get_projection_mode = lambda: "uv"
    original = SimpleNamespace(uv_transformation=SimpleNamespace(
        scale_mode="factors", scale=[-4., 4.], rotation=37, offset=[.1, -.2]))
    current = [deepcopy(original)]
    effect.get_projection_parameters = lambda: deepcopy(current[0])
    effect.set_projection_parameters = lambda value: current.__setitem__(0, deepcopy(value))
    host_modules.layerstack = SimpleNamespace(PaintLayerNode=PaintLayer, FillEffectNode=FillEffect,
        ProjectionMode=SimpleNamespace(UV="uv"), ScaleMode=SimpleNamespace(Factors="factors"),
        set_selected_nodes=Mock(), set_selection_type=Mock(), SelectionType=SimpleNamespace(Content="content"))
    host_modules.source = SimpleNamespace(SourceFont=SourceFont)
    host_modules.project = SimpleNamespace(Metadata=Mock())
    monkeypatch.setattr(module, "selected_single_layer", lambda: ("stack", effect if select_effect else layer))
    def measure(stack, node, capture):
        capture.append(object())
        return (.2, .2, .6, .6)
    monkeypatch.setattr(module, "measure_paint_bounds", measure)
    monkeypatch.setattr(module, "FitDiagnostics", Mock())
    verify = Mock(side_effect=RuntimeError("Verification failed") if failure is True else None)
    monkeypatch.setattr(module, "verify_placement", verify)
    write = Mock()
    monkeypatch.setattr(module, "write_state", write)
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    panel = SimpleNamespace(_loading=False, _updating=False, _disposed=False,
        text=SimpleNamespace(toPlainText=lambda: "Text"), font=SimpleNamespace(currentData=lambda: 0),
        status=Mock(), _cancel_live_update=Mock(), _selection_timer=Mock(), resources=[Mock()],
        request_refresh=Mock(), halign=Mock(), size=Mock(), _transform_originals={43: original})
    module.Panel.fit_painted_area(panel)
    layer.add_mask.assert_not_called()
    layer.remove_mask.assert_not_called()
    assert effect.get_source() is source
    if failure:
        assert current[0] == original
        report.assert_called_once()
        write.assert_not_called()
    else:
        report.assert_not_called()
        assert current[0].uv_transformation.rotation == 37
        assert current[0].uv_transformation.scale[0] < 0
        assert current[0].uv_transformation.scale[1] > 0
        assert 43 not in panel._transform_originals
        panel.halign.setCurrentIndex.assert_not_called()
        write.assert_called_once()
    assert not panel._loading and not panel._updating


@pytest.mark.parametrize("operation", ["rotate", "flip", "reset"])
def test_transform_controls_assign_copy_on_get_uv(painter_host, operation):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    class Projection:
        def __init__(self):
            self.value = SimpleNamespace(scale_mode="factors", scale=[-2., 3.], rotation=17)
        @property
        def uv_transformation(self):
            return deepcopy(self.value)
        @uv_transformation.setter
        def uv_transformation(self, value):
            self.value = deepcopy(value)
    projection = Projection()
    node = Mock()
    node.uid.return_value = 43
    painter_host.layerstack = SimpleNamespace(ScaleMode=SimpleNamespace(Factors="factors"))
    panel = SimpleNamespace(_selected_uv_projection=lambda:(node, projection),
        _remember_transform=Mock(), _set_rotation_controls=Mock(), _transform_originals={})
    if operation == "rotate":
        module.Panel.rotate_selected(panel, 90)
        assert projection.value.rotation == 90
    elif operation == "flip":
        module.Panel.flip_selected(panel, 0)
        assert projection.value.scale == [2., 3.]
    else:
        module.Panel.reset_selected_transform(panel)
        assert projection.value.rotation == 0
        assert projection.value.scale == [2., 3.]
    node.set_projection_parameters.assert_called_once_with(projection)