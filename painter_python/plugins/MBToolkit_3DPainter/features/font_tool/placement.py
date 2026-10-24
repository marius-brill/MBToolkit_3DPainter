"""Bounded, temporary UV coverage measurement using the public texture exporter."""
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
import hashlib
import json
import math
import os
from time import perf_counter

from PySide6 import QtGui, QtCore
import substance_painter as sp
from .centering import solve_center
from .paint_region import painted_rectangle
from .pixels import Coverage


def coverage_value(image, x, y):
    """Composite exported red coverage over black, ignoring transparent RGB."""
    color = image.pixelColor(x, y)
    return color.red() * color.alpha() / 255


def coverage_bounds(image, threshold=8):
    """Return normalized UV bounds from a grayscale coverage image (image Y points down)."""
    if image.isNull() or image.width() > 1024 or image.height() > 1024:
        raise ValueError("Invalid or oversized paint coverage image")
    width, height = image.width(), image.height()
    if hasattr(image, "convertToFormat"):
        try:
            measured = Coverage(image).bounds(threshold)
        except ValueError as exc:
            raise ValueError("No Base Color paint coverage found. Paint on the layer content first.") from exc
        if measured == (0., 0., 1., 1.):
            raise ValueError("Coverage reaches every image edge; use an isolated patch away from tile edges")
        return measured
    left, top, right, bottom = width, height, -1, -1
    for y in range(height):
        for x in range(width):
            if coverage_value(image, x, y) > threshold:
                left, top = min(left, x), min(top, y)
                right, bottom = max(right, x), max(bottom, y)
    if right < left:
        raise ValueError("No Base Color paint coverage found. Paint on the layer content first.")
    if left == 0 and top == 0 and right == width - 1 and bottom == height - 1:
        raise ValueError("Coverage reaches every image edge; cannot distinguish the patch from an opaque export. "
                         "Use a smaller isolated patch away from UV tile edges.")
    return left / width, 1 - (bottom + 1) / height, (right + 1) / width, 1 - top / height


def coverage_overlap(paint, mask, threshold=8):
    """Fraction of measured ink over paint; no dilation or bounding-box proxy."""
    if (paint.isNull() or mask.isNull() or paint.width() != mask.width()
            or paint.height() != mask.height() or not 0 < paint.width() <= 1024
            or not 0 < paint.height() <= 1024):
        raise ValueError("Paint and text coverage images must have matching bounded dimensions")
    ink = covered = 0
    if hasattr(paint, "convertToFormat") and hasattr(mask, "convertToFormat"):
        return Coverage(paint).overlap(Coverage(mask), threshold)
    for y in range(mask.height()):
        for x in range(mask.width()):
            value = coverage_value(mask, x, y)
            if value > threshold:
                ink += value
                if coverage_value(paint, x, y) > threshold:
                    covered += value
    if not ink:
        raise ValueError("Rendered text has no measurable ink")
    return covered / ink


class FitDiagnostics:
    """Best-effort, opt-in local captures; never make fitting depend on disk access."""

    def __init__(self):
        self.root = None
        self.events = []
        if os.environ.get("MBTOOLKIT_FONT_DIAGNOSTICS") == "1":
            try:
                self.root = Path(QtCore.QStandardPaths.writableLocation(
                    QtCore.QStandardPaths.StandardLocation.AppLocalDataLocation)) / "MBToolkit_3DPainter" / "generated"
                self.root.mkdir(parents=True, exist_ok=True)
                for name in ("coverage", "probe", "overlap"):
                    (self.root / f"last-fit-{name}.png").unlink(missing_ok=True)
                self.record(stage="started")
            except Exception as exc:
                self.root = None
                print("MBToolkit Fit diagnostics unavailable:", exc)

    def record(self, **event):
        if self.root is None:
            return
        try:
            self.events.append(event)
            (self.root / "last-fit.json").write_text(json.dumps(self.events, indent=2), encoding="utf-8")
            print("MBToolkit Fit", event)
        except Exception as exc:
            print("MBToolkit Fit diagnostic write failed:", exc)

    def image(self, name, image):
        if self.root is not None:
            try:
                if not image.save(str(self.root / f"last-fit-{name}.png")):
                    raise OSError("PNG save returned false")
            except Exception as exc:
                self.record(diagnostic_error=str(exc))

    def overlap(self, paint, mask):
        if self.root is None:
            return
        try:
            preview = QtGui.QImage(mask.width(), mask.height(), QtGui.QImage.Format.Format_RGB32)
            for y in range(mask.height()):
                for x in range(mask.width()):
                    p, m = coverage_value(paint, x, y), coverage_value(mask, x, y)
                    preview.setPixelColor(x, y, QtGui.QColor(int(m), int(p), 0))
            self.image("overlap", preview)
        except Exception as exc:
            self.record(diagnostic_error=str(exc))


