"""Coverage search is independent of Painter and works with holes and UV islands."""
import random

import pytest

from MBToolkit_3DPainter.features.font_tool.paint_region import painted_rectangle


def test_hole_and_disconnected_regions_never_select_unpainted_center():
    rows = [[1 <= x < 19 and 1 <= y < 19 and not (5 <= x < 15 and 5 <= y < 15)
             for x in range(20)] for y in range(20)]
    bounds = painted_rectangle(rows, (.2, .1))
    left, bottom, right, top = bounds
    assert right > left and top > bottom
    for y in range(round((1 - top) * 20), round((1 - bottom) * 20)):
        for x in range(round(left * 20), round(right * 20)):
            assert rows[y][x]


def test_uv_y_conversion_and_aspect_ratio():
    rows = [[False] * 12 for _ in range(10)]
    for y in range(1, 4):
        for x in range(2, 10):
            rows[y][x] = True
    assert painted_rectangle(rows, (.5, .1)) == pytest.approx((2 / 12, .6, 10 / 12, .9))


def test_rectangle_search_matches_brute_force():
    rng = random.Random(177)
    for _ in range(60):
        rows = [[rng.random() < .7 for _ in range(7)] for _ in range(6)]
        iw, ih = rng.uniform(.1, .5), rng.uniform(.1, .5)
        result = painted_rectangle(rows, (iw, ih))
        measured = min((result[2] - result[0]) / iw, (result[3] - result[1]) / ih)
        best = 0
        for top in range(6):
            for bottom in range(top + 1, 7):
                for left in range(7):
                    for right in range(left + 1, 8):
                        if all(rows[y][x] for y in range(top, bottom) for x in range(left, right)):
                            best = max(best, min((right - left) / 7 / iw, (bottom - top) / 6 / ih))
        assert measured == pytest.approx(best)


@pytest.mark.parametrize("rows,ink", [([], (.2, .1)), ([[False]], (.2, .1)),
                                        ([[True], []], (.2, .1)), ([[True]], (0, .1)),
                                        ([[True]], (float("nan"), .1))])
def test_invalid_or_empty_coverage_is_rejected(rows, ink):
    with pytest.raises(ValueError):
        painted_rectangle(rows, ink)