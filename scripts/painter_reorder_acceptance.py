"""Live acceptance of production native bridge; disposable test project required."""
import importlib
import json
import os
from pathlib import Path
import substance_painter as sp
from PySide6 import QtCore, QtGui
from MBToolkit_3DPainter.features.layer_graph.adapter import Adapter
from MBToolkit_3DPainter.features.layer_graph import ordering

assert "MBToolkit_Reorder_Test" in sp.project.file_path()
assert os.environ.get("MBTOOLKIT_EXPERIMENTAL_REORDER") == "1", "Explicit experimental native-drag opt-in required"
importlib.reload(ordering)
native_drag = importlib.import_module("MBToolkit_3DPainter.features.layer_graph.native_drag")
importlib.reload(native_drag)
adapter = Adapter(sp)
snapshot = adapter.scan()
chain = tuple(snapshot.chains[("", "layers")])
plan = ordering.connection_move(snapshot, chain[-1], "@output", "output", snapshot.context, ("", "layers"))
report = {"before": chain, "expected": plan.destination_after}


def roots():
    return tuple(str(n.uid()) for n in sp.layerstack.get_root_layer_nodes(sp.textureset.get_active_stack()))


def save():
    Path(__file__).with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def completed(error):
    report.update(error=error, after=roots(), identity_preserved=set(roots()) == set(chain))
    save()
    if error:
        return
    action = next(a for a in sp.ui.get_main_window().findChildren(QtGui.QAction) if a.objectName() == "UNDO")
    action.trigger()
    QtCore.QTimer.singleShot(400, undone)


def undone():
    report["undo"] = roots()
    action = next(a for a in sp.ui.get_main_window().findChildren(QtGui.QAction) if a.objectName() == "REDO")
    action.trigger()
    QtCore.QTimer.singleShot(400, redone)


def redone():
    report["redo"] = roots()
    report["passed"] = (not report["error"] and tuple(report["after"]) == plan.destination_after
                        and report["undo"] == chain and report["redo"] == plan.destination_after)
    save()


native_drag.start(adapter, plan, sp.ui.get_main_window(), completed)