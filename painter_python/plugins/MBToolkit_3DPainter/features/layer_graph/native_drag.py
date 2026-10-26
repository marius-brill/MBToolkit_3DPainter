"""Experimental Windows native UI bridge, NOT a public Painter move API.

Only the exact host version and simple root-layer scope tested live are enabled.
No fabricated MIME drops, private methods, layer reconstruction or cached widgets.
"""
import os
import sys
from .ordering import revalidate_move, ui_move_reason


def available(sp):
    return (os.environ.get("MBTOOLKIT_EXPERIMENTAL_REORDER") == "1" and sys.platform == "win32"
            and tuple(sp.application.version_info()) == (11, 0, 3))


def start(adapter, plan, parent, done):
    import ctypes
    from PySide6 import QtCore, QtGui, QtWidgets

    if not available(adapter.sp):
        raise ValueError("Native drag prototype is opt-in only: MBTOOLKIT_EXPERIMENTAL_REORDER=1 on Windows Painter 11.0.3")
    snapshot = adapter.scan()
    revalidate_move(snapshot, plan)
    if len(plan.moved) != 1:
        raise ValueError("Experimental native dragging supports one layer at a time")
    reason = ui_move_reason(snapshot, plan)
    if reason:
        raise ValueError(reason)
    if plan.noop:
        done("")
        return None
    adapter._ready(plan.intent.context)
    if QtWidgets.QApplication.activeModalWidget() or QtWidgets.QApplication.activePopupWidget():
        raise ValueError("Close native dialogs and popups before reordering")
    window = adapter.sp.ui.get_main_window()
    panels = [w for w in window.findChildren(QtWidgets.QWidget)
              if w.metaObject().className() == "Alg::LayersStackView" and w.isVisible()]
    if len(panels) != 1:
        raise ValueError("Show Painter's native Layers panel before reordering")
    labels = {}
    for uid in plan.source_before:
        name = snapshot.nodes[uid].name
        matches = [w for w in panels[0].findChildren(QtWidgets.QLabel) if w.text() == name and w.isVisible()]
        if len(matches) != 1:
            raise ValueError("All root layer rows must be visible and uniquely identifiable in Painter's Layers panel")
        row = matches[0]
        while row is not None and row.metaObject().className() != "Alg::LayerView":
            row = row.parentWidget()
        if row is None:
            raise ValueError("Painter's layer row structure differs from the verified version")
        labels[uid] = (matches[0], row)
    # Reorder only when the displayed rows independently agree with SDK order.
    if tuple(sorted(labels, key=lambda uid: labels[uid][1].mapToGlobal(QtCore.QPoint()).y())) != plan.source_before:
        raise ValueError("Native row order does not match the active stack; refresh")
    uid = plan.moved[0]
    remaining = [key for key in plan.destination_after if key != uid]
    index = plan.destination_after.index(uid)
    below = index < len(remaining)
    target = remaining[index] if below else remaining[-1]
    label, row = labels[target]
    source_label = labels[uid][0]
    source = source_label.mapToGlobal(source_label.rect().center())
    destination = row.mapToGlobal(QtCore.QPoint(100, 1 if below else row.height() - 1))
    # Clipped rows are not safe targets; do not scroll or expand native hierarchy implicitly.
    for point in (source, destination):
        if not panels[0].rect().contains(panels[0].mapFromGlobal(point)):
            raise ValueError("Native source/target rows are clipped or covered; make both visible")
    adapter.sp.layerstack.set_selected_nodes([adapter.resolve(uid, plan.intent.context)])
    user = ctypes.windll.user32
    user.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user.GetForegroundWindow.restype = ctypes.c_void_p
    if not user.SetForegroundWindow(int(window.winId())):
        raise ValueError("Painter must be the foreground application to reorder")
    original_cursor = QtGui.QCursor.pos()
    timer = QtCore.QTimer(parent)
    timer.setSingleShot(True)
    state = {"pressed": False, "finished": False}

    def finish(error=""):
        if state["finished"]:
            return
        state["finished"] = True
        timer.stop()
        if state["pressed"]:
            # Cancel the native QDrag before releasing on an error/disposal.
            if error:
                user.keybd_event(27, 0, 0, 0)
                user.keybd_event(27, 0, 2, 0)
            user.mouse_event(4, 0, 0, 0, 0)
            state["pressed"] = False
        QtGui.QCursor.setPos(original_cursor)
        QtWidgets.QApplication.instance().removeEventFilter(cancel)
        cancel.deleteLater()
        timer.deleteLater()
        done(error)

    class Cancel(QtCore.QObject):
        def eventFilter(self, obj, event):
            if event.type() == QtCore.QEvent.Type.KeyPress and event.key() == QtCore.Qt.Key.Key_Escape:
                # The original Escape already cancels QDrag; avoid injecting it recursively.
                state["pressed"] = False
                user.mouse_event(4, 0, 0, 0, 0)
                finish("Native reorder cancelled; refresh to inspect Painter's order")
            return False

    cancel = Cancel(parent)
    QtWidgets.QApplication.instance().installEventFilter(cancel)

    def verify():
        if state["finished"]:
            return
        try:
            fresh = adapter.scan()
            if (fresh.context != plan.intent.context or set(fresh.nodes) != set(snapshot.nodes)
                    or tuple(fresh.chains.get(plan.source, ())) != plan.destination_after
                    or any((fresh.nodes[key].scope, fresh.nodes[key].kind, fresh.nodes[key].name,
                            fresh.nodes[key].visible, fresh.nodes[key].mask) !=
                           (node.scope, node.kind, node.name, node.visible, node.mask)
                           for key, node in snapshot.nodes.items())):
                raise ValueError("Native drag did not produce the expected identity-preserving order. Inspect Layers; use Undo if needed")
            finish()
        except Exception as exc:
            finish(str(exc))

    def release():
        if state["finished"]:
            return
        try:
            adapter._ready(plan.intent.context)
            revalidate_move(adapter.scan(), plan)
            if user.GetForegroundWindow() != int(window.winId()):
                raise ValueError("Painter lost foreground focus; native reorder cancelled")
        except Exception as exc:
            # Escape before releasing avoids committing a now-stale native drop.
            user.keybd_event(27, 0, 0, 0)
            user.keybd_event(27, 0, 2, 0)
            finish(str(exc))
            return
        user.mouse_event(4, 0, 0, 0, 0)
        state["pressed"] = False
        QtCore.QTimer.singleShot(300, verify)

    def move():
        try:
            adapter._ready(plan.intent.context)
            revalidate_move(adapter.scan(), plan)
            if state["finished"]:
                return
            if user.GetForegroundWindow() != int(window.winId()):
                raise ValueError("Painter lost foreground focus; native reorder cancelled")
            if QtWidgets.QApplication.activeModalWidget() or QtWidgets.QApplication.activePopupWidget():
                raise ValueError("A native dialog interrupted the reorder")
            for point in (source, destination):
                hit = QtWidgets.QApplication.widgetAt(point)
                if hit is None or not panels[0].isAncestorOf(hit):
                    raise ValueError("Native source or destination became covered; reorder cancelled")
            QtCore.QTimer.singleShot(400, release)
            QtGui.QCursor.setPos(destination)
        except Exception as exc:
            finish(str(exc))

    QtGui.QCursor.setPos(source)
    user.mouse_event(2, 0, 0, 0, 0)
    state["pressed"] = True
    timer.timeout.connect(move)
    timer.start(200)
    # Expose cancellation to the panel's disposal path; callbacks retain the bridge.
    return finish