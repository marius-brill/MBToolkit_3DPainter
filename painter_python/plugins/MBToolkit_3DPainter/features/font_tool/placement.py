"""Bounded, temporary UV coverage measurement using the public texture exporter."""
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6 import QtGui
import substance_painter as sp


def coverage_bounds(image, threshold=8):
    """Return normalized UV bounds from a grayscale coverage image (image Y points down)."""
    if image.isNull() or image.width() > 1024 or image.height() > 1024:
        raise ValueError("Invalid or oversized paint coverage image")
    width, height = image.width(), image.height()
    left, top, right, bottom = width, height, -1, -1
    for y in range(height):
        for x in range(width):
            if image.pixelColor(x, y).red() > threshold:
                left, top = min(left, x), min(top, y)
                right, bottom = max(right, x), max(bottom, y)
    if right < left:
        raise ValueError("No Base Color paint coverage found. Paint on the layer content first.")
    if left == 0 and top == 0 and right == width - 1 and bottom == height - 1:
        raise ValueError("Coverage reaches every image edge; cannot distinguish the patch from an opaque export. "
                         "Use a smaller isolated patch away from UV tile edges.")
    return left / width, 1 - (bottom + 1) / height, (right + 1) / width, 1 - top / height


def placement_transform(bounds, padding=0.1):
    """Center a square source inside the UV bounding box without stretching its letters."""
    left, bottom, right, top = bounds
    extent = min(right - left, top - bottom) * (1 - 2 * padding)
    if extent <= 0:
        raise ValueError("Painted area is too small to fit text")
    return [1 / extent, 1 / extent], [(left + right) / 2 - 0.5, (bottom + top) / 2 - 0.5]


def measure_paint_bounds(stack, layer):
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
            return coverage_bounds(QtGui.QImage(str(files[0])))
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