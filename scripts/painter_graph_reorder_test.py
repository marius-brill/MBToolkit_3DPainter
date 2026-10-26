"""Exercise production graph port handlers in the running disposable Painter project."""
import importlib
import json
import os
from pathlib import Path
import substance_painter as sp
from PySide6 import QtCore, QtWidgets
from MBToolkit_3DPainter.features.layer_graph import canvas, panel, native_drag

assert "MBToolkit_Reorder_Test" in sp.project.file_path()
assert os.environ.get("MBTOOLKIT_EXPERIMENTAL_REORDER") == "1", "Explicit experimental native-drag opt-in required"
for module in (native_drag, canvas, panel):
    importlib.reload(module)
old = next(w for w in sp.ui.get_main_window().findChildren(QtWidgets.QWidget)
           if w.objectName() == "MBToolkit_layer_graph" and hasattr(w, "dispose"))
old.dispose()
old.native_reorder_busy = False
old.native_reorder = None
old.__class__ = panel.Panel
for i in range(old.tabs.count()):
    old.tabs.widget(i).__class__ = canvas.View
old.disposed = False
old.app.events.add(old.request_refresh)
old.poll.start()
old.refresh()
before = tuple(old.snapshot.chains[("", "layers")])
for key, color in zip(before, ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))):
    sp.layerstack.get_node_by_uid(int(key)).set_source(sp.textureset.ChannelType.BaseColor,
                                                    sp.colormanagement.Color(*color))
uid, target = before[0], before[-1]
view = old.view()


def point(key, side):
    port = view.cards[key].ports[side]
    return view.mapFromScene(port.mapToScene(port.rect().center()))


assert view.begin_connection(uid, "output", point(uid, "output"))
reason = view.drop_reason((target, "input"))
assert not reason, reason


def perform():
    sp.ui.get_main_window().grab().save(str(Path(__file__).with_suffix(".before.png")))
    view.finish_connection(point(target, "input"))


def report():
    after = tuple(str(n.uid()) for n in sp.layerstack.get_root_layer_nodes(sp.textureset.get_active_stack()))
    expected = (before[1], before[-1], before[0])
    Path(__file__).with_suffix(".json").write_text(json.dumps({"before": before, "after": after,
        "expected": expected, "passed": after == expected, "status": old.status.text()}, indent=2))
    sp.ui.get_main_window().grab().save(str(Path(__file__).with_suffix(".after.png")))


QtCore.QTimer.singleShot(900, perform)
QtCore.QTimer.singleShot(2800, report)