def placement_transform(bounds, padding=0.1):
    """Center a square source inside the UV bounding box without stretching its letters."""
    left, bottom, right, top = bounds
    extent = min(right - left, top - bottom) * (1 - 2 * padding)
    if extent <= 0:
        raise ValueError("Painted area is too small to fit text")
    return [1 / extent, 1 / extent], [(left + right) / 2 - 0.5, (bottom + top) / 2 - 0.5]


def measure_paint_bounds(stack, layer, capture=None):
    """Isolate one root paint layer; always restore visibility/mask and remove exports."""
    if not isinstance(layer, sp.layerstack.PaintLayerNode) or layer.get_parent() is not None:
        raise ValueError("Select a top-level paint layer, not a folder child or Fill layer")
    material = stack.material()
    tiles = material.all_uv_tiles()
    if material.is_layered_material() or len(tiles) > 1 or any(tile.u != 0 or tile.v != 0 for tile in tiles):
        raise ValueError("Fit currently supports a single 0–1 UV tile without material layering")
    if not stack.has_channel(sp.textureset.ChannelType.BaseColor):
        raise ValueError("Add Base Color to this texture set and paint the placement area first")
    roots = sp.layerstack.get_root_layer_nodes(stack)
    visibility = [(node, node.is_visible()) for node in roots]
    mask_enabled = layer.is_mask_enabled() if layer.has_mask() else None
    try:
        for node, _visible in visibility:
            node.set_visible(node.uid() == layer.uid())
        if mask_enabled:
            layer.enable_mask(False)
        with TemporaryDirectory(prefix="mbtoolkit-text-fit-") as directory:
            config = {
                "exportShaderParams": False, "exportPath": Path(directory).as_posix(),
                "defaultExportPreset": "MBTextCoverage",
                "exportPresets": [{"name": "MBTextCoverage", "maps": [{
                    "fileName": "coverage", "channels": [{
                        "destChannel": "R", "srcChannel": "A",
                        "srcMapType": "documentMap", "srcMapName": "baseColor"}],
                    "parameters": {"fileFormat": "png", "bitDepth": "8", "sizeLog2": 9,
                                   "paddingAlgorithm": "transparent", "dilationDistance": 0,
                                   "dithering": False}}]}],
                "exportList": [{"rootPath": str(stack)}]}
            result = sp.export.export_project_textures(config)
            if result.status != sp.export.ExportStatus.Success:
                raise RuntimeError("Paint coverage export did not complete: " + result.message)
            files = list(Path(directory).glob("*.png"))
            if len(files) != 1:
                raise RuntimeError("Expected one paint coverage image")
            image = QtGui.QImage(str(files[0]))
            if capture is not None:
                capture.append(image.copy())
            return coverage_bounds(image)
    finally:
        failures = []
        for node, visible in visibility:
            try:
                node.set_visible(visible)
            except Exception as exc:
                failures.append(str(exc))
        if mask_enabled is not None:
            try:
                layer.enable_mask(mask_enabled)
            except Exception as exc:
                failures.append(str(exc))
        if failures:
            raise RuntimeError("Could not restore layer visibility/mask: " + "; ".join(failures))


