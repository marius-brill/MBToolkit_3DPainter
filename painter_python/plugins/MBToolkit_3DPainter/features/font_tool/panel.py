"""Paintable text with a non-destructive SourceFont mask."""
from copy import deepcopy

from PySide6 import QtWidgets, QtCore
import substance_painter as sp
from ...adapters.painter import available_font_resources, selected_single_layer
from ...ui.common import error
from ...adapters.painter import active_stack
from .placement import measure_paint_bounds, placement_transform
from . import controls


class Panel(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.resources = []
        self._transform_originals = {}
        self._selected_identity = None
        self._loading = False
        controls.build(self)
        self._selection_timer = QtCore.QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(120)
        self._selection_timer.timeout.connect(self._sync_selection)
        self.app.events.add(self.request_refresh)
        self.request_refresh()

    def refresh(self):
        try:
            self.resources = available_font_resources()
            self._filter(self.search.text())
            self.request_refresh()
        except Exception as exc:
            error(self, "Font resources", exc)

    def request_refresh(self):
        self._selection_timer.start()

    def _sync_selection(self):
        if self._loading:
            return
        try:
            node, _source = self._selected_source()
            identity = (str(active_stack()), node.uid())
        except (ValueError, RuntimeError, AttributeError):
            self._selected_identity = None
            self.update_button.setEnabled(False)
            self.rotation.setEnabled(False)
            self.rotation_degrees.setEnabled(False)
            self.status.setText("Paint an area, then Fit")
            return
        self.update_button.setEnabled(True)
        self.rotation.setEnabled(True)
        self.rotation_degrees.setEnabled(True)
        if identity == self._selected_identity:
            return
        self._selected_identity = identity
        self._loading = True
        try:
            self.load_selected()
            self.status.setText("Editing selected text mask")
        finally:
            self._loading = False

    def _auto_size_changed(self, enabled):
        self.size.setEnabled(not enabled)
        self.size_slider.setEnabled(not enabled)

    def _size_slider_changed(self, value):
        controls.silently(self.size, controls.size_from_slider(value))

    def _size_number_changed(self, value):
        controls.silently(self.size_slider, controls.slider_from_size(value))

    def _filter(self, text):
        previous = self.font.currentData()
        self.font.clear()
        for i, res in enumerate(self.resources):
            name = res.gui_name()
            if text.casefold() in name.casefold():
                self.font.addItem(name, i)
        if previous is not None:
            index = self.font.findData(previous)
            if index >= 0:
                self.font.setCurrentIndex(index)

    def _selected_source(self):
        _stack, node = selected_single_layer()
        if isinstance(node, sp.layerstack.FillEffectNode):
            parent = node.get_parent()
            if isinstance(parent, sp.layerstack.PaintLayerNode) and any(
                    effect.uid() == node.uid() for effect in parent.mask_effects()):
                source = node.get_source()
                if isinstance(source, sp.source.SourceFont):
                    return node, source
        if isinstance(node, sp.layerstack.PaintLayerNode):
            matches = []
            for effect in node.mask_effects():
                if isinstance(effect, sp.layerstack.FillEffectNode):
                    source = effect.get_source()
                    if isinstance(source, sp.source.SourceFont):
                        matches.append((effect, source))
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError("Multiple text masks found; select the specific text Fill effect")
        raise ValueError("Select a paint layer with a text mask, or its text mask Fill effect. "
                         "Old Base Color text fill layers are not paintable text masks.")

    def load_selected(self):
        try:
            node, source = self._selected_source()
            self.search.clear()
            self.refresh()
            match = next((i for i, resource in enumerate(self.resources)
                          if resource.identifier() == source.resource_id), None)
            if match is not None:
                idx = self.font.findData(match)
                if idx >= 0:
                    self.font.setCurrentIndex(idx)
            params = source.get_parameters()
            self.text.setPlainText(params.text or "")
            self.auto_size.setChecked(params.auto_size)
            if params.size is not None:
                self.size.setValue(params.size)
            h = self.halign.findText(params.horizontal_alignment.name)
            if h >= 0:
                self.halign.setCurrentIndex(h)
            self.line_spacing.setValue(params.line_spacing)
            self.char_spacing.setValue(params.character_spacing)
        except Exception as exc:
            error(self, "Read text source", exc)
            return
        # Optional transform controls must not break the existing text-loading workflow.
        try:
            self._load_rotation(node)
        except Exception as exc:
            self.rotation.setToolTip("Rotation unavailable: " + str(exc))

    def _set_rotation_controls(self, degrees):
        """Display projection rotation without writing it back or rounding the source."""
        degrees = round(degrees if -180 <= degrees <= 180 else (degrees + 180) % 360 - 180)
        for widget in (self.rotation, self.rotation_degrees):
            blocked = widget.blockSignals(True)
            try:
                widget.setValue(degrees)
            finally:
                widget.blockSignals(blocked)

    def _load_rotation(self, node):
        params = node.get_projection_parameters()
        if params is not None and hasattr(params, "uv_transformation"):
            self._set_rotation_controls(params.uv_transformation.rotation or 0)

    def _selected_uv_projection(self):
        node, _source = self._selected_source()
        if node.get_projection_mode() != sp.layerstack.ProjectionMode.UV:
            raise ValueError("Rotation and flip currently support UV-projected text masks only. "
                             "Use Painter's projection controls for other projection modes.")
        params = node.get_projection_parameters()
        if params is None or params.uv_transformation is None:
            raise ValueError("Selected text mask has no editable UV transformation")
        return node, params

    def rotate_selected(self, degrees):
        node = original = None
        try:
            node, params = self._selected_uv_projection()
            original = deepcopy(params)
            self._remember_transform(node, original)
            params.uv_transformation.rotation = degrees % 360
            node.set_projection_parameters(params)
            self._set_rotation_controls(degrees)
        except Exception as exc:
            exc = self._restore_failed_transform(node, original, exc)
            error(self, "Rotate text mask", exc)

    def flip_selected(self, axis):
        node = original = None
        try:
            if axis not in (0, 1):
                raise ValueError("Flip axis must be horizontal or vertical")
            node, params = self._selected_uv_projection()
            uv = params.uv_transformation
            if uv.scale_mode != sp.layerstack.ScaleMode.Factors:
                raise ValueError("Set the text mask's UV scale mode to Tiling before flipping")
            if uv.scale is None or len(uv.scale) != 2 or not all(uv.scale):
                raise ValueError("Selected text mask has no valid UV scale to flip")
            original = deepcopy(params)
            self._remember_transform(node, original)
            scale = list(uv.scale)
            scale[axis] = -scale[axis]
            uv.scale = scale
            node.set_projection_parameters(params)
        except Exception as exc:
            exc = self._restore_failed_transform(node, original, exc)
            error(self, "Flip text mask", exc)

    def _remember_transform(self, node, params):
        # One small snapshot per edited mask, scoped to this panel instance.
        self._transform_originals.setdefault(node.uid(), deepcopy(params))

    def _restore_failed_transform(self, node, original, exc):
        if node is not None and original is not None:
            try:
                node.set_projection_parameters(original)
                self._set_rotation_controls(original.uv_transformation.rotation or 0)
            except Exception as restore_exc:
                return RuntimeError(f"{exc}. Could not restore text transform: {restore_exc}")
        return exc

    def reset_selected_transform(self):
        try:
            node, params = self._selected_uv_projection()
            original = self._transform_originals.get(node.uid())
            if original is not None:
                params = deepcopy(original)
            else:
                uv = params.uv_transformation
                if uv.scale_mode != sp.layerstack.ScaleMode.Factors:
                    raise ValueError("Reset currently supports Tiling scale mode only")
                uv.rotation = 0
                if uv.scale is not None:
                    uv.scale = [abs(value) for value in uv.scale]
            node.set_projection_parameters(params)
            self._set_rotation_controls(params.uv_transformation.rotation or 0)
        except Exception as exc:
            error(self, "Reset text transform", exc)

    def _apply_params(self, source, params=None):
        if params is None:
            params = source.get_parameters()
        params.text = self.text.toPlainText()
        params.auto_size = self.auto_size.isChecked()
        if not params.auto_size:
            params.size = self.size.value()
        params.horizontal_alignment = getattr(sp.source.HorizontalAlignment, self.halign.currentText())
        params.line_spacing = self.line_spacing.value()
        params.character_spacing = self.char_spacing.value()
        params.color = sp.colormanagement.Color(1, 1, 1)
        params.background_color = sp.colormanagement.Color(0, 0, 0)
        params.background_opacity = 1.0
        source.set_parameters(params)

    def prepare_area(self):
        layer = None
        try:
            stack = active_stack()
            if stack is None:
                raise ValueError("Open a Painter project first")
            if not stack.has_channel(sp.textureset.ChannelType.BaseColor):
                raise ValueError("Add Base Color to this texture set before preparing a text area")
            layer = sp.layerstack.insert_paint(sp.layerstack.InsertPosition.from_textureset_stack(stack))
            layer.set_name("MB Text Area: paint here, then Fit")
            sp.layerstack.set_selected_nodes([layer])
            sp.layerstack.set_selection_type(layer, sp.layerstack.SelectionType.Content)
        except Exception as exc:
            if layer is not None:
                try:
                    sp.layerstack.delete_node(layer)
                except Exception as cleanup_exc:
                    exc = RuntimeError(f"{exc}. Could not remove incomplete paint layer: {cleanup_exc}")
            error(self, "Prepare text area", exc)

    def fit_painted_area(self):
        layer = None
        added_mask = False
        try:
            if not self.text.toPlainText().strip():
                raise ValueError("Enter non-empty text before fitting a text mask")
            index = self.font.currentData()
            if index is None:
                self.refresh()
                index = self.font.currentData()
            if index is None:
                raise ValueError("Choose an available Painter font first")
            stack, layer = selected_single_layer()
            if not isinstance(layer, sp.layerstack.PaintLayerNode):
                raise ValueError("Select the painted area's paint layer before fitting")
            if layer.has_mask():
                raise ValueError("Fit requires an unmasked paint layer so existing masks are never replaced. "
                                 "Select the text layer and use Update text for previously fitted text.")
            bounds = measure_paint_bounds(stack, layer)
            scale, offset = placement_transform(bounds)
            layer.add_mask(sp.layerstack.MaskBackground.Black)
            added_mask = True
            effect = sp.layerstack.insert_fill(sp.layerstack.InsertPosition.inside_node(
                layer, sp.layerstack.NodeStack.Mask))
            effect.set_name("MB Text Mask")
            source = effect.set_source(None, self.resources[index].identifier())
            self._apply_params(source)
            params = source.get_parameters()
            params.auto_size = True
            params.horizontal_alignment = sp.source.HorizontalAlignment.Center
            params.vertical_alignment = sp.source.VerticalAlignment.Middle
            params.offset = (0, 0)
            source.set_parameters(params)
            effect.set_projection_mode(sp.layerstack.ProjectionMode.UV)
            effect.set_projection_parameters(sp.layerstack.UVProjectionParams(
                uv_wrapping_mode=sp.layerstack.UVWrapMode.RepeatNone,
                uv_transformation=sp.layerstack.UVTransformationParams(
                    scale_mode=sp.layerstack.ScaleMode.Factors, scale=scale, rotation=0, offset=offset)))
            sp.layerstack.set_selected_nodes([layer])
            sp.layerstack.set_selection_type(layer, sp.layerstack.SelectionType.Content)
            self.halign.setCurrentIndex(self.halign.findText("Center"))
            self.auto_size.setChecked(True)
        except Exception as exc:
            if added_mask:
                try:
                    layer.remove_mask()
                except Exception as cleanup_exc:
                    exc = RuntimeError(f"{exc}. Could not remove incomplete mask: {cleanup_exc}")
            error(self, "Fit text to painted area", exc)

    def update_selected(self):
        try:
            if not self.text.toPlainText().strip():
                raise ValueError("Enter non-empty text before updating a text mask")
            node, source = self._selected_source()
            params = source.get_parameters()
            index = self.font.currentData()
            if index is not None:
                wanted = self.resources[index].identifier()
                if source.resource_id != wanted:
                    source = node.set_source(None, wanted)
            self._apply_params(source, params)
        except Exception as exc:
            error(self, "Update text mask", exc)
