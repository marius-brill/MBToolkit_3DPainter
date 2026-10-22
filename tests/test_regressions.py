"""Controller regressions with minimal host doubles; not Qt integration tests."""
import importlib
import math
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def host_modules(monkeypatch):
    before = set(sys.modules)
    widgets = SimpleNamespace(QWidget=object, QDialog=object, QTreeWidgetItem=object)
    monkeypatch.setitem(sys.modules, "PySide6", SimpleNamespace(
        QtWidgets=widgets, QtCore=SimpleNamespace(),
        QtGui=SimpleNamespace(QKeySequence=lambda value: value)))
    painter = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "substance_painter", painter)
    try:
        yield painter
    finally:
        for name in set(sys.modules) - before:
            if name.startswith("MBToolkit_3DPainter."):
                sys.modules.pop(name, None)


def test_preferences_close_callback_does_not_interrupt_teardown(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.bootstrap")
    app = module.Toolkit()
    dialog = Mock()
    dialog.close.side_effect = lambda: setattr(app, "preferences", None)
    app.preferences = dialog
    app.events = Mock()
    app.stop()
    dialog.close.assert_called_once()
    dialog.deleteLater.assert_called_once()
    app.events.stop.assert_called_once()
    assert app.preferences is None


def test_command_catalog_has_no_retired_inspector(host_modules, tmp_path):
    module = importlib.import_module("MBToolkit_3DPainter.bootstrap")
    app = module.Toolkit()
    app.settings = module.Settings(tmp_path)
    app.commands = module.Commands(app.settings)
    app._register_commands()
    ids = {identifier for identifier, _label in app.commands.catalog()}
    assert "mb.performance" not in ids
    assert {"mb.blending", "mb.fonts", "mb.pies.edit"} <= ids


def test_pie_shortcuts_disable_auto_repeat(host_modules, monkeypatch):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.feature")
    action = Mock()
    monkeypatch.setattr(module.QtGui, "QAction", Mock(return_value=action), raising=False)
    monkeypatch.setattr(module.QtCore, "Qt", SimpleNamespace(
        ShortcutContext=SimpleNamespace(ApplicationShortcut="application")), raising=False)
    app = SimpleNamespace(main_window=Mock(), settings=SimpleNamespace(data={
        "pie_menus": [{"id": "main", "name": "Main", "shortcut": "Ctrl+1"}]}))
    feature = module.Feature(app)
    feature.rebuild_shortcuts()
    action.setAutoRepeat.assert_called_once_with(False)
    assert feature.shortcuts == [action]
    feature.show_wheel = Mock()
    action.triggered.connect.call_args.args[0]()
    feature.show_wheel.assert_called_once_with("main", "Ctrl+1")


def test_pie_open_menu_is_not_replaced(host_modules, monkeypatch):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.feature")
    wheel_type = Mock()
    monkeypatch.setattr(module, "Wheel", wheel_type)
    feature = module.Feature(SimpleNamespace())
    feature.wheel = Mock()
    feature.wheel.isVisible.return_value = True
    feature.show_wheel("main")
    wheel_type.assert_not_called()
    feature.wheel.close.assert_not_called()


@pytest.mark.parametrize("index", [None, 0])
def test_pie_hover_highlights_without_activating(host_modules, index):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.wheel")
    wheel = SimpleNamespace(_hit=Mock(return_value=index), _activate=Mock(), update=Mock())
    module.Wheel.mouseMoveEvent(wheel, Mock())
    assert wheel.hovered == index
    wheel._activate.assert_not_called()
    wheel.update.assert_called_once()


def test_pie_leaving_clears_highlight(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.wheel")
    wheel = SimpleNamespace(hovered=0, update=Mock())
    module.Wheel.leaveEvent(wheel, Mock())
    assert wheel.hovered is None
    wheel.update.assert_called_once()


@pytest.mark.parametrize("modifiers, expected", [(0, {65}), (1, {65, 100}), (15, {65, 100, 101, 102, 103})])
def test_pie_tracks_shortcut_key_and_required_modifiers(host_modules, monkeypatch, modifiers, expected):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.wheel")
    class Sequence:
        def isEmpty(self):
            return False

        def count(self):
            return 1

        def __getitem__(self, index):
            assert index == 0
            return SimpleNamespace(key=lambda: 65, keyboardModifiers=lambda: modifiers)

    monkeypatch.setattr(module.QtGui, "QKeySequence", lambda shortcut: Sequence())
    monkeypatch.setattr(module.QtCore, "Qt", SimpleNamespace(
        KeyboardModifier=SimpleNamespace(ControlModifier=1, ShiftModifier=2, AltModifier=4, MetaModifier=8),
        Key=SimpleNamespace(Key_Control=100, Key_Shift=101, Key_Alt=102, Key_Meta=103)), raising=False)
    wheel = SimpleNamespace(_release_keys=set())
    module.Wheel.set_hold_shortcut(wheel, "Ctrl+A")
    assert wheel._release_keys == expected


@pytest.mark.parametrize("index", [None, 0])
@pytest.mark.parametrize("key", [65, 100])
def test_pie_hotkey_release_commits_current_hover_or_cancels(host_modules, monkeypatch, index, key):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.wheel")
    monkeypatch.setattr(module.QtGui, "QCursor", SimpleNamespace(pos=lambda: "cursor"), raising=False)
    wheel = SimpleNamespace(_release_keys={65, 100}, isVisible=lambda: True,
                            mapFromGlobal=Mock(return_value="local"), _hit=Mock(return_value=index),
                            _activate=Mock(), close=Mock(), hovered=1)
    event = Mock()
    event.key.return_value = key
    event.isAutoRepeat.return_value = False
    module.Wheel.keyReleaseEvent(wheel, event)
    wheel._hit.assert_called_once_with("local")
    if index is None:
        wheel.close.assert_called_once()
        wheel._activate.assert_not_called()
    else:
        wheel._activate.assert_called_once_with(index)
        wheel.close.assert_not_called()


@pytest.mark.parametrize("key, repeat, visible", [(65, True, True), (66, False, True), (65, False, False)])
def test_pie_ignores_repeat_unrelated_or_hidden_key_releases(host_modules, key, repeat, visible):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.wheel")
    wheel = SimpleNamespace(_release_keys={65}, isVisible=lambda: visible, _activate=Mock(), close=Mock())
    event = Mock()
    event.key.return_value = key
    event.isAutoRepeat.return_value = repeat
    module.Wheel.keyReleaseEvent(wheel, event)
    wheel._activate.assert_not_called()
    wheel.close.assert_not_called()


def test_pie_mouse_release_does_not_commit_while_holding_hotkey(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.wheel")
    wheel = SimpleNamespace(_release_keys={65}, _activate=Mock(), close=Mock())
    event = Mock()
    module.Wheel.mouseReleaseEvent(wheel, event)
    event.accept.assert_called_once()
    wheel._activate.assert_not_called()
    wheel.close.assert_not_called()


def test_pie_activation_closes_before_dispatch_and_runs_once(host_modules, monkeypatch):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.wheel")
    timer = Mock()
    monkeypatch.setattr(module.QtCore, "QTimer", timer, raising=False)
    wheel = SimpleNamespace(_activated=False, isVisible=lambda: True,
                            close=Mock(), actions=[("mb.fonts", "Fonts")], execute=Mock())
    module.Wheel._activate(wheel, 0)
    wheel.close.assert_called_once()
    wheel.execute.assert_not_called()
    module.Wheel._activate(wheel, 0)
    timer.singleShot.assert_called_once()
    delay, dispatch = timer.singleShot.call_args.args
    assert delay == 0
    dispatch()
    wheel.execute.assert_called_once_with("mb.fonts")


@pytest.mark.parametrize("radius, expected", [(0, None), (118, None), (119, 0), (220, 0), (229, None)])
def test_pie_larger_center_and_thinner_ring_hit_testing(host_modules, radius, expected):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.wheel")
    wheel = SimpleNamespace(width=lambda: 494, height=lambda: 494,
                            INNER=module.Wheel.INNER, OUTER=module.Wheel.OUTER,
                            actions=[("mb.fonts", "Fonts")])
    point = SimpleNamespace(x=lambda: 247 + radius, y=lambda: 247)
    assert module.Wheel.SIZE == 380 * 1.3
    assert module.Wheel.INNER == 140 * .85
    assert module.Wheel._hit(wheel, point) == expected


@pytest.mark.parametrize("count", range(1, 13))
def test_pie_label_boxes_stay_inside_their_slice(host_modules, count):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.wheel")
    wheel = SimpleNamespace(INNER=module.Wheel.INNER, OUTER=module.Wheel.OUTER)
    assert wheel.OUTER-wheel.INNER > 228-156
    for index in range(count):
        angle = -math.pi/2 + (index+.5)*2*math.pi/count
        x, y, width, height = module.Wheel._label_box(wheel, angle, count)
        assert width > 0 and height > 0
        for dx in range(11):
            for dy in range(11):
                px, py = x+width*dx/10, y+height*dy/10
                assert wheel.INNER+8-.001 <= math.hypot(px, py) <= wheel.OUTER-8+.001
                delta = math.atan2(math.sin(math.atan2(py, px)-angle),
                                   math.cos(math.atan2(py, px)-angle))
                if count > 1:
                    assert abs(delta) <= math.pi/count-.035+.001


@pytest.mark.parametrize("required_width", [80, 3200])
def test_pie_labels_use_semibold_and_fit_without_truncation(host_modules, monkeypatch, required_width):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.wheel")
    font = Mock()
    font_type = Mock(return_value=font)
    font_type.Weight.DemiBold = "semibold"
    monkeypatch.setattr(module.QtGui, "QFont", font_type, raising=False)
    monkeypatch.setattr(module.QtCore, "Qt", SimpleNamespace(
        AlignmentFlag=SimpleNamespace(AlignCenter=1), TextFlag=SimpleNamespace(TextWordWrap=2)), raising=False)
    rect = SimpleNamespace(width=lambda: 100, height=lambda: 40, center=lambda: "center")
    monkeypatch.setattr(module.QtCore, "QRectF", Mock(), raising=False)

    def metrics(current_font):
        size = current_font.setPixelSize.call_args.args[0]
        return SimpleNamespace(boundingRect=lambda *args: SimpleNamespace(
            width=lambda: required_width*size/16, height=lambda: size*4))

    monkeypatch.setattr(module.QtGui, "QFontMetricsF", metrics, raising=False)
    painter = Mock()
    text = "A very long feature label that must not be truncated"
    labels = [(rect, text), (rect, "Short")]
    fitted_font, scale = module.Wheel._fit_labels(SimpleNamespace(), labels)
    for label_rect, label in labels:
        module.Wheel._draw_label(SimpleNamespace(), painter, label_rect, label, fitted_font, scale)
    font_type.assert_called_once_with("Segoe UI")
    font.setStyleName.assert_called_once_with("Semibold")
    font.setWeight.assert_called_once_with("semibold")
    assert font.setPixelSize.call_args.args[0] < 16
    assert painter.scale.call_args_list[0] == painter.scale.call_args_list[1]
    assert all(call.args[0] is fitted_font for call in painter.setFont.call_args_list)
    final_size = font.setPixelSize.call_args.args[0]
    assert required_width*final_size/16*scale <= 100
    assert final_size*4*scale <= 40
    assert painter.drawText.call_args_list[0].args[-1] == text
    assert painter.restore.call_count == 2


@pytest.mark.parametrize("name, expected", [(" Typography ", "Typography"), ("  ", "Fonts")])
def test_pie_feature_rename_and_default_reset(host_modules, name, expected):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.editor")
    menu = {"actions": ["mb.fonts"]}
    editor = SimpleNamespace(current=0, menus=[menu], actions=Mock(), label=lambda command: "Fonts")
    editor.actions.row.return_value = 0
    editor.action_names = lambda: module.Editor.action_names(editor)
    item = Mock()
    item.text.return_value = name
    module.Editor.rename_action(editor, item)
    assert menu["action_names"] == [name.strip()]
    item.setText.assert_called_once_with(expected)


def test_pie_custom_names_follow_reorder_and_removal(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.editor")
    menu = {"actions": ["a", "b"], "action_names": ["First", "Second"]}
    editor = SimpleNamespace(current=0, menus=[menu], actions=Mock())
    editor.action_names = lambda: module.Editor.action_names(editor)
    editor.actions.currentRow.return_value = 0
    module.Editor.move_action(editor, 1)
    assert menu == {"actions": ["b", "a"], "action_names": ["Second", "First"]}
    editor.actions.currentRow.return_value = 1
    module.Editor.remove_action(editor)
    assert menu == {"actions": ["b"], "action_names": ["Second"]}


@pytest.mark.parametrize("shortcut", ["", "Ctrl+1"])
def test_pie_runtime_uses_custom_names_and_default_fallback(host_modules, monkeypatch, shortcut):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.feature")
    wheel_type = Mock()
    monkeypatch.setattr(module, "Wheel", wheel_type)
    app = SimpleNamespace(settings=SimpleNamespace(data={"pie_menus": [{
        "id": "main", "name": "Main", "actions": ["a", "b", "c"], "action_names": ["Custom", ""]}]}),
        commands=SimpleNamespace(catalog=lambda: [("a", "A"), ("b", "B"), ("c", "C")]))
    feature = module.Feature(app)
    feature.show_wheel("main", shortcut)
    wheel_type.assert_called_once_with("Main", [("a", "Custom"), ("b", "B"), ("c", "C")], feature.dispatch)
    wheel_type.return_value.open_at_cursor.assert_called_once()
    if shortcut:
        wheel_type.return_value.set_hold_shortcut.assert_called_once_with(shortcut)
    else:
        wheel_type.return_value.set_hold_shortcut.assert_not_called()


def test_pie_population_blocks_selection_signals(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.editor")
    editor = SimpleNamespace(
        menus=[{"name": "First"}, {"name": "Second"}], current=0,
        menulist=Mock(), commit_current=Mock(), select_menu=Mock())
    editor.menulist.blockSignals.return_value = False
    editor.menulist.currentRow.return_value = 1
    module.Editor.populate(editor, 1)
    editor.commit_current.assert_called_once()
    assert editor.current == -1
    assert editor.menulist.method_calls == [
        ("blockSignals", (True,), {}), ("clear", (), {}),
        ("addItems", (["First", "Second"],), {}),
        ("setCurrentRow", (1,), {}), ("blockSignals", (False,), {}),
        ("currentRow", (), {})]
    editor.select_menu.assert_called_once_with(1)


def test_pie_selection_loads_shortcut_without_committing_partial_ui(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.pie_menus.editor")
    keyedit = Mock()
    keyedit.blockSignals.return_value = False
    editor = SimpleNamespace(
        menus=[{"name": "Second", "shortcut": "Ctrl+2", "actions": ["action"]}],
        commit_current=Mock(), name=Mock(), keyedit=keyedit, actions=Mock(),
        catalog=Mock(), app=SimpleNamespace(commands=SimpleNamespace(catalog=list)),
        label=lambda command: command, append_action_item=Mock())
    module.Editor.select_menu(editor, 0)
    assert keyedit.method_calls == [
        ("setEnabled", (True,), {}), ("blockSignals", (True,), {}),
        ("setKeySequence", ("Ctrl+2",), {}), ("blockSignals", (False,), {})]
    editor.commit_current.assert_called_once()


@pytest.mark.parametrize("text", ["", " ", "\n\t"])
def test_empty_font_text_does_not_create_layer(host_modules, monkeypatch, text):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    create_layer = Mock()
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    panel = SimpleNamespace(text=SimpleNamespace(toPlainText=lambda: text))
    module.Panel.fit_painted_area(panel)
    create_layer.assert_not_called()
    assert isinstance(report.call_args.args[2], ValueError)


def test_text_mask_adapter_creates_separate_paint_and_mask(host_modules, monkeypatch):
    module = importlib.import_module("MBToolkit_3DPainter.adapters.painter")
    monkeypatch.setattr(module, "active_stack", lambda: "stack")
    layer, effect, source = Mock(), Mock(), Mock()
    effect.set_source.return_value = source
    host_modules.layerstack = SimpleNamespace(
        insert_paint=Mock(return_value=layer), insert_fill=Mock(return_value=effect),
        InsertPosition=SimpleNamespace(from_textureset_stack=Mock(return_value="root"),
                                       inside_node=Mock(return_value="mask")),
        NodeStack=SimpleNamespace(Mask="mask-stack"), MaskBackground=SimpleNamespace(Black="black"),
        delete_node=Mock())
    assert module.add_text_paint_layer("font") == (layer, effect, source)
    host_modules.layerstack.insert_paint.assert_called_once_with("root")
    layer.add_mask.assert_called_once_with("black")
    host_modules.layerstack.InsertPosition.inside_node.assert_called_once_with(layer, "mask-stack")
    effect.set_source.assert_called_once_with(None, "font")
    effect.set_source.side_effect = RuntimeError("Missing font")
    with pytest.raises(RuntimeError, match="Missing font"):
        module.add_text_paint_layer("font")
    host_modules.layerstack.delete_node.assert_called_once_with(layer)


def test_text_panel_has_no_obsolete_create_action(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    assert not hasattr(module.Panel, "create")


@pytest.mark.parametrize("value", [0.001, 0.01, 0.1, 1, 10, 100])
def test_manual_size_slider_mapping(host_modules, value):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.controls")
    assert module.size_from_slider(module.slider_from_size(value)) == pytest.approx(value)


def test_text_selection_sync_loads_once_and_preserves_pending_edits(host_modules, monkeypatch):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    node = Mock()
    node.uid.return_value = 42
    monkeypatch.setattr(module, "active_stack", lambda: "stack")
    panel = SimpleNamespace(_loading=False, _selected_identity=None,
                            _selected_source=lambda: (node, Mock()), load_selected=Mock(),
                            update_button=Mock(), rotation=Mock(), rotation_degrees=Mock(), status=Mock())
    module.Panel._sync_selection(panel)
    module.Panel._sync_selection(panel)
    panel.load_selected.assert_called_once()
    assert panel._loading is False
    node.uid.return_value = 43
    module.Panel._sync_selection(panel)
    assert panel.load_selected.call_count == 2
    def no_text():
        raise ValueError("No text selected")
    panel._selected_source = no_text
    module.Panel._sync_selection(panel)
    assert panel._selected_identity is None
    panel.update_button.setEnabled.assert_called_with(False)


def test_manual_size_slider_sync_does_not_write_painter(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    panel = SimpleNamespace(size=Mock(), size_slider=Mock())
    module.Panel._size_slider_changed(panel, 400)
    panel.size.setValue.assert_called_once_with(pytest.approx(0.1))
    module.Panel._size_number_changed(panel, 1)
    panel.size_slider.setValue.assert_called_once_with(600)
    module.Panel._auto_size_changed(panel, True)
    panel.size.setEnabled.assert_called_once_with(False)
    panel.size_slider.setEnabled.assert_called_once_with(False)


def test_text_mask_params_are_white_on_opaque_black(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    host_modules.source = SimpleNamespace(HorizontalAlignment=SimpleNamespace(Left="left"))
    host_modules.colormanagement = SimpleNamespace(Color=lambda *rgb: rgb)
    params = SimpleNamespace(size=0.4, vertical_alignment="preserved")
    source = Mock()
    source.get_parameters.return_value = params
    panel = SimpleNamespace(text=SimpleNamespace(toPlainText=lambda: "Text"),
                            auto_size=SimpleNamespace(isChecked=lambda: True),
                            halign=SimpleNamespace(currentText=lambda: "Left"),
                            line_spacing=SimpleNamespace(value=lambda: 1.2),
                            char_spacing=SimpleNamespace(value=lambda: 0.1))
    module.Panel._apply_params(panel, source)
    assert (params.color, params.background_color, params.background_opacity) == ((1, 1, 1), (0, 0, 0), 1)
    assert params.text == "Text"
    assert params.size == 0.4
    assert params.vertical_alignment == "preserved"
    source.set_parameters.assert_called_once_with(params)


@pytest.mark.parametrize("selection", ["layer", "effect", "ambiguous", "content", "none"])
def test_text_mask_selection_resolves_only_mask_fonts(host_modules, monkeypatch, selection):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    class PaintLayer:
        pass
    class FillEffect:
        pass
    class Font:
        pass
    layer, effect, source = PaintLayer(), FillEffect(), Font()
    effect.get_source = lambda: source
    effect.get_parent = lambda: layer
    effect.uid = lambda: 1
    layer.mask_effects = lambda: ([effect, effect] if selection == "ambiguous" else
                                  [] if selection == "content" else [effect])
    host_modules.layerstack = SimpleNamespace(PaintLayerNode=PaintLayer, FillEffectNode=FillEffect)
    host_modules.source = SimpleNamespace(SourceFont=Font)
    selected = None if selection == "none" else effect if selection in ("effect", "content") else layer
    monkeypatch.setattr(module, "selected_single_layer", lambda: ("stack", selected))
    if selection in ("ambiguous", "content", "none"):
        with pytest.raises(ValueError):
            module.Panel._selected_source(None)
    else:
        assert module.Panel._selected_source(None) == (effect, source)


@pytest.mark.parametrize("change_font", [False, True])
def test_text_mask_update_preserves_existing_params_and_effect(host_modules, monkeypatch, change_font):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    effect, source, replacement, params = Mock(), Mock(), Mock(), Mock()
    source.resource_id = "old"
    source.get_parameters.return_value = params
    effect.set_source.return_value = replacement
    resource = Mock()
    resource.identifier.return_value = "new" if change_font else "old"
    panel = SimpleNamespace(text=SimpleNamespace(toPlainText=lambda: "Updated"),
                            _selected_source=lambda: (effect, source),
                            font=SimpleNamespace(currentData=lambda: 0), resources=[resource], _apply_params=Mock())
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    module.Panel.update_selected(panel)
    panel._apply_params.assert_called_once_with(replacement if change_font else source, params)
    if change_font:
        effect.set_source.assert_called_once_with(None, "new")
    else:
        effect.set_source.assert_not_called()
    assert effect.method_calls == ([("set_source", (None, "new"), {})] if change_font else [])
    report.assert_not_called()


def test_empty_text_mask_update_does_not_touch_selection(host_modules, monkeypatch):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    panel = SimpleNamespace(text=SimpleNamespace(toPlainText=lambda: "  "), _selected_source=Mock())
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    module.Panel.update_selected(panel)
    panel._selected_source.assert_not_called()
    assert isinstance(report.call_args.args[2], ValueError)


@pytest.mark.parametrize("case", ["success", "missing_channel", "no_project", "selection_failure", "cleanup_failure"])
def test_prepare_text_area_uses_stack_channels_and_cleans_failures(host_modules, monkeypatch, case):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    # A strict API double: paint layers do not expose active_channels.
    class PaintLayer:
        __slots__ = ("set_name",)
    layer = PaintLayer()
    layer.set_name = Mock()
    stack = SimpleNamespace(has_channel=Mock(return_value=case != "missing_channel"))
    monkeypatch.setattr(module, "active_stack", lambda: None if case == "no_project" else stack)
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    host_modules.textureset = SimpleNamespace(ChannelType=SimpleNamespace(BaseColor="base"))
    host_modules.layerstack = SimpleNamespace(
        insert_paint=Mock(return_value=layer),
        InsertPosition=SimpleNamespace(from_textureset_stack=Mock(return_value="root")),
        set_selected_nodes=Mock(), set_selection_type=Mock(), delete_node=Mock(),
        SelectionType=SimpleNamespace(Content="content"))
    api = host_modules.layerstack
    if case in ("selection_failure", "cleanup_failure"):
        api.set_selection_type.side_effect = RuntimeError("Selection failed")
    if case == "cleanup_failure":
        api.delete_node.side_effect = RuntimeError("Cleanup failed")
    module.Panel.prepare_area(None)
    if case == "success":
        report.assert_not_called()
        stack.has_channel.assert_called_once_with("base")
        api.insert_paint.assert_called_once_with("root")
        layer.set_name.assert_called_once_with("MB Text Area: paint here, then Fit")
        api.set_selected_nodes.assert_called_once_with([layer])
        api.set_selection_type.assert_called_once_with(layer, "content")
        api.delete_node.assert_not_called()
    elif case in ("missing_channel", "no_project"):
        api.insert_paint.assert_not_called()
        api.delete_node.assert_not_called()
        assert isinstance(report.call_args.args[2], ValueError)
    else:
        api.delete_node.assert_called_once_with(layer)
        message = str(report.call_args.args[2])
        assert "Selection failed" in message
        if case == "cleanup_failure":
            assert "Cleanup failed" in message


def test_measure_paint_bounds_checks_stack_channel_before_export(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.placement")
    class PaintLayer:
        __slots__ = ()
        def get_parent(self):
            return None
    material = SimpleNamespace(all_uv_tiles=lambda: [], is_layered_material=lambda: False)
    stack = SimpleNamespace(material=lambda: material, has_channel=Mock(return_value=False))
    host_modules.layerstack = SimpleNamespace(PaintLayerNode=PaintLayer)
    host_modules.textureset = SimpleNamespace(ChannelType=SimpleNamespace(BaseColor="base"))
    host_modules.export = SimpleNamespace(export_project_textures=Mock())
    with pytest.raises(ValueError, match="Add Base Color to this texture set"):
        module.measure_paint_bounds(stack, PaintLayer())
    stack.has_channel.assert_called_once_with("base")
    host_modules.export.export_project_textures.assert_not_called()


@pytest.mark.parametrize("degrees", [-180, -45, 0, 90, 180])
def test_text_rotation_preserves_scale_offset_and_other_projection_settings(host_modules, monkeypatch, degrees):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    uv = SimpleNamespace(rotation=23, scale=[-3.0, 4.0], offset=[0.2, -0.1], scale_mode="factors")
    params = SimpleNamespace(uv_transformation=uv, uv_wrapping_mode="none", filtering_mode="sharp")
    node = Mock()
    panel = SimpleNamespace(_selected_uv_projection=lambda: (node, params), _set_rotation_controls=Mock(),
                            _remember_transform=Mock(), _restore_failed_transform=Mock(side_effect=lambda n, p, e: e))
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    module.Panel.rotate_selected(panel, degrees)
    assert uv.rotation == degrees % 360
    assert uv.scale == [-3.0, 4.0]
    assert uv.offset == [0.2, -0.1]
    assert params.uv_wrapping_mode == "none"
    assert params.filtering_mode == "sharp"
    node.set_projection_parameters.assert_called_once_with(params)
    panel._set_rotation_controls.assert_called_once_with(degrees)
    report.assert_not_called()


@pytest.mark.parametrize("axis", [0, 1])
def test_text_flip_preserves_position_rotation_and_toggles_back(host_modules, monkeypatch, axis):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    host_modules.layerstack = SimpleNamespace(ScaleMode=SimpleNamespace(Factors="factors"))
    uv = SimpleNamespace(rotation=37, scale=(3.0, -4.0), offset=[0.25, 0.1], scale_mode="factors")
    params = SimpleNamespace(uv_transformation=uv)
    node = Mock()
    panel = SimpleNamespace(_selected_uv_projection=lambda: (node, params), _remember_transform=Mock(),
                            _restore_failed_transform=Mock(side_effect=lambda n, p, e: e))
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    module.Panel.flip_selected(panel, axis)
    assert uv.scale == ([-3.0, -4.0] if axis == 0 else [3.0, 4.0])
    assert uv.rotation == 37
    assert uv.offset == [0.25, 0.1]
    module.Panel.flip_selected(panel, axis)
    assert uv.scale == [3.0, -4.0]
    assert node.set_projection_parameters.call_count == 2
    report.assert_not_called()


@pytest.mark.parametrize("mode, scale", [("physical", [3, 4]), ("factors", None), ("factors", [0, 4])])
def test_text_flip_refuses_unsupported_scale_without_writing(host_modules, monkeypatch, mode, scale):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    host_modules.layerstack = SimpleNamespace(ScaleMode=SimpleNamespace(Factors="factors"))
    params = SimpleNamespace(uv_transformation=SimpleNamespace(scale_mode=mode, scale=scale))
    node = Mock()
    panel = SimpleNamespace(_selected_uv_projection=lambda: (node, params),
                            _restore_failed_transform=Mock(side_effect=lambda n, p, e: e))
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    module.Panel.flip_selected(panel, 0)
    node.set_projection_parameters.assert_not_called()
    assert isinstance(report.call_args.args[2], ValueError)


@pytest.mark.parametrize("mode", ["uv", "planar"])
def test_text_transform_checks_projection_mode(host_modules, mode):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    host_modules.layerstack = SimpleNamespace(ProjectionMode=SimpleNamespace(UV="uv"))
    node = Mock()
    node.get_projection_mode.return_value = mode
    params = SimpleNamespace(uv_transformation=SimpleNamespace(rotation=0))
    node.get_projection_parameters.return_value = params
    panel = SimpleNamespace(_selected_source=lambda: (node, Mock()))
    if mode == "uv":
        assert module.Panel._selected_uv_projection(panel) == (node, params)
    else:
        with pytest.raises(ValueError, match="UV-projected"):
            module.Panel._selected_uv_projection(panel)
        node.get_projection_parameters.assert_not_called()
    node.set_projection_parameters.assert_not_called()


def test_text_rotation_load_blocks_signals_and_preserves_fractional_source(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    slider, spin = Mock(), Mock()
    slider.blockSignals.return_value = False
    spin.blockSignals.return_value = True
    panel = SimpleNamespace(rotation=slider, rotation_degrees=spin)
    module.Panel._set_rotation_controls(panel, 405.25)
    for widget, previous in ((slider, False), (spin, True)):
        assert widget.method_calls == [
            ("blockSignals", (True,), {}), ("setValue", (45,), {}),
            ("blockSignals", (previous,), {})]
    node = Mock()
    node.get_projection_parameters.return_value = SimpleNamespace(
        uv_transformation=SimpleNamespace(rotation=45.25))
    panel = SimpleNamespace(_set_rotation_controls=Mock())
    module.Panel._load_rotation(panel, node)
    panel._set_rotation_controls.assert_called_once_with(45.25)
    node.set_projection_parameters.assert_not_called()


def test_failed_text_rotation_restores_original_projection(host_modules, monkeypatch):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    params = SimpleNamespace(uv_transformation=SimpleNamespace(rotation=17, scale=[2, 3], offset=[.2, .3]))
    node = Mock()
    node.uid.return_value = 42
    node.set_projection_parameters.side_effect = [RuntimeError("Write failed"), None]
    panel = SimpleNamespace(_selected_uv_projection=lambda: (node, params), _transform_originals={},
                            _set_rotation_controls=Mock())
    panel._remember_transform = lambda n, p: module.Panel._remember_transform(panel, n, p)
    panel._restore_failed_transform = lambda n, p, e: module.Panel._restore_failed_transform(panel, n, p, e)
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    module.Panel.rotate_selected(panel, 90)
    restored = node.set_projection_parameters.call_args.args[0]
    assert restored.uv_transformation.rotation == 17
    assert restored.uv_transformation.scale == [2, 3]
    assert restored.uv_transformation.offset == [.2, .3]
    panel._set_rotation_controls.assert_called_once_with(17)
    assert str(report.call_args.args[2]) == "Write failed"


def test_text_transform_reset_restores_session_snapshot(host_modules, monkeypatch):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    node = Mock()
    node.uid.return_value = 42
    original = SimpleNamespace(uv_transformation=SimpleNamespace(rotation=0, scale=[2, 3], offset=[.2, .3]))
    current = SimpleNamespace(uv_transformation=SimpleNamespace(rotation=90, scale=[-2, 3], offset=[.2, .3]))
    panel = SimpleNamespace(_selected_uv_projection=lambda: (node, current),
                            _transform_originals={42: original}, _set_rotation_controls=Mock())
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    module.Panel.reset_selected_transform(panel)
    restored = node.set_projection_parameters.call_args.args[0]
    assert restored == original
    assert restored is not original
    report.assert_not_called()


def test_paint_coverage_bounds_and_uv_transform(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.placement")
    image = SimpleNamespace(isNull=lambda: False, width=lambda: 10, height=lambda: 10,
                            pixelColor=lambda x, y: SimpleNamespace(
                                red=lambda: 255 if 2 <= x <= 5 and 1 <= y <= 4 else 0))
    bounds = module.coverage_bounds(image)
    assert bounds == pytest.approx((0.2, 0.5, 0.6, 0.9))
    scale, offset = module.placement_transform(bounds)
    assert scale == pytest.approx([3.125, 3.125])
    assert offset == pytest.approx([-0.1, 0.2])
    image.pixelColor = lambda x, y: SimpleNamespace(red=lambda: 0)
    with pytest.raises(ValueError, match="No Base Color"):
        module.coverage_bounds(image)
    image.pixelColor = lambda x, y: SimpleNamespace(red=lambda: 255)
    with pytest.raises(ValueError, match="every image edge"):
        module.coverage_bounds(image)
    image.width = lambda: 2048
    with pytest.raises(ValueError, match="oversized"):
        module.coverage_bounds(image)


@pytest.mark.parametrize("fail", [False, True])
def test_coverage_export_restores_visibility_and_deletes_temp_files(host_modules, monkeypatch, fail):
    from pathlib import Path
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.placement")
    class PaintLayer:
        pass
    layer = PaintLayer()
    layer.get_parent = lambda: None
    layer.uid = lambda: 1
    layer.has_mask = lambda: True
    layer.is_mask_enabled = lambda: True
    layer.enable_mask = Mock()
    layer.is_visible = lambda: False
    layer.set_visible = Mock()
    sibling = Mock()
    sibling.uid.return_value = 2
    sibling.is_visible.return_value = True
    material = SimpleNamespace(all_uv_tiles=lambda: [], is_layered_material=lambda: False)
    stack = SimpleNamespace(material=lambda: material, has_channel=lambda channel: channel == "base")
    host_modules.layerstack = SimpleNamespace(PaintLayerNode=PaintLayer, get_root_layer_nodes=lambda stack: [layer, sibling])
    host_modules.textureset = SimpleNamespace(ChannelType=SimpleNamespace(BaseColor="base"))
    folders = []
    def export(config):
        path = Path(config["exportPath"])
        folders.append(path)
        assert path.is_dir()
        channel = config["exportPresets"][0]["maps"][0]["channels"][0]
        assert channel == {"destChannel": "R", "srcChannel": "A", "srcMapType": "documentMap", "srcMapName": "baseColor"}
        parameters = config["exportPresets"][0]["maps"][0]["parameters"]
        assert parameters["paddingAlgorithm"] == "transparent"
        assert parameters["dilationDistance"] == 0
        assert parameters["sizeLog2"] == 9
        assert parameters["fileFormat"] == "png"
        (path / "coverage.png").write_bytes(b"temporary")
        if fail:
            raise RuntimeError("Export failed")
        return SimpleNamespace(status="success")
    host_modules.export = SimpleNamespace(export_project_textures=export, ExportStatus=SimpleNamespace(Success="success"))
    monkeypatch.setattr(module.QtGui, "QImage", lambda path: "image", raising=False)
    monkeypatch.setattr(module, "coverage_bounds", lambda image: (0.1, 0.2, 0.3, 0.4))
    if fail:
        with pytest.raises(RuntimeError, match="Export failed"):
            module.measure_paint_bounds(stack, layer)
    else:
        assert module.measure_paint_bounds(stack, layer) == (0.1, 0.2, 0.3, 0.4)
    assert layer.set_visible.call_args_list == [((True,), {}), ((False,), {})]
    assert sibling.set_visible.call_args_list == [((False,), {}), ((True,), {})]
    assert layer.enable_mask.call_args_list == [((False,), {}), ((True,), {})]
    assert folders and all(not path.exists() for path in folders)


@pytest.mark.parametrize("fail", [False, True])
def test_fit_painted_area_preserves_paint_and_cleans_incomplete_mask(host_modules, monkeypatch, fail):
    module = importlib.import_module("MBToolkit_3DPainter.features.font_tool.panel")
    class PaintLayer:
        pass
    layer = PaintLayer()
    layer.has_mask = lambda: False
    layer.add_mask, layer.remove_mask = Mock(), Mock()
    effect, source, params = Mock(), Mock(), SimpleNamespace()
    effect.set_source.return_value = source
    source.get_parameters.return_value = params
    if fail:
        effect.set_projection_parameters.side_effect = RuntimeError("Projection failed")
    host_modules.layerstack = SimpleNamespace(
        PaintLayerNode=PaintLayer, MaskBackground=SimpleNamespace(Black="black"),
        insert_fill=Mock(return_value=effect), InsertPosition=SimpleNamespace(inside_node=Mock()),
        NodeStack=SimpleNamespace(Mask="mask"), ProjectionMode=SimpleNamespace(UV="uv"),
        UVWrapMode=SimpleNamespace(RepeatNone="none"), ScaleMode=SimpleNamespace(Factors="factors"),
        UVProjectionParams=lambda **kw: kw, UVTransformationParams=lambda **kw: kw,
        set_selected_nodes=Mock(), set_selection_type=Mock(), SelectionType=SimpleNamespace(Content="content"))
    host_modules.source = SimpleNamespace(HorizontalAlignment=SimpleNamespace(Center="center"),
                                          VerticalAlignment=SimpleNamespace(Middle="middle"))
    monkeypatch.setattr(module, "selected_single_layer", lambda: ("stack", layer))
    monkeypatch.setattr(module, "measure_paint_bounds", lambda stack, layer: (0.2, 0.2, 0.6, 0.6))
    report = Mock()
    monkeypatch.setattr(module, "error", report)
    resource = Mock()
    panel = SimpleNamespace(text=SimpleNamespace(toPlainText=lambda: "Text"),
                            font=SimpleNamespace(currentData=lambda: 0), resources=[resource],
                            _apply_params=Mock(), halign=Mock(), auto_size=Mock())
    module.Panel.fit_painted_area(panel)
    if fail:
        layer.remove_mask.assert_called_once()
        assert isinstance(report.call_args.args[2], RuntimeError)
    else:
        report.assert_not_called()
        layer.remove_mask.assert_not_called()
        assert params.auto_size is True
        assert params.vertical_alignment == "middle"
        assert params.offset == (0, 0)
        host_modules.layerstack.set_selection_type.assert_called_once_with(layer, "content")


def test_event_start_is_idempotent_and_stop_retries_failures(host_modules):
    dispatcher = Mock()
    classes = [type(name, (), {}) for name in ("Changed", "Entered", "Closed")]
    host_modules.event = SimpleNamespace(
        DISPATCHER=dispatcher, LayerStacksModelDataChanged=classes[0],
        ProjectEditionEntered=classes[1], ProjectClosed=classes[2])
    module = importlib.import_module("MBToolkit_3DPainter.core.events")
    bus = module.EventBus()
    bus.start()
    bus.start()
    assert dispatcher.connect.call_count == 3
    bus.add(Mock())
    dispatcher.disconnect.side_effect = [RuntimeError("Temporary failure"), None, None]
    bus.stop()
    assert dispatcher.disconnect.call_count == 3
    assert len(bus.connected) == 1
    assert not bus.listeners
    dispatcher.disconnect.side_effect = None
    bus.stop()
    assert not bus.connected
    assert dispatcher.disconnect.call_count == 4


@pytest.mark.parametrize("raw,expected", [
    ("BaseColor", "Base Color"), ("Normal", "Normal"),
    ("LinearDodge", "Linear Dodge"), ("RGBColor", "RGB Color"),
    ("User_Channel", "User Channel")])
def test_blending_readable_labels(host_modules, raw, expected):
    module = importlib.import_module("MBToolkit_3DPainter.features.channel_blending.panel")
    assert module.display_name(raw) == expected


@pytest.mark.parametrize("handler,peer", [("_slider_changed", "percent"), ("_percent_changed", "slider")])
def test_blending_inputs_sync_without_feedback(host_modules, handler, peer):
    module = importlib.import_module("MBToolkit_3DPainter.features.channel_blending.panel")
    widget = Mock()
    widget.blockSignals.return_value = False
    row = SimpleNamespace(panel=Mock(), channel="color", percent=Mock(), slider=Mock())
    setattr(row, peer, widget)
    getattr(module.ChannelRow, handler)(row, 42)
    assert widget.method_calls == ([("setSpecialValueText", ("",), {})] if peer == "percent" else []) + [
        ("blockSignals", (True,), {}), ("setValue", (42,), {}),
        ("blockSignals", (False,), {})]
    row.panel._queue.assert_called_once_with("color", 42)


@pytest.mark.parametrize("selected", ["same", "different", None])
def test_blending_flush_guards_selection(host_modules, monkeypatch, selected):
    module = importlib.import_module("MBToolkit_3DPainter.features.channel_blending.panel")
    node = Mock()
    node.uid.return_value = "same"
    current = SimpleNamespace(uid=lambda: selected) if selected else None
    monkeypatch.setattr(module, "selected_single_layer", lambda: (None, current))
    panel = SimpleNamespace(_timer=Mock(), _refresh_timer=Mock(),
                            _pending={"color": (node, .42)})
    module.Panel._flush(panel)
    if selected == "same":
        node.set_opacity.assert_called_once_with(.42, "color")
    else:
        node.set_opacity.assert_not_called()
    assert panel._pending == {}


def test_blending_refresh_reuses_rows(host_modules, monkeypatch):
    module = importlib.import_module("MBToolkit_3DPainter.features.channel_blending.panel")
    host_modules.layerstack = SimpleNamespace(NodeType=SimpleNamespace(PaintLayer="paint", FillLayer="fill"))
    node = SimpleNamespace(uid=lambda: "same", get_type=lambda: "fill",
                           has_blending=lambda: True, get_name=lambda: "Metal")
    stack = SimpleNamespace(all_channels=lambda: ["color"])
    monkeypatch.setattr(module, "selected_single_layer", lambda: (stack, node))
    row = Mock()
    row.is_editing.return_value = False
    panel = SimpleNamespace(_dragging=0, _pending={}, node=node,
                            _channels={"color": row}, caption=Mock(), status=Mock(), area=Mock(), all_row=Mock())
    panel.all_row.is_editing.return_value = False
    module.Panel.refresh(panel)
    assert panel._channels["color"] is row
    row.sync.assert_called_once_with(node)


def test_blending_refresh_defers_in_progress_edit(host_modules, monkeypatch):
    module = importlib.import_module("MBToolkit_3DPainter.features.channel_blending.panel")
    host_modules.layerstack = SimpleNamespace(NodeType=SimpleNamespace(PaintLayer="paint", FillLayer="fill"))
    node = SimpleNamespace(uid=lambda: "same", get_type=lambda: "fill", has_blending=lambda: True)
    monkeypatch.setattr(module, "selected_single_layer",
                        lambda: (SimpleNamespace(all_channels=lambda: ["color"]), node))
    row = Mock()
    row.is_editing.return_value = True
    panel = SimpleNamespace(_dragging=0, _pending={}, node=node,
                            _channels={"color": row}, _refresh_timer=Mock(), all_row=Mock())
    panel.all_row.is_editing.return_value = False
    module.Panel.refresh(panel)
    row.sync.assert_not_called()
    panel._refresh_timer.start.assert_called_once()


def test_blending_bulk_targets_exclude_unavailable_channels(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.channel_blending.panel")
    panel = SimpleNamespace(_channels={
        "color": SimpleNamespace(isEnabled=lambda: True),
        "height": SimpleNamespace(isEnabled=lambda: False)})
    assert module.Panel._targets(panel, None) == ["color"]
    assert module.Panel._targets(panel, "color") == ["color"]


def test_blending_bulk_opacity_queues_individual_channels(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.channel_blending.panel")
    node = object()
    panel = SimpleNamespace(node=node, _targets=lambda channel: ["color", "roughness"],
                            _pending={}, _timer=Mock())
    module.Panel._queue(panel, None, 35)
    assert panel._pending == {"color": (node, .35), "roughness": (node, .35)}


@pytest.mark.parametrize("selected", ["same", "different"])
def test_blending_bulk_mode_checks_selection(host_modules, monkeypatch, selected):
    module = importlib.import_module("MBToolkit_3DPainter.features.channel_blending.panel")
    node = Mock()
    node.uid.return_value = "same"
    monkeypatch.setattr(module, "selected_single_layer",
                        lambda: (None, SimpleNamespace(uid=lambda: selected)))
    panel = SimpleNamespace(node=node, _targets=lambda channel: ["color", "roughness"],
                            request_refresh=Mock())
    module.Panel._set_mode(panel, None, "normal")
    assert node.set_blending_mode.call_count == (2 if selected == "same" else 0)


def test_blending_reset_uses_explicit_normal_and_full_opacity(host_modules):
    module = importlib.import_module("MBToolkit_3DPainter.features.channel_blending.panel")
    host_modules.layerstack = SimpleNamespace(BlendingMode=SimpleNamespace(__members__={"Normal": "normal"}))
    panel = SimpleNamespace(node=object(), _set_mode=Mock(), _queue=Mock(), _flush=Mock())
    module.Panel._reset(panel, None)
    panel._set_mode.assert_called_once_with(None, "normal")
    panel._queue.assert_called_once_with(None, 100)
    panel._flush.assert_called_once()