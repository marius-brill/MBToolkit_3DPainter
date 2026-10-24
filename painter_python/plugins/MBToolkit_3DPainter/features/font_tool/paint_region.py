"""Linear-time painted-rectangle search; no bounding-box containment assumptions."""
import math


def painted_rectangle(rows, ink_size, preferred=(.5, .5)):
    """Find a solid rectangle maximizing the scale of a given ink aspect ratio.

    Rows contain booleans in image coordinates. Return normalized UV bounds.
    A histogram stack visits every pixel once, including disconnected regions.
    Equal-sized fits prefer the location nearest the original patch center.
    """
    iw, ih = ink_size
    if not all(math.isfinite(v) and v > 0 for v in (iw, ih)):
        raise ValueError("Cannot fit text with invalid ink dimensions")
    height = len(rows)
    width = len(rows[0]) if height else 0
    if not width or any(len(row) != width for row in rows):
        raise ValueError("Paint coverage must be a nonempty rectangular grid")
    histogram = [0] * (width + 1)
    best = None
    best_score = (-1., -float("inf"))
    for y, row in enumerate(rows):
        for x, covered in enumerate(row):
            histogram[x] = histogram[x] + 1 if covered else 0
        stack = []
        for x in range(width + 1):
            start = x
            while stack and stack[-1][1] > histogram[x]:
                left, h = stack.pop()
                start = left
                bounds = (left / width, 1 - (y + 1) / height,
                          x / width, 1 - (y + 1 - h) / height)
                factor = min((x - left) / width / iw, h / height / ih)
                center = ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
                score = (factor, -sum((a - b) ** 2 for a, b in zip(center, preferred)))
                if score > best_score:
                    best, best_score = bounds, score
            if histogram[x] and (not stack or stack[-1][1] < histogram[x]):
                stack.append((start, histogram[x]))
    if best is None:
        raise ValueError("No solid painted region is available for text")
    return best