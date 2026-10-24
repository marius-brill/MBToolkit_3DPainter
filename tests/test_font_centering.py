"""Render observations, not a guessed UV offset convention, determine placement."""
import pytest

from MBToolkit_3DPainter.features.font_tool.centering import solve_center


@pytest.mark.parametrize("matrix", [((1, 0), (0, 1)), ((-1, 0), (0, -1)),
                                    ((0, 2), (-2, 0)), ((.2, .1), (-.1, .3))])
def test_centering_calibrates_offset_direction_rotation_and_scale(matrix):
    calls = []
    def observe(offset):
        calls.append(offset)
        center = [.5 + sum(matrix[i][j] * offset[j] for j in range(2)) for i in range(2)]
        return center[0] - .04, center[1] - .02, center[0] + .04, center[1] + .02
    result = solve_center(observe, [.31, .68], [0, 0])
    final = observe(result)
    assert (final[0] + final[2]) / 2 == pytest.approx(.31)
    assert (final[1] + final[3]) / 2 == pytest.approx(.68)
    assert len(calls) <= 28


def test_centering_recovers_from_invisible_seed():
    def observe(offset):
        if abs(offset[0]) > 1:
            raise ValueError("empty")
        return .45 + offset[0], .45 + offset[1], .55 + offset[0], .55 + offset[1]
    assert solve_center(observe, [.6, .4], [20, 20]) == pytest.approx([.1, -.1])


@pytest.mark.parametrize("bounds", [(.4, .4, .6, .6), (0, .4, .6, .6),
                                    (float("nan"), .4, .6, .6)])
def test_centering_rejects_stale_clipped_invalid_renders(bounds):
    with pytest.raises(ValueError):
        solve_center(lambda offset: bounds, [.5, .5], [0, 0])


def test_centering_propagates_selection_change():
    def observe(offset):
        raise RuntimeError("Selection changed")
    with pytest.raises(RuntimeError, match="Selection changed"):
        solve_center(observe, [.5, .5], [0, 0])


def test_centering_adapts_to_subpixel_quantized_offset_response():
    def observe(offset):
        x = round((.5 + .02 * offset[0]) * 512) / 512
        y = round((.5 - .02 * offset[1]) * 512) / 512
        return x - .025, y - .025, x + .025, y + .025
    result = solve_center(observe, [.52, .48], [0, 0])
    bounds = observe(result)
    assert (bounds[0] + bounds[2]) / 2 == pytest.approx(.52, abs=2/512)
    assert (bounds[1] + bounds[3]) / 2 == pytest.approx(.48, abs=2/512)