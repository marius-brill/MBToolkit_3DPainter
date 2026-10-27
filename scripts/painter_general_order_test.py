"""Explicit disposable-session investigation of native layer ordering.

Invoke with runpy.run_path(path, init_globals={"phase": "setup"})["report"].
Never opens over a user project. Does not save the test project.
"""
from pathlib import Path
import json
import shutil
import tempfile

import substance_painter as sp
from PySide6 import QtCore, QtGui, QtWidgets

STATE = Path(tempfile.gettempdir()) / "MBToolkit_General_Order_State.json"


def panel():
    matches = [w for w in sp.ui.get_main_window().findChildren(QtWidgets.QWidget)
               if w.metaObject().className() == "Alg::LayersStackView"]
    assert len(matches) == 1
    return matches[0]


def actions():
    return [{"text": a.text(), "name": a.objectName(), "enabled": a.isEnabled(),
             "shortcuts": [s.toString() for s in a.shortcuts()]}
            for a in QtWidgets.QWidget.actions(panel())]


def run(phase):
    if phase == "setup":
        assert not sp.project.is_open(), "Close the user project first"
        folder = Path(tempfile.mkdtemp(prefix="MBToolkit_General_Order_"))
        destination = folder / "MBToolkit_General_Order_Test.spp"
        source = Path("C:/Program Files/Adobe/Adobe Substance 3D Painter/resources/python/modules/automated_tests/resources/layerstack-cube.spp")
        shutil.copyfile(source, destination)
        STATE.write_text(json.dumps({"project": str(destination)}), encoding="utf-8")
        sp.project.open(str(destination))
        return {"project": str(destination)}
    state = json.loads(STATE.read_text(encoding="utf-8"))
    assert Path(sp.project.file_path()) == Path(state["project"]), "Disposable project required"
    assert not sp.project.is_busy()
    stack = sp.textureset.get_active_stack()
    if phase == "inspect":
        return {"actions": actions(), "clipboard": QtWidgets.QApplication.clipboard().mimeData().formats(),
                "roots": [(n.uid(), n.get_name(), n.get_type().name) for n in sp.layerstack.get_root_layer_nodes(stack)],
                "models": [(o.metaObject().className(), o.rowCount())
                           for o in panel().findChildren(QtCore.QAbstractItemModel)]}
    if phase == "drag_metadata":
        result = []
        for obj in sp.ui.get_main_window().findChildren(QtCore.QObject):
            meta = obj.metaObject()
            name = meta.className()
            if not any(word in name for word in ("LayersStack", "LayerList", "DragAndDrop")):
                continue
            result.append({
                "class": name, "name": obj.objectName(),
                "methods": [bytes(meta.method(i).methodSignature()).decode()
                            for i in range(meta.methodOffset(), meta.methodCount())],
                "properties": [(meta.property(i).name(), meta.property(i).typeName())
                               for i in range(meta.propertyOffset(), meta.propertyCount())],
            })
        return result
    if phase in ("effect_prepare", "effect_move"):
        import os
        from MBToolkit_3DPainter.features.layer_graph.adapter import Adapter
        from MBToolkit_3DPainter.features.layer_graph import native_effect_order
        from MBToolkit_3DPainter.features.layer_graph.ordering import MoveIntent, plan_move

        previous = os.environ.get("MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER")
        os.environ["MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER"] = "1"
        results = []
        try:
            adapter = Adapter(sp)
            owner = sp.layerstack.get_root_layer_nodes(stack)[0]
            if not owner.has_mask():
                owner.add_mask(sp.layerstack.MaskBackground.Black)
            for domain in (globals().get("domain", "content"),):
                position = sp.layerstack.InsertPosition.inside_node(
                    owner, getattr(sp.layerstack.NodeStack, domain.capitalize()))
                # Ensure the first candidate really moves, rather than Undo
                # accidentally undoing fixture creation after a no-op plan.
                if phase == "effect_prepare":
                    for _ in range(3):
                        sp.layerstack.insert_levels_effect(position)
                names = [globals().get("factory", "insert_levels_effect")]
                for name in names:
                    if phase == "effect_prepare":
                        node = getattr(sp.layerstack, name)(position)
                        node.set_visible(False)
                        state.update({"effect": str(node.uid()), "factory": name, "domain": domain})
                        STATE.write_text(json.dumps(state), encoding="utf-8")
                        sp.layerstack.set_selected_nodes([node])
                        return state
                    assert state["domain"] == domain and state["factory"] == name
                    node = sp.layerstack.get_node_by_uid(int(state["effect"]))
                    scope = (str(owner.uid()), domain)
                    before = adapter.scan()
                    chain = before.chains[scope]
                    placement = "start" if chain[0] == str(node.uid()) else "end"
                    plan = plan_move(before, MoveIntent(before.context, (str(node.uid()),), scope, placement))
                    assert tuple(chain) != plan.destination_after, "Test requires a real move"
                    native_effect_order.move(adapter, plan)
                    moved = adapter.scan()
                    assert tuple(moved.chains[scope]) == plan.destination_after, (name, domain, "move")
                    for label, expected in (("UNDO", before), ("REDO", moved)):
                        matches = [a for a in sp.ui.get_main_window().findChildren(QtGui.QAction)
                                   if a.objectName() == label]
                        assert len(matches) == 1 and matches[0].isEnabled(), (name, domain, label, "action")
                        matches[0].trigger()
                        actual = adapter.scan()
                        assert actual.chains == expected.chains, (name, domain, label, "chains", actual.chains, expected.chains)
                        assert actual.nodes == expected.nodes, (name, domain, label, "records", actual.nodes, expected.nodes)
                    results.append({"domain": domain, "factory": name, "uid": str(node.uid()),
                                    "undo_redo": True, "records_preserved": True})
                    STATE.with_suffix(".results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
            return results
        finally:
            if previous is None:
                os.environ.pop("MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER", None)
            else:
                os.environ["MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER"] = previous
    if phase == "select_layer":
        node = sp.layerstack.get_root_layer_nodes(stack)[0]
        sp.layerstack.set_selected_nodes([node])
        sp.layerstack.set_selection_type(node, sp.layerstack.SelectionType.Content)
        return {"selected": node.uid(), "actions": actions()}
    raise ValueError("Unknown phase: " + phase)


if "phase" in globals():
    report = run(globals()["phase"])