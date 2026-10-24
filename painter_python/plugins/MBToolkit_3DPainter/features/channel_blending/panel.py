"""Compact, palette-aware multi-channel blending editor."""
import re

from PySide6 import QtCore, QtWidgets
import substance_painter as sp

from ...adapters.painter import selected_single_layer
from ...ui.common import clear_layout, error


def display_name(name):
    """Keep enum IDs separate from their human-readable labels."""
    name = name.replace("_", " ")
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", name)


def set_value_silently(widget, value):
    blocked = widget.blockSignals(True)
    try:
        widget.setValue(value)
    finally:
        widget.blockSignals(blocked)


class ChannelRow(QtWidgets.QWidget):
    """One channel: title, blend selector, slider and precise percentage."""

    def __init__(self, panel, channel):
        super().__init__()
        self.panel = panel
        self.channel = channel
        self.setObjectName("MBChannelRow")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 8, 7)
        layout.setSpacing(8)
        title = QtWidgets.QLabel("Apply to all" if channel is None else display_name(channel.name))
        title.setObjectName("MBChannelName")
        title.setFixedWidth(112)
        title.setToolTip(title.text())
        layout.addWidget(title, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.percent = QtWidgets.QSpinBox()
        self.percent.setRange(0, 100)
        self.percent.setFixedWidth(43)
        self.percent.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.percent.setKeyboardTracking(False)
        self.percent.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.percent.setAccessibleName(title.text() + " opacity")
        self.combo = QtWidgets.QComboBox()
        self.combo.setFixedWidth(88)
        self.combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo.setMinimumContentsLength(6)
        self.combo.setAccessibleName(title.text() + " blend mode")
        for name, mode in sp.layerstack.BlendingMode.__members__.items():
            self.combo.addItem(display_name(name), mode)
        # Keep full mode names readable in the popup without widening the column.
        self.combo.view().setMinimumWidth(190)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setMinimumWidth(65)
        self.slider.setAccessibleName(title.text() + " opacity slider")
        layout.addWidget(self.combo, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.slider, 1, QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.percent, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.reset = QtWidgets.QToolButton()
        self.reset.setText("↻")
        self.reset.setObjectName("MBReset")
        self.reset.setFixedSize(28, 28)
        self.reset.setToolTip("Set Normal blending and 100% opacity" +
                              (" on all available channels" if channel is None else ""))
        self.reset.setAccessibleName(title.text() + " reset to Normal and 100 percent")
        self.reset.clicked.connect(lambda: panel._reset(channel))
        layout.addWidget(self.reset, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.slider.sliderPressed.connect(panel._drag_start)
        self.slider.sliderReleased.connect(panel._drag_end)
        self.slider.valueChanged.connect(self._slider_changed)
        self.percent.valueChanged.connect(self._percent_changed)
        self.percent.editingFinished.connect(panel.request_refresh)
        self.combo.currentIndexChanged.connect(
            lambda _index: panel._set_mode(channel, self.combo.currentData()))

    def _slider_changed(self, value):
        self.percent.setSpecialValueText("")
        set_value_silently(self.percent, value)
        self.panel._queue(self.channel, value)

    def _percent_changed(self, value):
        self.percent.setSpecialValueText("")
        set_value_silently(self.slider, value)
        self.panel._queue(self.channel, value)

    def is_editing(self):
        return (self.percent.hasFocus() and self.percent.lineEdit().isModified()) or self.combo.view().isVisible()

    def sync(self, node):
        try:
            opacity = round(node.get_opacity(self.channel) * 100)
            mode = node.get_blending_mode(self.channel)
            index = next((i for i in range(self.combo.count())
                          if self.combo.itemData(i) == mode), -1)
            if index < 0:
                raise ValueError("This channel's blending mode is not available")
            set_value_silently(self.slider, opacity)
            set_value_silently(self.percent, opacity)
            self.percent.setSpecialValueText("")
            self.percent.setProperty("modified", opacity != 100)
            self.percent.style().unpolish(self.percent)
            self.percent.style().polish(self.percent)
            blocked = self.combo.blockSignals(True)
            try:
                self.combo.setCurrentIndex(index)
            finally:
                self.combo.blockSignals(blocked)
            self.setEnabled(True)
            self.reset.setEnabled("Normal" in sp.layerstack.BlendingMode.__members__)
            self.setToolTip("")
        except Exception as exc:
            self.setEnabled(False)
            self.setToolTip("Unavailable for this layer: " + str(exc))

    def sync_all(self, rows):
        """Show shared values or Mixed; never write while reflecting selection."""
        available = [row for row in rows if row.isEnabled()]
        self.setEnabled(bool(available))
        if not available:
            return
        modes = {row.combo.currentIndex() for row in available}
        values = {row.percent.value() for row in available}
        blocked = self.combo.blockSignals(True)
        try:
            self.combo.setPlaceholderText("Mixed")
            self.combo.setCurrentIndex(next(iter(modes)) if len(modes) == 1 else -1)
        finally:
            self.combo.blockSignals(blocked)
        mixed = len(values) != 1
        self.percent.setSpecialValueText("—" if mixed else "")
        set_value_silently(self.percent, 0 if mixed else next(iter(values)))
        set_value_silently(self.slider, 0 if mixed else next(iter(values)))
        self.slider.setToolTip("Mixed opacity — adjusting applies to all available channels" if mixed else "Opacity for all channels")
        self.reset.setEnabled("Normal" in sp.layerstack.BlendingMode.__members__)


class Panel(QtWidgets.QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.node = None
        self._channels = {}
        self._pending = {}
        self._dragging = 0
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._flush)
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(160)
        self._refresh_timer.timeout.connect(self.refresh)
        self.setObjectName("MBBlendingPanel")
        self.setStyleSheet("""
            QWidget#MBBlendingPanel { background: #303030; color: #dedede; }
            QLabel { color: #dedede; background: transparent; }
            QLabel#MBLayerName { color: #aaa; padding: 2px 4px; }
            QLabel#MBChannelName { font-weight: 600; }
            QWidget#MBChannelRow { background: #2d2d2d; border: 1px solid #242424; }
            QComboBox { color: #dedede; background: #2d2d2d; border: none; padding: 4px; min-height: 22px; }
            QComboBox:hover { background: #393939; }
            QComboBox QAbstractItemView { color: #dedede; background: #303030; selection-background-color: #456887; }
            QSpinBox { color: #dedede; background: transparent; border: none; padding: 2px; }
            QSpinBox[modified="true"] { color: #65acf0; }
            QSpinBox:focus { background: #242424; border: 1px solid #65acf0; }
            QSlider::groove:horizontal { height: 5px; background: #626262; border-radius: 2px; }
            QSlider::handle:horizontal { width: 15px; margin: -5px 0; border-radius: 7px; background: #ccc; }
            QSlider::handle:horizontal:hover { background: #eee; }
            QToolButton { color: #ccc; background: transparent; border: none; padding: 3px; }
            QToolButton:hover { background: #444; color: white; }
            QToolButton#MBReset { font-size: 23px; }
            QWidget:disabled, QLabel:disabled, QToolButton:disabled { color: #727272; }
            QScrollArea { border: none; background: #303030; }
        """)
        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(6, 6, 6, 6)
        main.setSpacing(3)
        self.caption = QtWidgets.QLabel("No layer selected")
        self.caption.setObjectName("MBLayerName")
        self.caption.setWordWrap(True)
        main.addWidget(self.caption)
        self.status = QtWidgets.QLabel("Select one paint or fill layer to edit its channels.")
        self.status.setWordWrap(True)
        main.addWidget(self.status)
        self.all_row = ChannelRow(self, None)
        self.all_row.setEnabled(False)
        self.area = QtWidgets.QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main.addWidget(self.area, 1)
        contents = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(contents)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(3)
        content_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        # Share the same viewport width, including when a scrollbar is visible.
        content_layout.addWidget(self.all_row)
        self.rows = QtWidgets.QVBoxLayout()
        content_layout.addLayout(self.rows)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(3)
        self.rows.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.area.setWidget(contents)
        self.area.hide()
        footer_widget = QtWidgets.QWidget()
        footer_widget.setObjectName("MBBlendFooter")
        footer_widget.setStyleSheet("QToolButton { padding: 0px 4px; margin: 0; font-size: 10px; }")
        footer = QtWidgets.QHBoxLayout(footer_widget)
        footer.setContentsMargins(8, 1, 8, 1)
        footer.setSpacing(3)
        for name, text in (("Normal", "NO"), ("Dissolve", "DI"), ("Passthrough", "PA"),
                           ("Multiply", "MU"), ("Overlay", "OV")):
            mode = sp.layerstack.BlendingMode.__members__.get(name)
            if mode is None:
                continue
            button = QtWidgets.QToolButton()
            button.setText(text)
            button.setToolTip("Apply " + display_name(name) + " to all available channels")
            button.clicked.connect(lambda checked=False, value=mode: self._set_mode(None, value))
            footer.addWidget(button)
        footer.addStretch()
        refresh = QtWidgets.QToolButton()
        refresh.setText("↻")
        refresh.setToolTip("Refresh selected layer")
        refresh.clicked.connect(self.refresh)
        footer.addWidget(refresh)
        main.addWidget(footer_widget)
        self.setMinimumWidth(440)
        app.events.add(self.request_refresh)

    def request_refresh(self):
        self._refresh_timer.start()

    def _empty(self, message, detail):
        self.node = None
        self.all_row.setEnabled(False)
        self.caption.setText(message)
        self.status.setText(detail)
        self.status.setVisible(True)
        self.area.hide()
        clear_layout(self.rows)
        self._channels.clear()

    def refresh(self):
        if self._dragging:
            self._refresh_timer.start()
            return
        if self._pending:
            self._flush()
        try:
            stack, node = selected_single_layer()
            valid = (sp.layerstack.NodeType.PaintLayer, sp.layerstack.NodeType.FillLayer)
            if stack is None or node is None or node.get_type() not in valid or not node.has_blending():
                self._empty("No editable layer selected", "Select one paint or fill layer to edit its channels.")
                return
            channels = list(stack.all_channels())
            same_node = self.node is not None and self.node.uid() == node.uid()
            if same_node and (self.all_row.is_editing() or any(row.is_editing() for row in self._channels.values())):
                self._refresh_timer.start()
                return
            self.node = node
            self.caption.setText(node.get_name())
            self.caption.setToolTip(node.get_name())
            self.status.setText("")
            self.status.setVisible(False)
            if list(self._channels) != channels:
                clear_layout(self.rows)
                self._channels.clear()
                for channel in channels:
                    row = ChannelRow(self, channel)
                    self.rows.addWidget(row)
                    self._channels[channel] = row
            for row in self._channels.values():
                row.sync(node)
            self.all_row.sync_all(self._channels.values())
            self.area.setVisible(bool(channels))
        except Exception as exc:
            self._empty("Unable to read layer", str(exc))

    def _drag_start(self):
        self._dragging += 1

    def _drag_end(self):
        self._dragging = max(0, self._dragging - 1)
        self._flush()

    def _queue(self, channel, value):
        if self.node is not None:
            for target in self._targets(channel):
                self._pending[target] = (self.node, float(value) / 100)
            self._timer.start()

    def _targets(self, channel):
        if channel is not None:
            return [channel]
        return [key for key, row in self._channels.items() if row.isEnabled()]

    def _reset(self, channel):
        mode = sp.layerstack.BlendingMode.__members__.get("Normal")
        if mode is not None and self.node is not None:
            self._set_mode(channel, mode)
            self._queue(channel, 100)
            self._flush()

    def _flush(self):
        self._timer.stop()
        pending, self._pending = self._pending, {}
        try:
            _stack, current_node = selected_single_layer()
            for channel, (node, value) in pending.items():
                if current_node is not None and current_node.uid() == node.uid():
                    try:
                        node.set_opacity(value, channel)
                    except Exception as exc:
                        error(self, "Channel opacity", exc)
        except Exception as exc:
            error(self, "Channel opacity", exc)
        finally:
            self._refresh_timer.start()

    def _set_mode(self, channel, mode):
        if mode is None or self.node is None:
            return
        try:
            _stack, current_node = selected_single_layer()
            if current_node is None or current_node.uid() != self.node.uid():
                return
            for target in self._targets(channel):
                try:
                    self.node.set_blending_mode(mode, target)
                except Exception as exc:
                    error(self, "Blend mode", exc)
        except Exception as exc:
            error(self, "Blend mode", exc)
        finally:
            self.request_refresh()