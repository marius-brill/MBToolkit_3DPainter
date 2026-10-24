"""Paintable text with a non-destructive SourceFont mask."""
from copy import deepcopy

from PySide6 import QtWidgets, QtCore
import substance_painter as sp
from ...adapters.painter import available_font_resources, selected_single_layer
from ...ui.common import error
from ...adapters.painter import active_stack
from .placement import FitDiagnostics, measure_paint_bounds, placement_transform, verify_placement
from . import controls
from .sizing import metadata_key, read_state, scaled_projection, write_state


class Panel(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.resources = []
        self._transform_originals = {}
        self._size_dirty = False
        self._selected_identity = None
        self._fit_result_selection = None
        self._loading = False
        self._updating = False
        self._disposed = False
        self._pending_identity = None
        self._update_timer = QtCore.QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(250)
        self._update_timer.timeout.connect(self._flush_live_update)
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
        if not self._disposed:
            self._selection_timer.start()

    def _cancel_live_update(self):
        self._update_timer.stop()
        self._pending_identity = None

    def _live_update_changed(self, enabled):
        self._cancel_live_update()
        if enabled:
            self._queue_live_update()

    def _queue_live_update(self, *_args):
        if self._loading or self._updating or self._disposed or not self.live_update.isChecked():
            return
        self._cancel_live_update()
        if self._selected_identity is None or not self.text.toPlainText().strip():
            return
        try:
            node, _source = self._selected_source()
            identity = (str(active_stack()), node.uid())
        except (ValueError, RuntimeError, AttributeError):
            return
        if identity != self._selected_identity:
            self.request_refresh()
            return
        self._pending_identity = identity
        self._update_timer.start()

    def _flush_live_update(self):
        identity = self._pending_identity
        self._cancel_live_update()
        if (identity is None or self._disposed or self._loading or self._updating
                or not self.live_update.isChecked() or not self.text.toPlainText().strip()):
            return
        try:
            node, source = self._selected_source()
            if identity != self._selected_identity or identity != (str(active_stack()), node.uid()):
                self.request_refresh()
                return
            self._updating = True
            self._write_selected(node, source)
            self.status.setText("Text mask updated")
            self.status.setToolTip("")
        except Exception as exc:
            # Live typing must not open repeated modal dialogs on a host failure.
            self.status.setText("Live update failed; use Update text to retry")
            self.status.setToolTip(str(exc))
        finally:
            self._updating = False

    def dispose(self):
        self._disposed = True
        self._cancel_live_update()
        self._selection_timer.stop()

    def _sync_selection(self):
        if self._loading or self._updating or self._disposed:
            return
        keep_fit_status = False
        if getattr(self, "_fit_result_selection", None) is not None:
            try:
                stack, selected = selected_single_layer()
                keep_fit_status = (str(stack), selected.uid()) == self._fit_result_selection
            except (ValueError, RuntimeError, AttributeError):
                pass
            if not keep_fit_status:
                self._fit_result_selection = None
        try:
            node, _source = self._selected_source()
            identity = (str(active_stack()), node.uid())
        except (ValueError, RuntimeError, AttributeError):
            self._cancel_live_update()
            self._selected_identity = None
            self.update_button.setEnabled(False)
            self.rotation.setEnabled(False)
            self.rotation_degrees.setEnabled(False)
            if not keep_fit_status:
                self.status.setText("Paint an area, then Fit")
            return
        self.update_button.setEnabled(True)
        self.rotation.setEnabled(True)
        self.rotation_degrees.setEnabled(True)
        if identity == self._selected_identity:
            return
        self._cancel_live_update()
        self._selected_identity = identity
        self._loading = True
        try:
            self.load_selected()
            if not keep_fit_status:
                self.status.setText("Editing selected text mask")
        finally:
            self._loading = False

    def _size_slider_changed(self, value):
        controls.silently(self.size, controls.size_from_slider(value))
        if not self._loading:
            self._size_dirty = True

    def _size_number_changed(self, value):
        controls.silently(self.size_slider, controls.slider_from_size(value))
        if not self._loading:
            self._size_dirty = True

    def _filter(self, text):
        previous = self.font.currentData()
        blocked = self.font.blockSignals(True)
        try:
            self.font.clear()
            for i, res in enumerate(self.resources):
                name = res.gui_name()
                if text.casefold() in name.casefold():
                    self.font.addItem(name, i)
            if previous is not None:
                index = self.font.findData(previous)
                self.font.setCurrentIndex(index)
            elif self._selected_identity is not None:
                self.font.setCurrentIndex(-1)
        finally:
            self.font.blockSignals(blocked)

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
        self._cancel_live_update()
        loading = self._loading
        self._loading = True
        try:
            self._load_selected()
        finally:
            self._loading = loading

    def _load_selected(self):
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
            metadata = sp.project.Metadata("MBToolkit_3DPainter.font_sizing")
            state = read_state(metadata, metadata_key(active_stack(), node.uid()))
            self.size.setValue(state[1] if state else 0)
            self._size_dirty = False
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
            uv = params.uv_transformation
            uv.rotation = degrees % 360
            params.uv_transformation = uv
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
            params.uv_transformation = uv
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
                params.uv_transformation = uv
            node.set_projection_parameters(params)
            self._set_rotation_controls(params.uv_transformation.rotation or 0)
        except Exception as exc:
            error(self, "Reset text transform", exc)

    def _apply_params(self, source, params=None):
        if params is None:
            params = source.get_parameters()
        params.text = self.text.toPlainText()
        params.auto_size = True
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
        if self._loading or self._updating or self._disposed:
            self.status.setText("Fit unavailable: panel closed" if self._disposed
                                else "Fit busy: wait for the current update, then retry")
            return
        diagnostics = FitDiagnostics()
        self._fit_result_selection = None
        self.status.setToolTip("")
        self.status.setText("Fit: checking selection…")
        self.status.repaint()
        self._cancel_live_update()
        self._selection_timer.stop()
        self._updating = True
        self._loading = True
        layer = None
        added_mask = False
        saved_projection = None
        effect = None
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
            if isinstance(layer, sp.layerstack.FillEffectNode):
                layer = layer.get_parent()
            if layer is None:
                raise ValueError("Select the painted area's paint layer before fitting")
            self._fit_result_selection = (str(stack), layer.uid())
            diagnostics.record(stack=str(stack), layer=layer.uid())
            if not isinstance(layer, sp.layerstack.PaintLayerNode):
                raise ValueError("Select the painted area's paint layer before fitting")
            if layer.has_mask():
                effects = list(layer.mask_effects())
                if (len(effects) != 1 or not isinstance(effects[0], sp.layerstack.FillEffectNode)
                        or effects[0].get_name() != "MB Text Mask"
                        or not isinstance(effects[0].get_source(), sp.source.SourceFont)):
                    raise ValueError("Refit requires a single MB Text Mask effect. Existing custom masks "
                                     "are never replaced; select an unmasked paint layer for a new fit.")
                effect = effects[0]
                if effect.get_projection_mode() != sp.layerstack.ProjectionMode.UV:
                    raise ValueError("Refit supports UV-projected text masks only")
                saved_projection = deepcopy(effect.get_projection_parameters())
            self.status.setText("Fit: measuring painted coverage…")
            self.status.repaint()
            capture = []
            try:
                bounds = measure_paint_bounds(stack, layer, capture=capture)
            finally:
                if capture:
                    diagnostics.image("coverage", capture[0])
            diagnostics.record(paint_bounds=list(bounds))
            current_stack, current_layer = selected_single_layer()
            if (str(current_stack) != str(stack) or current_layer is None
                    or current_layer.uid() not in (layer.uid(), effect.uid() if effect else layer.uid())):
                raise ValueError("Selection changed while measuring the painted area")
            scale, offset = placement_transform(bounds)
            self.status.setText("Fit: rendering text mask…")
            self.status.repaint()
            if effect is None:
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
                projection = sp.layerstack.UVProjectionParams(
                    uv_wrapping_mode=sp.layerstack.UVWrapMode.RepeatNone,
                    uv_transformation=sp.layerstack.UVTransformationParams(
                        scale_mode=sp.layerstack.ScaleMode.Factors, scale=scale, rotation=0, offset=offset))
            else:
                # Refit only placement, preserving the actual source, rotation and mirrors.
                projection = deepcopy(saved_projection)
                uv = projection.uv_transformation
                if uv.scale_mode != sp.layerstack.ScaleMode.Factors:
                    raise ValueError("Refit requires UV Tiling scale mode")
                uv.scale = [(-v if old < 0 else v) for v, old in zip(scale, uv.scale)]
                uv.offset = offset
                projection.uv_transformation = uv
            effect.set_projection_parameters(projection)
            sp.layerstack.set_selected_nodes([layer])
            self.status.setText("Fit: verifying text position and paint overlap…")
            self.status.repaint()
            verify_placement(stack, layer, effect, bounds, capture[0], diagnostics=diagnostics)
            if saved_projection is not None:
                metadata = sp.project.Metadata("MBToolkit_3DPainter.font_sizing")
                fitted = effect.get_projection_parameters().uv_transformation.scale
                write_state(metadata, metadata_key(stack, effect.uid()), (list(fitted), 0))
            sp.layerstack.set_selected_nodes([layer])
            sp.layerstack.set_selection_type(layer, sp.layerstack.SelectionType.Content)
            if saved_projection is None:
                self.halign.setCurrentIndex(self.halign.findText("Center"))
            self.size.setValue(0)
            self._size_dirty = False
            # Clear session-only transform reset state after fitting a new baseline.
            if hasattr(self, "_transform_originals"):
                self._transform_originals.pop(effect.uid(), None)
            self.status.setText("Text placement verified")
            diagnostics.record(result="verified")
        except Exception as exc:
            if saved_projection is not None:
                try:
                    effect.set_projection_parameters(saved_projection)
                except Exception as restore_exc:
                    exc = RuntimeError(f"{exc}. Could not restore prior text placement: {restore_exc}")
            if added_mask:
                try:
                    layer.remove_mask()
                except Exception as cleanup_exc:
                    exc = RuntimeError(f"{exc}. Could not remove incomplete mask: {cleanup_exc}")
            self.status.setText("Fit failed: " + str(exc))
            self.status.setToolTip(str(exc))
            diagnostics.record(result="failed", error=str(exc))
            error(self, "Fit text to painted area", exc)
        finally:
            self._loading = False
            self._updating = False
            self.request_refresh()

    def update_selected(self):
        self._cancel_live_update()
        if self._loading or self._updating or self._disposed:
            return
        try:
            if not self.text.toPlainText().strip():
                raise ValueError("Enter non-empty text before updating a text mask")
            node, source = self._selected_source()
            if (str(active_stack()), node.uid()) != self._selected_identity:
                self.request_refresh()
                raise ValueError("Selection changed; wait for the selected text mask to load before updating")
            self._updating = True
            self._write_selected(node, source)
            self.status.setText("Text mask updated")
            self.status.setToolTip("")
        except Exception as exc:
            error(self, "Update text mask", exc)
        finally:
            self._updating = False

    def _write_selected(self, node, source):
        original = None
        state = None
        if self._size_dirty:
            if node.get_projection_mode() != sp.layerstack.ProjectionMode.UV:
                raise ValueError("Relative size supports UV-projected text masks only")
            original = node.get_projection_parameters()
            if original.uv_transformation.scale_mode != sp.layerstack.ScaleMode.Factors:
                raise ValueError("Relative size requires UV Tiling scale mode")
            metadata = sp.project.Metadata("MBToolkit_3DPainter.font_sizing")
            key = metadata_key(active_stack(), node.uid())
            projection, state = scaled_projection(original, self.size.value(), read_state(metadata, key))
        params = source.get_parameters()
        index = self.font.currentData()
        if index is not None:
            wanted = self.resources[index].identifier()
            if source.resource_id != wanted:
                source = node.set_source(None, wanted)
        try:
            if state is not None:
                node.set_projection_parameters(projection)
            self._apply_params(source, params)
            if state is not None:
                write_state(metadata, key, state)
        except Exception:
            if original is not None:
                node.set_projection_parameters(original)
            raise
        if state is not None:
            self._size_dirty = False

    def make_stencil(self):
        """Read inputs only; generation never invokes the text-mask update path."""
        if self._disposed:
            return
        from .stencil import create_stencil
        loading = self._loading
        self._loading = True
        self.stencil_button.setEnabled(False)
        try:
            index = self.font.currentData()
            if index is None:
                raise ValueError("Choose an available Painter font first")
            if not self.text.toPlainText().strip():
                raise ValueError("Enter non-empty text before making a stencil")
            if not sp.project.is_open():
                raise ValueError("Open a Painter project before making a stencil")
            resource = create_stencil(self.resources[index], self.text.toPlainText(),
                                      self.line_spacing.value(), self.char_spacing.value())
            self.status.setText("Stencil created — drag the alpha from Assets to the Stencil slot")
            try:
                resource.show_in_ui()
                self.status.setToolTip("")
            except Exception as exc:
                self.status.setToolTip("Alpha imported, but could not reveal it in Assets: " + str(exc))
        except Exception as exc:
            error(self, "Make stencil", exc)
        finally:
            self._loading = loading
            self.stencil_button.setEnabled(True)
