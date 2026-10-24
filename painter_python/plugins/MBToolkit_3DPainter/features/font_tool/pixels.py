"""Owned, row-packed red-times-alpha coverage buffers (no per-pixel Qt calls)."""
from PySide6 import QtGui


class Coverage:
    def __init__(self, image):
        self.width, self.height = image.width(), image.height()
        if image.isNull() or not 0 < self.width <= 4096 or not 0 < self.height <= 4096:
            raise ValueError("Invalid or oversized coverage image")
        if image.format() == QtGui.QImage.Format.Format_Grayscale8:
            raw, stride = bytes(image.constBits()), image.bytesPerLine()
            self.data = b"".join(raw[y * stride:y * stride + self.width] for y in range(self.height))
            return
        # Keep the converted image alive until the buffer has been copied.
        converted = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
        raw, stride = bytes(converted.constBits()), converted.bytesPerLine()
        rows = []
        opaque = not converted.hasAlphaChannel() or all(raw[i] == 255 for i in range(3, len(raw), 4))
        for y in range(self.height):
            row = raw[y * stride:y * stride + self.width * 4]
            if opaque:
                rows.append(row[::4])
            else:
                # Ceiling preserves the original value > integer-threshold decision.
                rows.append(bytes((row[i] * row[i + 3] + 254) // 255 for i in range(0, len(row), 4)))
        self.data = b"".join(rows)

    def bounds(self, threshold=8):
        # bytes.translate runs thresholding in C; find/rfind scan each row in C.
        binary = self.data.translate(bytes(255 if i > threshold else 0 for i in range(256)))
        left, top, right, bottom = self.width, self.height, -1, -1
        for y in range(self.height):
            row = binary[y * self.width:(y + 1) * self.width]
            first = row.find(b"\xff")
            if first >= 0:
                left, right = min(left, first), max(right, row.rfind(b"\xff"))
                top, bottom = min(top, y), y
        if right < left:
            raise ValueError("No measurable ink in coverage image")
        return left / self.width, 1 - (bottom + 1) / self.height, (right + 1) / self.width, 1 - top / self.height

    def overlap(self, mask, threshold=8):
        if (self.width, self.height) != (mask.width, mask.height):
            raise ValueError("Coverage dimensions do not match")
        ink = covered = 0
        for p, m in zip(self.data, mask.data):
            if m > threshold:
                ink += m
                if p > threshold:
                    covered += m
        if not ink:
            raise ValueError("Rendered text has no measurable ink")
        return covered / ink

    def rows(self, threshold=8):
        binary = self.data.translate(bytes(int(i > threshold) for i in range(256)))
        return [binary[y * self.width:(y + 1) * self.width] for y in range(self.height)]