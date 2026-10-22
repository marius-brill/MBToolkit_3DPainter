"""Compact paint-first text controls; no Painter writes during construction."""
import math

from PySide6 import QtCore, QtWidgets


SLIDER_STYLE = """
    QSlider::groove:horizontal { height: 5px; background: #626262; border-radius: 2px; }
    QSlider::handle:horizontal { width: 15px; margin: -5px 0; border-radius: 7px; background: #ccc; }
    QSlider::handle:horizontal:hover { background: #eee; }
"""
NUMBER_STYLE = """
    QAbstractSpinBox { color: #dedede; background: transparent; border: none; padding: 2px; }
    QAbstractSpinBox:focus { background: #242424; border: 1px solid #65acf0; }
"""


def size_from_slider(value):
    return 10 ** (-3 + value / 200)


def slider_from_size(value):
    return round((math.log10(max(0.001, min(100, value))) + 3) * 200)


def silently(widget, value):
    blocked = widget.blockSignals(True)
    try:
        widget.setValue(value)
    finally:
        widget.blockSignals(blocked)


def slider_row(panel, name, minimum, maximum, number):
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(8)
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setTracking(False)
    slider.setMinimumWidth(65)
    slider.setStyleSheet(SLIDER_STYLE)
    slider.setAccessibleName(name + " slider")
    number.setFixedWidth(68)
    number.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
    number.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
    number.setKeyboardTracking(False)
    number.setStyleSheet(NUMBER_STYLE)
    number.setAccessibleName(name)
    row.addWidget(slider, 1)
    row.addWidget(number)
    return row, slider


def build(panel):
    main = QtWidgets.QVBoxLayout(panel)
    main.setContentsMargins(10, 10, 10, 10)
    main.setSpacing(8)
    panel.status = QtWidgets.QLabel("Paint an area to begin")
    panel.status.setToolTip("Select an existing text layer to edit it. Changes to text/font use Update text.")
    main.addWidget(panel.status)
    panel.text = QtWidgets.QPlainTextEdit("Hello World")
    panel.text.setPlaceholderText("Enter your text…")
    panel.text.setMaximumHeight(74)
    main.addWidget(panel.text)
    panel.search = QtWidgets.QLineEdit()
    panel.search.setPlaceholderText("Search fonts…")
    panel.search.textChanged.connect(panel._filter)
    main.addWidget(panel.search)
    font_row = QtWidgets.QHBoxLayout()
    panel.font = QtWidgets.QComboBox()
    panel.font.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    panel.font.setMinimumContentsLength(12)
    font_row.addWidget(panel.font, 1)
    refresh = QtWidgets.QToolButton()
    refresh.setText("↻")
    refresh.setToolTip("Refresh Painter fonts")
    refresh.clicked.connect(panel.refresh)
    font_row.addWidget(refresh)
    main.addLayout(font_row)
    placement = QtWidgets.QHBoxLayout()
    prepare = QtWidgets.QPushButton("Prepare text area")
    prepare.setToolTip("Create an unmasked paint layer. Paint a broad patch on its content, then Fit.")
    prepare.clicked.connect(panel.prepare_area)
    panel.fit_button = QtWidgets.QPushButton("Fit to painted area")
    panel.fit_button.setToolTip("Initial placement: fit text inside the patch's UV bounds. Single 0–1 UV tile, "
                               "top-level unmasked Base Color paint layer only. Uses a temporary 512px export.")
    panel.fit_button.clicked.connect(panel.fit_painted_area)
    placement.addWidget(prepare)
    placement.addWidget(panel.fit_button)
    main.addLayout(placement)
    form = QtWidgets.QFormLayout()
    panel.auto_size = QtWidgets.QCheckBox("Auto fit")
    panel.auto_size.setChecked(True)
    form.addRow("Size", panel.auto_size)
    panel.size = QtWidgets.QDoubleSpinBox()
    panel.size.setDecimals(4)
    panel.size.setRange(0.001, 100)
    panel.size.setValue(0.1)
    row, panel.size_slider = slider_row(panel, "Manual size", 0, 1000, panel.size)
    panel.size_slider.setValue(slider_from_size(0.1))
    panel.size.setEnabled(False)
    panel.size_slider.setEnabled(False)
    panel.auto_size.toggled.connect(panel._auto_size_changed)
    panel.size_slider.valueChanged.connect(panel._size_slider_changed)
    panel.size.valueChanged.connect(panel._size_number_changed)
    form.addRow("Manual size", row)
    panel.rotation_degrees = QtWidgets.QSpinBox()
    panel.rotation_degrees.setRange(-180, 180)
    panel.rotation_degrees.setSuffix("°")
    row, panel.rotation = slider_row(panel, "Rotation", -180, 180, panel.rotation_degrees)
    panel.rotation.valueChanged.connect(panel.rotate_selected)
    panel.rotation_degrees.valueChanged.connect(panel.rotate_selected)
    reset = QtWidgets.QToolButton()
    reset.setText("↻")
    reset.setToolTip("Restore rotation/flip from before this session's first edit")
    reset.clicked.connect(panel.reset_selected_transform)
    row.addWidget(reset)
    form.addRow("Rotation", row)
    flips = QtWidgets.QHBoxLayout()
    for label, axis in (("Flip horizontal", 0), ("Flip vertical", 1)):
        button = QtWidgets.QPushButton(label)
        button.clicked.connect(lambda checked=False, axis=axis: panel.flip_selected(axis))
        flips.addWidget(button)
    form.addRow("Mirror", flips)
    main.addLayout(form)
    advanced = QtWidgets.QToolButton()
    advanced.setText("Advanced")
    advanced.setCheckable(True)
    main.addWidget(advanced)
    advanced_body = QtWidgets.QWidget()
    advanced_form = QtWidgets.QFormLayout(advanced_body)
    panel.halign = QtWidgets.QComboBox()
    panel.halign.addItems(["Left", "Center", "Right"])
    advanced_form.addRow("Alignment", panel.halign)
    panel.line_spacing = QtWidgets.QDoubleSpinBox()
    panel.line_spacing.setRange(0, 10)
    panel.line_spacing.setValue(1)
    panel.line_spacing.setSingleStep(0.1)
    advanced_form.addRow("Line spacing", panel.line_spacing)
    panel.char_spacing = QtWidgets.QDoubleSpinBox()
    panel.char_spacing.setRange(-2, 10)
    panel.char_spacing.setSingleStep(0.05)
    advanced_form.addRow("Character spacing", panel.char_spacing)
    advanced_body.hide()
    advanced.toggled.connect(advanced_body.setVisible)
    main.addWidget(advanced_body)
    panel.update_button = QtWidgets.QPushButton("Update text")
    panel.update_button.clicked.connect(panel.update_selected)
    main.addWidget(panel.update_button)
    main.addStretch()
    panel.setMinimumWidth(320)