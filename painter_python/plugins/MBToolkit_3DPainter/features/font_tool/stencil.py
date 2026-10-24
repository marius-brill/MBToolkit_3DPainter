"""Painter-native text-mask export; no font files or user-mask edits."""
import hashlib
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6 import QtCore, QtGui
import substance_painter as sp
from .pixels import Coverage
from .paint_region import painted_rectangle
from .centering import solve_center


def export_mask(layer, path):
    """Export an individual layer mask using the documented JS UID path."""
    # Omit optional dithering: some Painter builds reject the documented spelling.
    options = {"padding": "Transparent", "dilation": 0, "resolution": [2048, 2048], "keepAlpha": True}
    sp.js.evaluate("alg.mapexport.save(%s, %s, %s)" % (
        json.dumps([layer.uid(), "mask"]), json.dumps(str(path)), json.dumps(options)))
    image = QtGui.QImage(str(path))
    if image.isNull() or image.width() != 2048 or image.height() != 2048:
        raise RuntimeError("Painter did not export a valid 2048px text mask")
    opaque = QtGui.QImage(2048, 2048, QtGui.QImage.Format.Format_RGB32)
    opaque.fill(QtCore.Qt.GlobalColor.black)
    painter = QtGui.QPainter(opaque)
    try:
        painter.drawImage(0, 0, image)
    finally:
        painter.end()
    return opaque.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)


def verify_full_coverage(image):
    """Reject contexts where export clips the procedural mask to UV islands."""
    data, stride = bytes(image.constBits()), image.bytesPerLine()
    for y in range(image.height()):
        if min(data[y * stride:y * stride + image.width()]) < 250:
            raise ValueError("Painter's mask export does not cover the full square in this context. "
                             "Stencil generation stopped to avoid UV-clipped lettering.")


