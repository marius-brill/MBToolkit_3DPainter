"""Relative scale arithmetic is host-independent and cannot accumulate drift."""
from types import SimpleNamespace

import pytest

from MBToolkit_3DPainter.features.font_tool.sizing import metadata_key, read_state, scaled_projection, size_factor, write_state


@pytest.mark.parametrize("value,factor", [(-1, .25), (0, 1), (1, 4)])
def test_relative_size_endpoints(value, factor):
    assert size_factor(value) == factor


@pytest.mark.parametrize("value", [-1.1, 1.1, float("nan"), float("inf")])
def test_relative_size_rejects_invalid(value):
    with pytest.raises(ValueError):
        size_factor(value)


def test_relative_size_restores_auto_baseline_without_drift():
    original = SimpleNamespace(uv_transformation=SimpleNamespace(
        scale=[-3., 4.], rotation=37, offset=[.2, -.1]), wrapping="preserved")
    current, state = original, None
    for value in (1, -.5, 1, -1, 0, .25, 0):
        current, state = scaled_projection(current, value, state)
        assert current.uv_transformation.scale == pytest.approx([-3 / size_factor(value), 4 / size_factor(value)])
        assert current.uv_transformation.rotation == 37
        assert current.uv_transformation.offset == [.2, -.1]
        assert current.wrapping == "preserved"
    assert original.uv_transformation.scale == [-3., 4.]


def test_relative_size_preserves_external_mirroring_and_rescaling():
    original = SimpleNamespace(uv_transformation=SimpleNamespace(scale=[2., 3.]))
    current, state = scaled_projection(original, 1)
    current.uv_transformation.scale = [-1., 1.5]
    restored, state = scaled_projection(current, 0, state)
    assert restored.uv_transformation.scale == [-4., 6.]


def test_relative_size_metadata_roundtrip_and_stack_isolation():
    data = {}
    metadata = SimpleNamespace(list=lambda: list(data), get=data.__getitem__, set=data.__setitem__)
    key = metadata_key("stack", 42)
    assert read_state(metadata, key) is None
    write_state(metadata, key, ([-3., 4.], .5))
    assert read_state(metadata, key) == ([-3., 4.], .5)
    assert read_state(metadata, metadata_key("other", 42)) is None