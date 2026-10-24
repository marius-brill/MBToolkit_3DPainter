"""Non-cumulative relative sizing around a native auto-sized UV projection."""
from copy import deepcopy
import math
import hashlib


def size_factor(value):
    if not math.isfinite(value) or not -1 <= value <= 1:
        raise ValueError("Relative size must be between -1 and +1")
    return 4 ** value


def metadata_key(stack, uid):
    return "relative_size_" + hashlib.sha256(f"{stack}:{uid}".encode()).hexdigest()


def read_state(metadata, key):
    if key not in metadata.list():
        return None
    data = metadata.get(key)
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Invalid relative size metadata")
    baseline, value = data.get("baseline"), data.get("value")
    if not isinstance(baseline, list) or len(baseline) != 2 or not all(
            isinstance(v, (float, int)) and math.isfinite(v) and v != 0 for v in baseline):
        raise ValueError("Invalid relative size baseline")
    size_factor(value)
    return baseline, value


def write_state(metadata, key, state):
    baseline, value = state
    metadata.set(key, {"version": 1, "baseline": list(baseline), "value": value})


def scaled_projection(params, value, previous=None):
    """Return projection and baseline; compensate for edits made outside this control.

    Painter UV scale represents tiling, so larger lettering needs smaller factors.
    Only scale is changed: all other projection fields are copied unchanged.
    """
    factor = size_factor(value)
    uv = params.uv_transformation
    scale = uv.scale
    if scale is None or len(scale) != 2 or not all(math.isfinite(v) and v != 0 for v in scale):
        raise ValueError("Relative sizing requires valid non-zero UV scale factors")
    baseline = list(scale)
    if previous is not None:
        old_baseline, old_value = previous
        old_factor = size_factor(old_value)
        # Rebase external scale changes while retaining the previous relative amount.
        baseline = [v * old_factor for v in scale]
        if all(math.isclose(v, b / old_factor, rel_tol=1e-6, abs_tol=1e-9)
               for v, b in zip(scale, old_baseline)):
            baseline = list(old_baseline)
    result = deepcopy(params)
    transform = result.uv_transformation
    transform.scale = [v / factor for v in baseline]
    result.uv_transformation = transform
    return result, (baseline, value)