def verify_placement(stack, layer, effect, bounds, paint, diagnostics=None):
    """Measure the real mask, not mask-multiplied paint; calibrate before accepting Fit."""
    original = deepcopy(effect.get_projection_parameters())
    identity = (str(stack), layer.uid())
    diagnostics = diagnostics or FitDiagnostics()
    diagnostics.record(stack=str(stack), layer=layer.uid(), effect=effect.uid(), target_bounds=list(bounds),
                       scale=list(original.uv_transformation.scale), seed=list(original.uv_transformation.offset))
    target = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2]
    started = perf_counter()
    paint_pixels = Coverage(paint) if hasattr(paint, "convertToFormat") else None
    try:
        with TemporaryDirectory(prefix="mb-fit-probe-") as directory:
            count = 0
            last_bounds = None
            last_image = None
            working = deepcopy(original)
            last_pixels = None
            export_seconds = 0.

            def observe(offset):
                nonlocal count, last_bounds, last_image, last_pixels, export_seconds
                selected = sp.layerstack.get_selected_nodes(stack)
                if str(sp.textureset.get_active_stack()) != identity[0] or not any(
                        node.uid() in (identity[1], effect.uid()) for node in selected):
                    raise RuntimeError("Selection changed while fitting; placement canceled")
                params = deepcopy(working)
                uv = params.uv_transformation
                uv.offset = list(offset)
                params.uv_transformation = uv
                effect.set_projection_parameters(params)
                readback = effect.get_projection_parameters().uv_transformation.offset
                diagnostics.record(requested_offset=list(offset),
                                   readback=None if readback is None else list(readback))
                if (readback is None or len(readback) != 2
                        or not all(math.isclose(a, b, abs_tol=1e-5) for a, b in zip(offset, readback))):
                    raise RuntimeError("Painter did not retain the requested text offset")
                count += 1
                path = Path(directory) / f"probe-{count}.png"
                options = {"padding": "Transparent", "dilation": 0,
                           "resolution": [512, 512], "keepAlpha": True}
                export_started = perf_counter()
                sp.js.evaluate("alg.mapexport.save(%s, %s, %s)" % (
                    json.dumps([layer.uid(), "mask"]), json.dumps(str(path)), json.dumps(options)))
                export_seconds += perf_counter() - export_started
                image = QtGui.QImage(str(path))
                if image.isNull() or image.width() != 512 or image.height() != 512:
                    raise RuntimeError("Painter did not export the text mask for placement verification")
                last_image = image
                diagnostics.image("probe", image)
                if getattr(diagnostics, "root", None) is not None:
                    diagnostics.record(probe=count, offset=list(offset), readback=list(readback),
                                       sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                last_pixels = Coverage(image) if paint_pixels is not None else None
                measured = last_pixels.bounds() if last_pixels is not None else coverage_bounds(image)
                last_bounds = measured
                diagnostics.record(probe=count, bounds=list(measured))
                return measured

            region = bounds
            seed = list(original.uv_transformation.offset)
            for attempt in range(4):
                offset = solve_center(observe, target, seed)
                diagnostics.overlap(paint, last_image)
                overlap = paint_pixels.overlap(last_pixels) if paint_pixels is not None else coverage_overlap(paint, last_image)
                diagnostics.record(attempt=attempt, ink_overlap=overlap)
                tolerance = 2 / 512
                contained = (last_bounds[0] >= region[0] - tolerance
                             and last_bounds[1] >= region[1] - tolerance
                             and last_bounds[2] <= region[2] + tolerance
                             and last_bounds[3] <= region[3] + tolerance)
                if overlap >= .98 and contained:
                    diagnostics.record(exports=count, export_seconds=export_seconds,
                                       total_seconds=perf_counter() - started)
                    # The final observation has written and independently verified this offset.
                    return offset
                if attempt == 3:
                    raise ValueError(f"Could not fit readable text on the paint: {overlap:.1%} overlap. "
                                     "Paint a broader solid patch; no placement was committed.")
                ink = (last_bounds[2] - last_bounds[0], last_bounds[3] - last_bounds[1])
                if attempt == 0:
                    rows = paint_pixels.rows() if paint_pixels is not None else [[bounds[0] <= (x + .5) / paint.width() <= bounds[2]
                             and bounds[1] <= 1 - (y + .5) / paint.height() <= bounds[3]
                             and coverage_value(paint, x, y) > 8 for x in range(paint.width())]
                            for y in range(paint.height())]
                    region = painted_rectangle(rows, ink, target)
                target = [(region[0] + region[2]) / 2, (region[1] + region[3]) / 2]
                factor = min((region[2] - region[0]) / ink[0],
                             (region[3] - region[1]) / ink[1]) * (.8 if attempt == 0 else .65)
                # Never enlarge during recovery, nor silently accept subpixel text.
                factor = min(factor, .9)
                if min(ink) * factor * 512 < 4:
                    raise ValueError("Paint is too narrow for readable text at the 512px fitting resolution")
                working = deepcopy(effect.get_projection_parameters())
                uv = working.uv_transformation
                uv.scale = [v / factor for v in uv.scale]
                working.uv_transformation = uv
                seed = offset
                diagnostics.record(recovery_region=list(region), resize_factor=factor,
                                   scale=list(uv.scale), target=target)
    except Exception:
        effect.set_projection_parameters(original)
        raise