def usable_region(image):
    """Conservatively pool coverage: every pixel in each cell must be covered."""
    pixels = Coverage(image)
    step = max(1, pixels.width // 256)
    rows = []
    for y in range(0, pixels.height - step + 1, step):
        row = bytearray()
        for x in range(0, pixels.width - step + 1, step):
            row.append(all(min(pixels.data[yy * pixels.width + x:yy * pixels.width + x + step]) >= 250
                           for yy in range(y, y + step)))
        rows.append(row)
    region = painted_rectangle(rows, (1, 1))
    # Account for any discarded partial cells on non-power-of-two test images.
    sx, sy = len(rows[0]) * step / pixels.width, len(rows) * step / pixels.height
    region = (region[0] * sx, 1 - (1 - region[1]) * sy,
              region[2] * sx, 1 - (1 - region[3]) * sy)
    extent = min(region[2] - region[0], region[3] - region[1]) * .7
    if extent * pixels.width < 128:
        raise ValueError("The mesh has no covered region large enough for a sharp stencil (128px minimum). "
                         "Use a texture set with a larger solid UV island.")
    return region, extent


def place_stencil_source(layer, effect, image, directory):
    """Fit the whole white source square, not potentially clipped text glyphs."""
    region, extent = usable_region(image)
    target = [(region[0] + region[2]) / 2, (region[1] + region[3]) / 2]
    projection = effect.get_projection_parameters()
    uv = projection.uv_transformation
    uv.scale = [1 / extent, 1 / extent]
    projection.uv_transformation = uv
    last = [None]
    count = 0
    def observe(offset):
        nonlocal count
        count += 1
        if count > 64:
            raise ValueError("Stencil placement exceeded its render budget")
        uv.offset = offset
        projection.uv_transformation = uv
        effect.set_projection_parameters(projection)
        actual = effect.get_projection_parameters().uv_transformation.offset
        if actual is None or any(abs(a - b) > 1e-5 for a, b in zip(actual, offset)):
            raise RuntimeError("Painter did not retain the stencil offset")
        path = Path(directory) / f"source-{count}.png"
        pixels = Coverage(export_mask(layer, path))
        bounds = pixels.bounds(250)
        if any(abs(bounds[i + 2] - bounds[i] - extent) > 4 / 2048 for i in range(2)):
            raise ValueError("The stencil source square is clipped by UV coverage")
        # Bounds alone cannot detect a hole inside the source square.
        left, right = round(bounds[0] * pixels.width) + 2, round(bounds[2] * pixels.width) - 2
        top, bottom = round((1 - bounds[3]) * pixels.height) + 2, round((1 - bounds[1]) * pixels.height) - 2
        if any(min(pixels.data[y * pixels.width + left:y * pixels.width + right]) < 250
               for y in range(top, bottom)):
            raise ValueError("UV coverage has a hole inside the stencil source")
        last[0] = bounds
        return bounds
    delta = [v - .5 for v in target]
    # Seeds only locate a complete square; acceptance always uses measured calibration.
    seeds = [[0., 0.]] + [[sx * delta[0] * factor, sy * delta[1] * factor]
                          for factor in (1, 1 / extent, extent) for sx in (1, -1) for sy in (1, -1)]
    for seed in seeds:
        try:
            solve_center(observe, target, seed, tolerance=2 / 2048, budget=16)
            return last[0]
        except ValueError:
            if count >= 64:
                break
    raise ValueError("Could not place a complete stencil source on this mesh's UV islands; "
                     "no clipped stencil was imported.")


def centered_image(image):
    """Center actual rendered ink on black with 10% padding, without rotation."""
    width, height = image.width(), image.height()
    data, stride = bytes(image.constBits()), image.bytesPerLine()
    left, top, right, bottom = width, height, -1, -1
    for y in range(height):
        row = data[y * stride:y * stride + width]
        xs = [x for x, value in enumerate(row) if value > 8]
        if xs:
            left, top = min(left, xs[0]), min(top, y)
            right, bottom = max(right, xs[-1]), max(bottom, y)
    if right < left:
        raise ValueError("Painter rendered empty text; check the font and text characters")
    if left == 0 or top == 0 or right == width - 1 or bottom == height - 1:
        raise ValueError("Painter text reaches the export edge; refusing a potentially clipped stencil")
    cropped = image.copy(left, top, right - left + 1, bottom - top + 1)
    fitted = cropped.scaled(1638, 1638, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                            QtCore.Qt.TransformationMode.SmoothTransformation)
    result = QtGui.QImage(2048, 2048, QtGui.QImage.Format.Format_RGB32)
    result.fill(QtCore.Qt.GlobalColor.black)
    painter = QtGui.QPainter(result)
    try:
        painter.drawImage((2048 - fitted.width()) // 2, (2048 - fitted.height()) // 2, fitted)
    finally:
        painter.end()
    return result.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)


def render_text(resource, text, line_spacing, character_spacing):
    """Render the exact resource with SourceFont and always delete our scratch layer."""
    stack = sp.textureset.get_active_stack()
    if stack is None:
        raise ValueError("Select an active texture set before making a stencil")
    selection = sp.layerstack.get_selected_nodes(stack)
    selection_types = [(node, sp.layerstack.get_selection_type(node)) for node in selection
                       if isinstance(node, sp.layerstack.LayerNode)]
    layer = None
    try:
        layer = sp.layerstack.insert_fill(sp.layerstack.InsertPosition.from_textureset_stack(stack))
        layer.set_name("MB Stencil render (temporary)")
        layer.add_mask(sp.layerstack.MaskBackground.Black)
        effect = sp.layerstack.insert_fill(sp.layerstack.InsertPosition.inside_node(
            layer, sp.layerstack.NodeStack.Mask))
        source = effect.set_source(None, resource.identifier())
        params = source.get_parameters()
        params.auto_size = True
        params.horizontal_alignment = sp.source.HorizontalAlignment.Center
        params.vertical_alignment = sp.source.VerticalAlignment.Middle
        params.offset = (0, 0)
        params.line_spacing = line_spacing
        params.character_spacing = character_spacing
        params.color = sp.colormanagement.Color(1, 1, 1)
        params.background_opacity = 1
        params.resolution = sp.source.ResolutionOverride(sp.source.ResolutionMode.Custom, (2048, 2048))
        effect.set_projection_mode(sp.layerstack.ProjectionMode.UV)
        effect.set_projection_parameters(sp.layerstack.UVProjectionParams(
            uv_wrapping_mode=sp.layerstack.UVWrapMode.RepeatNone,
            uv_transformation=sp.layerstack.UVTransformationParams(
                scale_mode=sp.layerstack.ScaleMode.Factors, scale=[1.25, 1.25], rotation=0, offset=[0, 0])))
        with TemporaryDirectory(prefix="mb-stencil-") as directory:
            path = Path(directory) / "mask.png"
            # Probe at identity scale so the white background covers the full tile.
            projection = effect.get_projection_parameters()
            uv = projection.uv_transformation
            uv.scale = [1, 1]
            projection.uv_transformation = uv
            effect.set_projection_parameters(projection)
            params.text = text
            params.background_color = sp.colormanagement.Color(1, 1, 1)
            source.set_parameters(params)
            coverage = export_mask(layer, path)
            try:
                verify_full_coverage(coverage)
                source_bounds = None
            except ValueError:
                source_bounds = place_stencil_source(layer, effect, coverage, directory)
            path.unlink()
            if source_bounds is None:
                uv.scale = [1.25, 1.25]
                projection.uv_transformation = uv
                effect.set_projection_parameters(projection)
            params.text = text
            params.background_color = sp.colormanagement.Color(0, 0, 0)
            source.set_parameters(params)
            rendered = export_mask(layer, path)
            if source_bounds is not None:
                left, bottom, right, top = source_bounds
                # The entire source was verified before changing white to black.
                # Crop to that square to ignore unrelated exported pixels.
                x, y = round(left * 2048), round((1 - top) * 2048)
                rendered = rendered.copy(x, y, round((right - left) * 2048), round((top - bottom) * 2048))
                # Auto-sized glyphs may legitimately touch the source texture border.
                # The white-square probe proved this whole texture was exported.
                padded = QtGui.QImage(rendered.width() + 4, rendered.height() + 4,
                                      QtGui.QImage.Format.Format_RGB32)
                padded.fill(QtCore.Qt.GlobalColor.black)
                painter = QtGui.QPainter(padded)
                try:
                    painter.drawImage(2, 2, rendered)
                finally:
                    painter.end()
                rendered = padded.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
            return centered_image(rendered)
    finally:
        failures = []
        if layer is not None:
            try:
                sp.layerstack.delete_node(layer)
            except Exception as exc:
                failures.append("delete temporary layer: " + str(exc))
        try:
            sp.layerstack.set_selected_nodes(selection)
            for node, kind in selection_types:
                sp.layerstack.set_selection_type(node, kind)
        except Exception as exc:
            failures.append("restore selection: " + str(exc))
        if failures:
            raise RuntimeError("Stencil cleanup failed: " + "; ".join(failures))


def retain_image(image):
    """Atomically retain the import source, including after import returns."""
    data = QtCore.QByteArray()
    buffer = QtCore.QBuffer(data)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    try:
        if not image.save(buffer, "PNG"):
            raise RuntimeError("Could not encode stencil PNG")
    finally:
        buffer.close()
    digest = hashlib.sha256(bytes(data)).hexdigest()
    directory = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.AppLocalDataLocation)
    if not directory:
        raise RuntimeError("No writable application-local data directory")
    path = Path(directory) / "MBToolkit_3DPainter" / "generated" / f"MB_Text_{digest}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    output = QtCore.QSaveFile(str(path))
    if not output.open(QtCore.QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Could not save stencil: " + output.errorString())
    if output.write(data) != data.size() or not output.commit():
        output.cancelWriting()
        raise RuntimeError("Could not finish saving stencil: " + output.errorString())
    return path


def create_stencil(resource, text, line_spacing, character_spacing):
    if not sp.project.is_open():
        raise ValueError("Open a Painter project before making a stencil")
    if not text.strip():
        raise ValueError("Enter non-empty text before making a stencil")
    if len(text) > 10000 or len(text.splitlines()) > 256:
        raise ValueError("Stencil text exceeds the 10000 character / 256 line limit")
    if (not math.isfinite(line_spacing) or not 0 <= line_spacing <= 10
            or not math.isfinite(character_spacing) or not -2 <= character_spacing <= 10):
        raise ValueError("Invalid text spacing")
    image = render_text(resource, text, line_spacing, character_spacing)
    saved = retain_image(image)
    return sp.resource.import_project_resource(str(saved), sp.resource.Usage.ALPHA, saved.stem)