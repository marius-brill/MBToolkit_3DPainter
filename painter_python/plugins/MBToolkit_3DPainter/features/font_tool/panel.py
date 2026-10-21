"""Paintable text with a non-destructive SourceFont mask."""
from PySide6 import QtWidgets
import substance_painter as sp
from ...adapters.painter import available_font_resources, selected_single_layer, add_text_paint_layer
from ...ui.common import error
from ...adapters.painter import active_stack
from .placement import measure_paint_bounds, placement_transform


class Panel(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.resources = []
        main = QtWidgets.QVBoxLayout(self)
        note = QtWidgets.QLabel("Paint through an editable text mask. Paint on the layer content, not the mask. "
                                "Changing the text reveals your existing paint through the new lettering. "
                                "Paint a broad area to cover future text changes. Position the mask's Fill effect "
                                "using Painter's projection controls.")
        note.setWordWrap(True)
        main.addWidget(note)
        placement_note = QtWidgets.QLabel(
            "Experimental paint-first placement: Prepare text area, paint a broad patch, then Fit text to painted area. "
            "Uses the UV bounding-box center (not the 3D viewport center); single 0–1 tile, top-level Base Color paint "
            "layer only. Seams, holes and separate patches may give an unsuitable center. Uses a temporary 512px export.")
        placement_note.setWordWrap(True)
        main.addWidget(placement_note)
        prepare = QtWidgets.QPushButton("Prepare text area")
        prepare.clicked.connect(self.prepare_area)
        main.addWidget(prepare)
        fit = QtWidgets.QPushButton("Fit text to painted area")
        fit.clicked.connect(self.fit_painted_area)
        main.addWidget(fit)
        form = QtWidgets.QFormLayout()
        self.font = QtWidgets.QComboBox()
        self.font.setEditable(False)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Filter Painter fonts...")
        self.search.textChanged.connect(self._filter)
        form.addRow("Search", self.search)
        form.addRow("Font", self.font)
        self.text = QtWidgets.QPlainTextEdit("Hello World")
        self.text.setMaximumHeight(90)
        form.addRow("Text", self.text)
        self.auto_size = QtWidgets.QCheckBox("Auto fit")
        self.auto_size.setChecked(True)
        form.addRow("Size", self.auto_size)
        self.size = QtWidgets.QDoubleSpinBox()
        self.size.setRange(0.001, 100)
        self.size.setSingleStep(0.01)
        self.size.setDecimals(3)
        self.size.setValue(0.1)
        self.size.setEnabled(False)
        self.auto_size.toggled.connect(lambda on: self.size.setEnabled(not on))
        form.addRow("Manual size (normalized)", self.size)
        self.halign = QtWidgets.QComboBox()
        self.halign.addItems(["Left", "Center", "Right"])
        form.addRow("Horizontal align", self.halign)
        self.line_spacing = QtWidgets.QDoubleSpinBox()
        self.line_spacing.setRange(0, 10)
        self.line_spacing.setValue(1.0)
        self.line_spacing.setSingleStep(.1)
        form.addRow("Line spacing", self.line_spacing)
        self.char_spacing = QtWidgets.QDoubleSpinBox()
        self.char_spacing.setRange(-2, 10)
        self.char_spacing.setValue(0)
        self.char_spacing.setSingleStep(.05)
        form.addRow("Character spacing", self.char_spacing)
        main.addLayout(form)
        buttons = QtWidgets.QHBoxLayout()
        create = QtWidgets.QPushButton("Create paintable text")
        create.clicked.connect(self.create)
        buttons.addWidget(create)
        load = QtWidgets.QPushButton("Load selected text mask")
        load.clicked.connect(self.load_selected)
        buttons.addWidget(load)
        update = QtWidgets.QPushButton("Update selected text mask")
        update.clicked.connect(self.update_selected)
        buttons.addWidget(update)
        main.addLayout(buttons)
        fonts = QtWidgets.QPushButton("Refresh font resources")
        fonts.clicked.connect(self.refresh)
        main.addWidget(fonts)
        main.addStretch()
        self.setMinimumWidth(380)

    def refresh(self):
        try:
            self.resources = available_font_resources()
            self._filter(self.search.text())
        except Exception as exc:
            error(self, "Font resources", exc)

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
            _node, source = self._selected_source()
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

    def create(self):
        node = None
        try:
            text = self.text.toPlainText()
            if not text.strip():
                raise ValueError("Enter non-empty text before creating a text mask")
            idx = self.font.currentData()
            if idx is None:
                self.refresh()
                idx = self.font.currentData()
            if idx is None:
                raise ValueError("No compatible Painter font resource found")
            resource = self.resources[idx]
            node, _effect, source = add_text_paint_layer(resource.identifier())
            node.set_name("MB Text: " + text.strip().splitlines()[0][:45])
            self._apply_params(source)
            sp.layerstack.set_selected_nodes([node])
            sp.layerstack.set_selection_type(node, sp.layerstack.SelectionType.Content)
        except Exception as exc:
            if node is not None:
                try:
                    sp.layerstack.delete_node(node)
                except Exception as cleanup_exc:
                    exc = RuntimeError(f"{exc}. Could not remove incomplete text layer: {cleanup_exc}")
            error(self, "Create paintable text", exc)

    def prepare_area(self):
        try:
            stack = active_stack()
            if stack is None:
                raise ValueError("Open a Painter project first")
            layer = sp.layerstack.insert_paint(sp.layerstack.InsertPosition.from_textureset_stack(stack))
            layer.active_channels = set(layer.active_channels) | {sp.textureset.ChannelType.BaseColor}
            layer.set_name("MB Text Area: paint here, then Fit")
            sp.layerstack.set_selected_nodes([layer])
            sp.layerstack.set_selection_type(layer, sp.layerstack.SelectionType.Content)
        except Exception as exc:
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
                                 "Use Load/Update for previously fitted text.")
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
