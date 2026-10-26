"""Run real Qt in a subprocess so other tests' lightweight Qt doubles cannot leak in."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional offscreen Qt")
def test_layout_drag_defers_refresh_and_preserves_inline_boundary_and_frame_positions():
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
from types import SimpleNamespace
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from PySide6 import QtWidgets, QtCore, QtGui, QtTest
from layer_graph_fixtures import Host
from MBToolkit_3DPainter.features.layer_graph.model import ROOT, TYPES
from MBToolkit_3DPainter.features.layer_graph.panel import Panel
from MBToolkit_3DPainter.features.layer_graph.canvas import FrameItem
application = QtWidgets.QApplication([])
host = Host()
def create(kind, scope=ROOT):
    return host.adapter.create(TYPES[kind], host.adapter.context(), scope, None)
group = create('group')
child = create('fill', (group, 'layers'))
a = create('fill')
b = create('paint')
listeners = set()
panel = Panel(SimpleNamespace(events=SimpleNamespace(add=listeners.add, remove=listeners.discard)), host.adapter)
panel.show()
QtTest.QTest.qWait(30)
panel.toggle(group)
view = panel.view()
view.resetTransform()
native_order = list(host.roots)
def drag_start(item, local=QtCore.QPointF(100, 40)):
    view.centerOn(item)
    point = view.mapFromScene(item.mapToScene(local))
    QtTest.QTest.mousePress(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
    assert view.layout_drag
    return point
def drag_move(point, delta):
    target = point + delta
    event = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, QtCore.QPointF(target),
        QtCore.QPointF(view.viewport().mapToGlobal(target)), QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    application.sendEvent(view.viewport(), event)
    return target
def finish(point):
    QtTest.QTest.mouseRelease(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
    assert not view.layout_drag
    QtTest.QTest.qWait(350)
    assert not panel.pending_refresh
def position(uid):
    return QtCore.QPointF(view.cards[uid].pos())
# Exercise real press/move/release with native-refresh and direct rebuild attempts
# while the button remains held longer than the coalescing timer interval.
for uid in [a, child, '@input', '@output', f'@input:layers:{group}', f'@output:layers:{group}']:
    view.scene().clearSelection()
    card = view.cards[uid]
    before = position(uid)
    point = drag_start(card)
    target = drag_move(point, QtCore.QPoint(43, 27))
    moved = position(uid)
    assert moved == before + QtCore.QPointF(43, 27), (uid, before, moved)
    for _ in range(3):
        panel.request_refresh()
    panel.refresh()
    view.rebuild()
    panel.arrange(view)
    QtTest.QTest.qWait(350)
    assert view.cards[uid] is card and position(uid) == moved
    assert panel.pending_refresh and view.layout_drag
    finish(target)
    assert view.cards[uid] is not card and position(uid) == moved
    panel.refresh()
    assert position(uid) == moved
# Moving an expanded owner keeps its whole branch at the new placement on refresh.
before = {uid: position(uid) for uid in [group, *view.branch_children[group]]}
view.cards[group].moveBy(21, 19)
panel.refresh()
for uid, old in before.items():
    assert position(uid) == old + QtCore.QPointF(21, 19)
# Multiple selected nodes retain their relative offset and final locations.
view.scene().clearSelection()
view.cards[a].setSelected(True)
view.cards[b].setSelected(True)
before = {uid: position(uid) for uid in [a, b]}
point = drag_start(view.cards[a])
target = drag_move(point, QtCore.QPoint(31, 17))
panel.request_refresh()
finish(target)
for uid, old in before.items():
    assert position(uid) == old + QtCore.QPointF(31, 17)
    assert view.cards[uid].isSelected()
# Expanded visual frames move their members without snapping back after refresh.
frame = panel.layout.frame(ROOT, [a, b], 'Placement')
view.rebuild()
view.scene().clearSelection()
frame_item = next(item for item in view.scene().items() if isinstance(item, FrameItem))
before = {uid: position(uid) for uid in [a, b]}
point = drag_start(frame_item, QtCore.QPointF(80, 20))
target = drag_move(point, QtCore.QPoint(29, 23))
panel.request_refresh()
finish(target)
for uid, old in before.items():
    assert position(uid) == old + QtCore.QPointF(29, 23)
# Escape and lost activation release the guard and flush queued refreshes.
for interrupted in ['escape', 'deactivate', 'hide']:
    point = drag_start(view.cards[a])
    panel.request_refresh()
    if interrupted == 'escape':
        QtTest.QTest.keyClick(view, QtCore.Qt.Key.Key_Escape)
    elif interrupted == 'deactivate':
        application.sendEvent(view, QtCore.QEvent(QtCore.QEvent.Type.WindowDeactivate))
    else:
        view.hide()
        view.show()
    assert not view.layout_drag
    finish(point)
# A project/session change must invalidate even an actively held gesture.
point = drag_start(view.cards[a])
host.epoch += 1
panel.check_context()
assert not view.layout_drag
assert not panel.layout.frames
assert panel.snapshot.context == host.adapter.context()
finish(point)
assert host.roots == native_order
panel.arrange(view)
assert position('@input') == QtCore.QPointF(-310, 0)
assert all(view.cards[uid].y() == 0 for uid in panel.snapshot.members(ROOT))
panel.dispose()
panel.close()
assert not listeners
print('Free layout drag regression passed')
'''
    result = subprocess.run([sys.executable, "-B", "-c", script,
                             str(root / "painter_python" / "plugins"), str(root / "tests")],
                            capture_output=True, text=True, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional offscreen Qt")
def test_right_click_creation_targets_content_mask_and_nested_frames():
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
from types import SimpleNamespace
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from PySide6 import QtWidgets, QtCore, QtGui, QtTest
from layer_graph_fixtures import Host
from MBToolkit_3DPainter.features.layer_graph.model import ROOT, TYPES
from MBToolkit_3DPainter.features.layer_graph.panel import Panel, Browser
application = QtWidgets.QApplication([])
host = Host()
def create(kind, scope=ROOT, selected=None):
    return host.adapter.create(TYPES[kind], host.adapter.context(), scope, selected)
group = create('group')
layer = create('fill', (group, 'layers'))
create('black', (group, 'layers'), selected=layer)
effect = create('levels', (layer, 'content'))
listeners = set()
panel = Panel(SimpleNamespace(events=SimpleNamespace(add=listeners.add, remove=listeners.discard)), host.adapter)
panel.show()
QtTest.QTest.qWait(30)
view = panel.view()
def card_point(uid, x=120, y=40):
    return view.cards[uid].mapToScene(QtCore.QPointF(x, y))
def background_point(scope):
    return view.branch_frames[scope].rect().topLeft() + QtCore.QPointF(8, 65)
def insert_at(scene_point, scope, selected=None, shift=False):
    view.centerOn(scene_point)
    point = view.mapFromScene(scene_point)
    target = view.context_target(point)
    assert target[1:] == (selected, scope), (target[1:], scope)
    errors = []
    def choose(dialog):
        try:
            assert isinstance(dialog, Browser)
            assert (dialog.scope, dialog.selected) == (scope, selected)
            dialog.query.setText('fill')
            ids = [dialog.list.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
                   for i in range(dialog.list.count())]
            expected = 'fill' if scope[1] == 'layers' else 'fill_fx'
            assert expected in ids, ids
            assert ('fill_fx' if expected == 'fill' else 'fill') not in ids, ids
            dialog.list.setCurrentRow(ids.index(expected))
            dialog.choose()
        except Exception as exc:
            errors.append(repr(exc))
            if dialog:
                dialog.reject()
    def choose_popup():
        popup = application.activePopupWidget()
        if shift:
            try:
                assert isinstance(popup, QtWidgets.QMenu)
                action = next(a for a in popup.actions() if a.text() == 'Add Node…')
                popup.close()
                QtCore.QTimer.singleShot(0, lambda: choose(application.activePopupWidget()))
                action.trigger()
            except Exception as exc:
                errors.append(repr(exc))
                if popup:
                    popup.close()
        else:
            choose(popup)
    before = set(panel.snapshot.nodes)
    QtCore.QTimer.singleShot(0, choose_popup)
    modifiers = QtCore.Qt.KeyboardModifier.ShiftModifier if shift else QtCore.Qt.KeyboardModifier.NoModifier
    view.contextMenuEvent(QtGui.QContextMenuEvent(QtGui.QContextMenuEvent.Reason.Mouse, point,
                          view.viewport().mapToGlobal(point), modifiers))
    assert not errors, errors
    added = set(panel.snapshot.nodes) - before
    assert len(added) == 1, added
    node = panel.snapshot.nodes[added.pop()]
    assert node.scope == scope
    assert node.layer == (scope[1] == 'layers')
    host.delete(host.nodes[int(node.id)])
    panel.refresh()

# A group body also owns content effects, rather than implicitly adding children.
insert_at(card_point(group), (group, 'content'))
panel.toggle(layer)
assert layer in view.cards
insert_at(card_point(layer), (layer, 'content'))
insert_at(card_point(layer, 220, 50), (layer, 'mask'))
insert_at(background_point((layer, 'content')), (layer, 'content'))
insert_at(background_point((layer, 'mask')), (layer, 'mask'))
insert_at(card_point(effect), (layer, 'content'), effect)
for domain in ('content', 'mask'):
    for side in ('input', 'output'):
        insert_at(card_point(f'@{side}:{domain}:{layer}'), (layer, domain))
insert_at(background_point((layer, 'mask')), (layer, 'mask'), shift=True)
insert_at(card_point(layer), (layer, 'content'), shift=True)
insert_at(background_point((group, 'layers')), (group, 'layers'))
insert_at(QtCore.QPointF(-450, -350), ROOT)
panel.open_scope((layer, 'mask'))
view = panel.view()
insert_at(card_point('@input'), (layer, 'mask'))
panel.dispose()
panel.close()
'''
    result = subprocess.run([sys.executable, "-B", "-c", script,
                             str(root / "painter_python" / "plugins"), str(root / "tests")],
                            capture_output=True, text=True, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional offscreen Qt")
def test_order_arrangement_and_batch_native_handoff_are_non_destructive():
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
from types import SimpleNamespace
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from PySide6 import QtWidgets, QtCore, QtGui, QtTest
from layer_graph_fixtures import Host
from MBToolkit_3DPainter.features.layer_graph.model import ROOT, TYPES
from MBToolkit_3DPainter.features.layer_graph.panel import Panel
application = QtWidgets.QApplication([])
host = Host()
def create(kind, scope=ROOT):
    return host.adapter.create(TYPES[kind], host.adapter.context(), scope)
a, b, group = create('fill'), create('paint'), create('group')
child = create('fill', (group, 'layers'))
listeners = set()
panel = Panel(SimpleNamespace(events=SimpleNamespace(add=listeners.add, remove=listeners.discard)), host.adapter)
panel.show()
QtTest.QTest.qWait(30)
view = panel.view()
panel.open_scope((group, 'layers'))
other = panel.view()
other.cards[child].moveBy(80, 50)
other_positions = {key: value for key, value in panel.layout.positions.items() if key[0] == other.scope}
panel.open_scope(ROOT)
view.cards[a].moveBy(1000, 300)
view.cards[b].moveBy(-200, 400)
view.cards[a].setSelected(True)
view.cards[b].setSelected(True)
frame = panel.layout.frame(ROOT, [a, b], 'Keep this frame')
view.rebuild()
before = host.adapter.scan()
transform = view.transform()
original_scan = host.adapter.scan
def no_host_scan():
    raise AssertionError('Layout arrangement must not scan Painter')
host.adapter.scan = no_host_scan
panel.arrange(view)
host.adapter.scan = original_scan
assert view.cards[a].x() < view.cards[b].x() < view.cards[group].x()
assert set(view.selected_ids()) == {a, b}
assert frame.id in panel.layout.frames
assert view.transform() == transform
assert {key: value for key, value in panel.layout.positions.items() if key[0] == other.scope} == other_positions
assert host.adapter.scan() == before
assert 'material are unchanged' in panel.status.text()
panel.reorder_selection_native((a,b))
assert [str(node.uid()) for node in host.selected] == [b,a]
assert host.adapter.scan() == before
actions = []
def inspect():
    menu = application.activePopupWidget()
    try:
        actions.extend(action.text() for action in menu.actions())
        order = next(action.menu() for action in menu.actions() if action.text() == 'Evaluation Order')
        actions.extend(action.text() for action in order.actions())
    finally:
        menu.close()
point = view.mapFromScene(view.cards[a].mapToScene(QtCore.QPointF(120,40)))
QtCore.QTimer.singleShot(10, inspect)
view.contextMenuEvent(QtGui.QContextMenuEvent(QtGui.QContextMenuEvent.Reason.Mouse, point,
                      view.viewport().mapToGlobal(point), QtCore.Qt.KeyboardModifier.ShiftModifier))
assert 'Arrange by Evaluation Order (Layout Only)' in actions
assert 'Select All in Painter to Reorder…' in actions
panel.dispose()
panel.close()
assert not listeners
'''
    result = subprocess.run([sys.executable, "-B", "-c", script,
                             str(root / "painter_python" / "plugins"), str(root / "tests")],
                            capture_output=True, text=True, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional offscreen Qt")
def test_connection_drag_mask_preview_and_popup_dismissal(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
from types import SimpleNamespace
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from PySide6 import QtWidgets, QtCore, QtGui, QtTest
from layer_graph_fixtures import Host
from MBToolkit_3DPainter.features.layer_graph.model import ROOT, TYPES
from MBToolkit_3DPainter.features.layer_graph.panel import Panel, Browser
application = QtWidgets.QApplication([])
host = Host()
context = host.adapter.context()
a = host.adapter.create(TYPES['fill'], context, ROOT)
b = host.adapter.create(TYPES['paint'], context, ROOT)
host.adapter.create(TYPES['black'], context, ROOT, a)
listeners = set()
panel = Panel(SimpleNamespace(events=SimpleNamespace(add=listeners.add, remove=listeners.discard)), host.adapter)
panel.resize(1200, 760)
panel.show()
QtTest.QTest.qWait(50)
view = panel.view()
assert view.cards['@input'].brush().color().name() == '#195681'
assert set(view.cards['@input'].ports) == {'output'}
assert set(view.cards['@output'].ports) == {'input'}
def port(uid, side):
    item = view.cards[uid].ports[side]
    return view.mapFromScene(item.mapToScene(item.rect().center()))
def drag(start, end):
    QtTest.QTest.mousePress(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=start)
    assert view.connection_drag is not None
    QtTest.QTest.mouseMove(view.viewport(), end, delay=10)
    QtTest.QTest.mouseRelease(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=end)
    application.processEvents()
empty = QtCore.QPoint(30, view.viewport().height()-30)
drag(port(a, 'output'), empty)
assert panel.snapshot.nodes[a].disconnected
assert not host.nodes[int(a)].visible
assert all(a not in wire.data(0)[:2] for wire in view.wires)
drag(port(a, 'output'), port(b, 'input'))
assert not panel.snapshot.nodes[a].disconnected
assert host.nodes[int(a)].visible
QtTest.QTest.mousePress(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=port(a, 'output'))
panel.refresh()
assert view.connection_drag is not None
QtTest.QTest.keyClick(view, QtCore.Qt.Key.Key_Escape)
assert view.connection_drag is None
assert host.nodes[int(a)].visible
QtTest.QTest.mouseRelease(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=empty)
panel.timer.stop()
panel.pending_refresh = False
drag(port(a, 'output'), port(a, 'input'))
assert host.nodes[int(a)].visible
assert 'itself' in panel.status.text()
# Exercise grabbing the wire itself, not just the port.
wire = next(w for w in view.wires if w.data(0)[:2] == (a, b))
midpoint = view.mapFromScene(wire.path().pointAtPercent(.5))
drag(midpoint, empty)
assert panel.snapshot.nodes[a].disconnected
drag(port(a, 'output'), port(b, 'input'))
window = QtWidgets.QMainWindow()
action = QtGui.QAction('View Mask', window)
triggered = []
action.triggered.connect(lambda: triggered.append(True))
host.sp.ui = SimpleNamespace(get_main_window=lambda: window)
mask = view.mapFromScene(view.cards[a].mapToScene(view.cards[a].mask_rect.center()))
QtTest.QTest.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton,
                       QtCore.Qt.KeyboardModifier.AltModifier, mask)
assert triggered == [True]
assert host.selection_type == 'mask'
panel.open_scope((a, 'mask'))
assert panel.view().cards['@input'].mask_master
panel.view().grab()  # Force icon painting.
browser = Browser(panel, ROOT, None)
browser.move(panel.mapToGlobal(QtCore.QPoint(200, 100)))
browser.show()
application.processEvents()
outside = QtCore.QPointF(browser.width()+30, browser.height()+30)
event = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, outside,
                         QtCore.QPointF(browser.mapToGlobal(outside.toPoint())),
                         QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.LeftButton,
                         QtCore.Qt.KeyboardModifier.NoModifier)
application.sendEvent(browser, event)
assert not browser.isVisible()
assert browser.result() == QtWidgets.QDialog.DialogCode.Rejected
browser.show()
application.processEvents()
application.sendEvent(application, QtCore.QEvent(QtCore.QEvent.Type.ApplicationDeactivate))
assert not browser.isVisible()
browser = Browser(panel, ROOT, None)
browser.move(panel.mapToGlobal(QtCore.QPoint(200, 100)))
click_dismissed = []
def click_away():
    assert browser.windowModality() == QtCore.Qt.WindowModality.NonModal
    QtTest.QTest.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(5,5))
    click_dismissed.append(not browser.isVisible())
QtCore.QTimer.singleShot(20, click_away)
QtCore.QTimer.singleShot(500, browser.reject)
assert panel.exec_dialog(browser) == QtWidgets.QDialog.DialogCode.Rejected
assert not browser.isVisible()
assert click_dismissed == [True]
browser = Browser(panel, ROOT, None)
browser.show()
application.processEvents()
application.sendEvent(browser, QtCore.QEvent(QtCore.QEvent.Type.WindowDeactivate))
assert not browser.isVisible()
browser.close()
# The Shift-right-click management menu uses Qt's ordinary popup dismissal.
menus_closed = []
def dismiss_menu():
    menu = application.activePopupWidget()
    assert isinstance(menu, QtWidgets.QMenu)
    outside = QtCore.QPointF(-20, -20)
    event = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, outside,
                             QtCore.QPointF(menu.mapToGlobal(outside.toPoint())),
                             QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.LeftButton,
                             QtCore.Qt.KeyboardModifier.NoModifier)
    application.sendEvent(menu, event)
    menus_closed.append(not menu.isVisible())
QtCore.QTimer.singleShot(20, dismiss_menu)
event = QtGui.QContextMenuEvent(QtGui.QContextMenuEvent.Reason.Mouse, QtCore.QPoint(5,5),
                                view.viewport().mapToGlobal(QtCore.QPoint(5,5)),
                                QtCore.Qt.KeyboardModifier.ShiftModifier)
view.contextMenuEvent(event)
assert menus_closed == [True]
# Hover validation uses only the existing snapshot, even over repeated valid targets.
original_scan = host.adapter.scan
original_context = host.adapter.context
def forbidden_host_access():
    raise AssertionError('Hover must not access Painter')
assert view.begin_connection(a, 'output', port(a, 'output'))
host.adapter.scan = forbidden_host_access
host.adapter.context = forbidden_host_access
try:
    for _ in range(20):
        view.move_connection(port(b, 'input'))
        assert not view.drop_reason((b, 'input'))
finally:
    host.adapter.scan = original_scan
    host.adapter.context = original_context
view.cancel_connection()
panel.reorder_native(a)
assert host.selected == [host.nodes[int(a)]]
assert 'No verified public native move API' in panel.status.text()
order_actions = []
def inspect_order_menu():
    menu = application.activePopupWidget()
    try:
        submenu = next(action.menu() for action in menu.actions() if action.text() == 'Evaluation Order')
        commands = [action for action in submenu.actions() if not action.isSeparator()]
        order_actions.extend((action.text(), action.isEnabled(), action.toolTip()) for action in commands)
    finally:
        menu.close()
point = view.mapFromScene(view.cards[a].mapToScene(QtCore.QPointF(120, 40)))
QtCore.QTimer.singleShot(20, inspect_order_menu)
view.contextMenuEvent(QtGui.QContextMenuEvent(QtGui.QContextMenuEvent.Reason.Mouse, point,
                      view.viewport().mapToGlobal(point), QtCore.Qt.KeyboardModifier.ShiftModifier))
assert len(order_actions) == 5
assert all(not enabled and 'No verified public native move API' in tooltip
           for text, enabled, tooltip in order_actions[:4])
assert order_actions[-1][0] == 'Select in Painter to Reorder…' and order_actions[-1][1]
# A project change cancels the stale gesture instead of deferring refresh forever.
assert view.begin_connection(a, 'output', port(a, 'output'))
host.epoch += 1
panel.check_context()
assert view.connection_drag is None
assert panel.snapshot.context == host.adapter.context()
assert not panel.pending_refresh
panel.dispose()
panel.close()
'''
    path = tmp_path / "connections.py"
    path.write_text(script, encoding="utf-8")
    result = subprocess.run([sys.executable, str(path), str(root / "painter_python" / "plugins"),
                             str(root / "tests")], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional offscreen Qt")
def test_layer_graph_canvas_browser_tabs_frames_and_lifecycle(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
from types import SimpleNamespace
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from PySide6 import QtWidgets, QtCore, QtTest
from layer_graph_fixtures import Host
from MBToolkit_3DPainter.features.layer_graph.model import ROOT, TYPES
from MBToolkit_3DPainter.features.layer_graph.panel import Panel, Browser, ResourcePicker
application = QtWidgets.QApplication([])
host = Host()
adapter = host.adapter
def create(kind, scope=ROOT, selected=None, resource=None):
    return adapter.create(TYPES[kind], adapter.context(), scope, selected, resource)
a = create('fill')
b = create('paint')
group = create('group')
child = create('fill', (group, 'layers'))
create('black', (group, 'layers'), selected=child)
generator = create('generator', (child, 'mask'), resource='generator')
levels = create('levels', (child, 'mask'), generator)
listeners = set()
app = SimpleNamespace(events=SimpleNamespace(add=listeners.add, remove=listeners.discard))
panel = Panel(app, adapter)
panel.resize(1200, 760)
panel.show()
QtTest.QTest.qWait(50)
assert len(panel.snapshot.nodes) == 6
view = panel.view()
assert len(view.cards) == 5
assert len(view.wires) == 4
def accept_fill_browser():
    dialog = application.activePopupWidget()
    assert isinstance(dialog, Browser)
    dialog.query.setText('fill layer')
    dialog.choose()
QtCore.QTimer.singleShot(0, accept_fill_browser)
panel.browser(view, QtCore.QPointF(700, 260), b)
assert len(panel.snapshot.nodes) == 7
created = str(host.selected[0].uid())
assert panel.layout.positions[(ROOT, created)] == (700., 260.)
host.delete(host.nodes[int(created)])
panel.refresh()
resource = SimpleNamespace(gui_name=lambda: 'Edge Wear',
                           identifier=lambda: SimpleNamespace(url=lambda: 'resource://edge-wear'))
picker = ResourcePicker([resource], panel)
picker.query.setText('edge')
assert picker.list.count() == 1
picker.choose()
assert picker.chosen.url() == 'resource://edge-wear'
picker.close()
view.cards[a].setSelected(True)
view.cards[b].setSelected(False)
assert panel.inspected == a
before = view.cards[a].pos()
view.cards[a].moveBy(50, 80)
assert panel.layout.positions[(ROOT, a)] == (before.x()+50, before.y()+80)
saved_positions = dict(panel.layout.positions)
saved_transform = view.transform()
native_order = list(host.roots)
host.roots.reverse()
for _ in range(10):
    panel.request_refresh()
panel.refresh()
assert panel.snapshot.members(ROOT) == [str(node.uid()) for node in reversed(host.roots)]
assert panel.layout.positions == saved_positions
assert view.transform() == saved_transform
assert view.cards[a].isSelected()
assert not panel.timer.isActive() and not panel.pending_refresh
expected = ['@input', *panel.snapshot.members(ROOT), '@output']
assert [(x, y) for x, y, domain in view.links] == list(zip(expected, expected[1:]))
# Simulate native Undo restoring the exact chain; no custom graph history is involved.
host.roots[:] = native_order
panel.request_refresh()
panel.refresh()
assert panel.snapshot.members(ROOT) == [str(node.uid()) for node in reversed(native_order)]
assert panel.layout.positions == saved_positions
assert view.wires[0].path().elementCount() > 0
panel.open_scope((group, 'layers'))
assert panel.tabs.count() == 2
panel.open_scope((group, 'layers'))
assert panel.tabs.count() == 2
panel.open_scope((child, 'mask'))
assert panel.tabs.count() == 3
mask_view = panel.view()
assert len(mask_view.cards) == 4
assert len(mask_view.wires) == 3
assert mask_view.cards['@input'].toolTip().startswith('Black Background')
assert 'GroupLayer' in panel.tabs.tabToolTip(panel.tabs.currentIndex())
browser = Browser(panel, (child, 'mask'), generator)
browser.query.setText('levels')
assert browser.list.count() == 1
assert browser.list.item(0).text() == 'Levels'
browser.choose()
assert browser.chosen.id == 'levels'
browser.close()
browser = Browser(panel, ROOT, None)
browser.query.setText('compare')
assert browser.list.count() == 0
assert 'available here' in browser.reason.text()
browser.query.setText('not-a-node')
assert not browser.list.count()
browser.close()
panel.open_scope(ROOT)
view = panel.view()
frame = panel.layout.frame(ROOT, [a,b], 'Surface')
view.rebuild()
assert len(panel.layout.frames) == 1
view.toggle_frame(frame.id)
assert frame.collapsed
assert a not in view.cards and b not in view.cards
assert '@frame:'+frame.id in view.cards
assert len(view.wires) == 3
view.cards['@frame:'+frame.id].moveBy(60, 30)
view.toggle_frame(frame.id)
assert not frame.collapsed and a in view.cards and b in view.cards
assert len(view.wires) == 4
panel.toggle(group)
assert child in view.cards
panel.toggle(group)
assert child not in view.cards
view.zoom(100)
assert view.transform().m11() <= 2.5
view.zoom(.00001)
assert view.transform().m11() >= .1499
view.fit()
assert panel.grab().width() > 0
panel.open_scope((child, 'mask'))
host.delete(host.nodes[int(group)])
panel.refresh()
assert panel.tabs.count() == 1
assert panel.view().scope == ROOT
host.epoch += 1
panel.refresh()
assert not panel.layout.frames
host.opened = False
panel.refresh()
assert not panel.snapshot.nodes and not panel.view().cards
assert 'editable' in panel.status.text()
host.opened = True
panel.refresh()
assert len(panel.snapshot.nodes) == 2
host.nodes[int(a)].content_effects = lambda: (_ for _ in ()).throw(RuntimeError('scan failed'))
panel.refresh()
assert 'editing disabled' in panel.status.text()
assert not panel.view().cards
panel.dispose()
assert not listeners and not panel.timer.isActive() and not panel.poll.isActive()
panel.close()
print('Layer Graph offscreen UI checks passed')
'''
    result = subprocess.run([sys.executable, "-B", "-c", script,
                             str(root / "painter_python" / "plugins"), str(root / "tests")],
                            capture_output=True, text=True, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional offscreen Qt")
def test_direct_node_controls_mask_regions_and_delete_keyboard():
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
from types import SimpleNamespace
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from PySide6 import QtWidgets, QtCore, QtTest
from layer_graph_fixtures import Host
from MBToolkit_3DPainter.features.layer_graph.model import ROOT, TYPES
from MBToolkit_3DPainter.features.layer_graph.panel import Panel
application = QtWidgets.QApplication([])
host = Host()
adapter = host.adapter
def create(kind, scope=ROOT, selected=None):
    return adapter.create(TYPES[kind], adapter.context(), scope, selected)
a = create('fill')
create('black', selected=a)
fx = create('levels', (a, 'mask'))
content_fx = create('levels', (a, 'content'))
group = create('group')
child = create('paint', (group, 'layers'))
create('white', (group, 'layers'), selected=child)
nested_fx = create('levels', (child, 'mask'))
empty_group = create('group', (group, 'layers'))
listeners = set()
panel = Panel(SimpleNamespace(events=SimpleNamespace(add=listeners.add, remove=listeners.discard)), adapter)
panel.show()
QtTest.QTest.qWait(30)
from MBToolkit_3DPainter.features.layer_graph.panel import Browser
from MBToolkit_3DPainter.features.layer_graph.icons import KINDS, draw
from PySide6 import QtGui
assert KINDS['AnchorPointEffect'] == 'anchor' and KINDS['PaintLayer'] == 'brush'
image = QtGui.QImage(30,30,QtGui.QImage.Format.Format_ARGB32)
painter = QtGui.QPainter(image)
for kind in KINDS:
    draw(painter, kind, 1, 1, QtGui.QColor('white'))
painter.end()
popup = Browser(panel, ROOT, None)
assert not popup.findChildren(QtWidgets.QDialogButtonBox)
assert all(' / ' not in popup.list.item(i).text() for i in range(popup.list.count())
           if popup.list.item(i).data(QtCore.Qt.ItemDataRole.UserRole) != 'group')
popup.query.setText('levels')
assert popup.list.count() == 0
popup.query.clear()
QtTest.QTest.keyClick(popup.query, QtCore.Qt.Key.Key_Down)
assert popup.list.currentRow() == 1
popup.close()
resource = SimpleNamespace(gui_name=lambda: 'Wear', identifier=lambda: 'wear-id')
adapter.resources = lambda usage: [resource]
popup = Browser(panel, (a,'mask'), fx)
popup.query.setText('generator')
popup.choose()
assert popup.resource_type.id == 'generator' and popup.chosen is None
assert popup.list.item(0).text() == 'Wear'
popup.choose()
assert popup.chosen.id == 'generator' and popup.resource == 'wear-id'
popup.close()
# Dispatch a real context-menu event: no intermediary management menu.
view = panel.view()
before_nodes = len(host.nodes)
errors = []
def choose_direct():
    dialog = application.activePopupWidget()
    try:
        assert isinstance(dialog, Browser)
        dialog.query.setText('fill layer')
        row = dialog.list.item(0)
        QtTest.QTest.mouseClick(dialog.list.viewport(), QtCore.Qt.MouseButton.LeftButton,
                               pos=dialog.list.visualItemRect(row).center())
    except Exception as exc:
        errors.append(str(exc))
        if dialog:
            dialog.reject()
QtCore.QTimer.singleShot(0, choose_direct)
local = QtCore.QPoint(25,25)
context_event = QtGui.QContextMenuEvent(QtGui.QContextMenuEvent.Reason.Mouse, local,
                                      view.viewport().mapToGlobal(local))
view.contextMenuEvent(context_event)
assert not errors, errors
assert len(host.nodes) == before_nodes + 1
created = host.selected[0]
host.delete(created)
panel.refresh()
assert not hasattr(panel, 'inspector') and not hasattr(panel, 'breadcrumb')
assert not panel.findChildren(QtWidgets.QSplitter)
assert QtWidgets.QWidget.layout(panel).contentsMargins().left() == 0
assert panel.tabs.width() >= panel.width() - 2
view = panel.view()
view.resetTransform()
view.centerOn(view.cards[a])
def point(uid, local):
    return view.mapFromScene(view.cards[uid].mapToScene(QtCore.QPointF(*local)))
def click(uid, local):
    QtTest.QTest.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point(uid, local))
    QtTest.QTest.qWait(20)
card = view.cards[a]
before = card.pos()
assert card.region(QtCore.QPointF(220, 50)) == 'mask'
assert card.region(QtCore.QPointF(19, 18)) == 'eye'
assert card.region(QtCore.QPointF(18, 85)) == 'arrow'
QtTest.QTest.mouseMove(view.viewport(), point(a, (90,40)))
QtTest.QTest.qWait(10)
assert card.hover_region == 'body'
assert card.body_color().lightness() > card.brush().color().lightness()
QtTest.QTest.mouseMove(view.viewport(), QtCore.QPoint(5,5))
QtTest.QTest.qWait(10)
assert not card.hover_region
assert card.body_color() == card.brush().color()
QtTest.QTest.mouseMove(view.viewport(), point(a, (220,50)))
QtTest.QTest.qWait(10)
assert card.hover_region == 'mask'
click(a, (19,18))
assert not host.nodes[int(a)].visible
assert not view.cards[a].enabled
assert view.cards[a].pen().color().name() == '#444b53'
assert view.cards[a].brush().color().name() == '#20252b'
assert view.cards[a].pos() == before
assert panel.tabs.count() == 1
click(a, (90,40))
assert host.selected == [host.nodes[int(a)]] and host.selection_type == 'content'
assert panel.tabs.count() == 1
click(a, (220,50))
assert host.selection_type == 'mask' and view.cards[a].isSelected()
assert panel.tabs.count() == 1
click(a, (19,18))
assert host.nodes[int(a)].visible
assert view.cards[a].pen().color().name() == '#2faae8'
click(a, (18,85))
assert a in panel.layout.expanded and fx in view.cards
assert view.cards[fx].y() > view.cards[a].y()
assert view.cards[fx].x() == view.cards[a].x() + 370
scope = (a, 'mask')
frame = view.branch_frames[scope]
assert view.backgroundBrush().color().name() == '#333333'
assert frame.rect().left() == view.cards[a].x()
content_frame = view.branch_frames[(a, 'content')]
assert content_frame.rect().top() == view.cards[a].y() + 100
assert content_frame.rect().left() == frame.rect().left()
assert content_frame.rect().width() == frame.rect().width()
assert content_frame.rect().bottom() == frame.rect().top()
assert view.cards[content_fx].x() == view.cards[fx].x()
assert view.cards[content_frame.members[0]].y() == view.cards[content_fx].y()
input_uid, output_uid = '@input:mask:'+a, '@output:mask:'+a
assert frame.members == [input_uid, fx, output_uid]
assert set(view.cards[input_uid].ports) == {'output'}
assert set(view.cards[output_uid].ports) == {'input'}
assert (input_uid, fx, 'mask') in view.links
assert (fx, output_uid, 'mask') in view.links
assert (fx, a, 'mask') not in view.links
assert frame.rect().contains(view.cards[fx].sceneBoundingRect())
assert view.begin_connection(fx, 'input', point(fx, (0,77)))
assert not view.drop_reason((input_uid, 'output'))
assert view.drop_reason(('@input', 'output'))
view.cancel_connection()
old_frame = QtCore.QRectF(frame.rect())
old_child = view.cards[fx].pos()
view.cards[a].moveBy(10,20)
assert view.cards[fx].pos() == old_child + QtCore.QPointF(10,20)
assert frame.rect() == old_frame.translated(10,20)
view.cards[fx].moveBy(0,40)
assert frame.rect().contains(view.cards[fx].sceneBoundingRect())
assert panel.tabs.count() == 1
click(a, (18,85))
assert a not in panel.layout.expanded and fx not in view.cards
assert scope not in view.branch_frames and input_uid not in view.cards
QtTest.QTest.mouseDClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point(a, (220,50)))
QtTest.QTest.qWait(20)
assert panel.view().scope == (a, 'mask')
panel.open_scope(ROOT)
view = panel.view()
view.centerOn(view.cards[a])
QtTest.QTest.mouseDClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point(a, (90,40)))
QtTest.QTest.qWait(20)
assert panel.view().scope == (a, 'content')
panel.open_scope(ROOT)
view = panel.view()
view.scene().clearSelection()
panel.toggle(group)
panel.toggle(child)
outer = view.branch_frames[(group, 'layers')]
inner = view.branch_frames[(child, 'mask')]
assert panel.layout.expanded == {group, child}
assert outer.rect().contains(inner.rect())
assert inner.rect().contains(view.cards[nested_fx].sceneBoundingRect())
panel.toggle(empty_group)
assert panel.layout.expanded == {group, empty_group}
assert (child, 'mask') not in view.branch_frames
assert nested_fx not in view.cards
outer = view.branch_frames[(group, 'layers')]
empty_frame = view.branch_frames[(empty_group, 'layers')]
assert len(empty_frame.members) == 2
assert (empty_frame.members[0], empty_frame.members[1], 'layers') in view.links
assert outer.rect().contains(empty_frame.rect())
positions = {uid: QtCore.QPointF(card.pos()) for uid, card in view.cards.items()}
view.cards[group].moveBy(15,25)
for uid in [child, empty_group, *empty_frame.members]:
    assert view.cards[uid].pos() == positions[uid] + QtCore.QPointF(15,25)
assert outer.rect().contains(empty_frame.rect())
panel.toggle(a)
assert panel.layout.expanded == {a}
assert child not in view.cards and (group, 'layers') not in view.branch_frames
panel.toggle(group)
assert panel.layout.expanded == {group}
panel.toggle(group)
assert child not in view.cards and nested_fx not in view.cards
assert (child, 'mask') not in view.branch_frames
panel.toggle(group)
view.cards[group].setSelected(True)
view.cards[child].setSelected(True)
confirmations = []
def confirm():
    dialog = application.activeModalWidget()
    assert isinstance(dialog, QtWidgets.QMessageBox)
    confirmations.append(dialog.text())
    dialog.done(QtWidgets.QMessageBox.StandardButton.Yes)
QtCore.QTimer.singleShot(0, confirm)
QtTest.QTest.keyClick(view, QtCore.Qt.Key.Key_Delete)
assert len(confirmations) == 1
assert int(group) not in host.nodes and int(child) not in host.nodes
assert int(a) in host.nodes
def apply_blending():
    dialog = application.activeModalWidget()
    assert isinstance(dialog, QtWidgets.QDialog)
    dialog.findChild(QtWidgets.QDoubleSpinBox).setValue(42)
    dialog.accept()
QtCore.QTimer.singleShot(0, apply_blending)
panel.channel_popup(a)
assert host.nodes[int(a)].opacity == .42
view = panel.view()
frame = panel.layout.frame(ROOT, [a], 'Keep content')
view.rebuild()
view.toggle_frame(frame.id)
view.scene().clearSelection()
view.cards['@frame:'+frame.id].setSelected(True)
QtTest.QTest.keyClick(view, QtCore.Qt.Key.Key_Delete)
assert not panel.layout.frames and int(a) in host.nodes
view.scene().clearSelection()
view.cards['@output'].setSelected(True)
QtTest.QTest.keyClick(view, QtCore.Qt.Key.Key_Delete)
assert int(a) in host.nodes
assert panel.grab().width() > 0
panel.dispose()
assert not listeners
panel.close()
print('Direct node controls passed')
'''
    result = subprocess.run([sys.executable, "-B", "-c", script,
                             str(root / "painter_python" / "plugins"), str(root / "tests")],
                            capture_output=True, text=True, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr