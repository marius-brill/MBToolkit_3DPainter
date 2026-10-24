"""Bounded render-measured centering without assumptions about UV offset direction."""
import math


def solve_center(observe, target, seed, tolerance=2 / 512, budget=32):
    """Observe(offset) returns unclipped UV ink bounds; no guessed success fallback."""
    calls = 0

    def sample(offset):
        nonlocal calls
        calls += 1
        if calls > budget:
            raise ValueError("Text placement exceeded its render budget")
        if not all(math.isfinite(v) and abs(v) <= 64 for v in offset):
            raise ValueError("Text placement requested an unsafe offset")
        bounds = observe(list(offset))
        if len(bounds) != 4 or not all(math.isfinite(v) for v in bounds):
            raise ValueError("Invalid rendered text bounds")
        left, bottom, right, top = bounds
        if not (0 < left < right < 1 and 0 < bottom < top < 1):
            raise ValueError("Rendered text is empty or clipped by the tile")
        return ((left + right) / 2, (bottom + top) / 2), (right - left, top - bottom)

    # Identity offset usually exposes the font even when the guessed seed is off-tile.
    current = None
    for candidate in (seed, [0., 0.]):
        try:
            center, extent = sample(candidate)
            current = list(candidate)
            break
        except ValueError:
            pass
    if current is None:
        raise ValueError("Cannot locate unclipped rendered text; no placement was committed")
    columns = None
    for _ in range(5):
        error = [target[i] - center[i] for i in range(2)]
        # Even a centered seed needs a responsive probe, to reject stale exports.
        recalibrate = columns is None
        if recalibrate:
            columns = []
        for axis in range(2) if recalibrate else ():
            column = None
            for delta in (.04, -.04, .12, -.12, .3, -.3):
                probe = list(current)
                probe[axis] += delta
                try:
                    measured, size = sample(probe)
                except ValueError:
                    continue
                if any(abs(size[i] - extent[i]) > max(.008, extent[i] * .08) for i in range(2)):
                    continue
                movement = [measured[i] - center[i] for i in range(2)]
                if max(abs(v) for v in movement) >= 1 / 512:
                    column = [v / delta for v in movement]
                    break
            if column is None:
                raise ValueError("Text render did not respond reliably to offset probes")
            columns.append(column)
        a, c = columns[0]
        b, d = columns[1]
        determinant = a * d - b * c
        if abs(determinant) < 1e-8:
            raise ValueError("Cannot calibrate text projection offset")
        correction = [(d * error[0] - b * error[1]) / determinant,
                      (-c * error[0] + a * error[1]) / determinant]
        current = [current[i] + correction[i] for i in range(2)]
        previous_center = center
        center, size = sample(current)
        if any(abs(size[i] - extent[i]) > max(.008, extent[i] * .08) for i in range(2)):
            raise ValueError("Text became clipped during placement")
        if max(abs(center[i] - target[i]) for i in range(2)) <= tolerance:
            # Independent repeat rejects one-off stale success observations.
            verified, verified_size = sample(current)
            if (max(abs(verified[i] - target[i]) for i in range(2)) <= tolerance
                    and all(abs(verified_size[i] - size[i]) <= max(.008, size[i] * .08)
                            for i in range(2))):
                return current
        # Reuse the local Jacobian only while observations agree with its prediction.
        if max(abs(center[i] - previous_center[i] - error[i]) for i in range(2)) > tolerance * 2:
            columns = None
        extent = size
    raise ValueError("Rendered text did not converge on the painted area")