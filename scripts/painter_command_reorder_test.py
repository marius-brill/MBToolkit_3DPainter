"""Explicit phased live experiment. Mutates only a named disposable project.

Use runpy.run_path(path, init_globals={"phase": phase_name})["report"].
Results are retained in the temporary directory; no production feature is enabled.
"""
import json
from pathlib import Path
import shutil
import tempfile

import substance_painter as sp
from PySide6 import QtGui, QtWidgets

TEST = Path(tempfile.gettempdir()) / "MBToolkit_Reorder_Command_Test.spp"
RESULTS = TEST.with_suffix(".json")
FIXTURE = Path("C:/Program Files/Adobe/Adobe Substance 3D Painter/resources/python/modules/automated_tests/resources/layerstack-cube.spp")


def action(label):
    panels = [w for w in sp.ui.get_main_window().findChildren(QtWidgets.QWidget)
              if w.metaObject().className() == "Alg::LayersStackView"]
    matches = [a for w in panels for a in QtWidgets.QWidget.actions(w) if a.text() == label]
    if len(matches) != 1 or not matches[0].isEnabled():
        raise ValueError("Missing, ambiguous or disabled action: " + label)
    return matches[0]


def roots():
    return [(str(n.uid()), n.get_name()) for n in sp.layerstack.get_root_layer_nodes(sp.textureset.get_active_stack())]


def history(name):
    matches = [a for a in sp.ui.get_main_window().findChildren(QtGui.QAction) if a.objectName() == name]
    assert len(matches) == 1 and matches[0].isEnabled()
    matches[0].trigger()


def run(phase):
    if phase == "setup":
        assert sp.project.is_open() and Path(sp.project.file_path()) == FIXTURE
        assert not sp.project.needs_saving()
        assert not TEST.exists(), "Refusing to overwrite existing disposable project"
        shutil.copyfile(FIXTURE, TEST)
        sp.project.close()
        sp.project.open(str(TEST))
        return {"test_project": str(TEST)}
    assert Path(sp.project.file_path()) == TEST, "Disposable project required"
    assert not sp.project.is_busy()
    data = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    if phase == "cut":
        data["before"] = roots()
        source = sp.layerstack.get_node_by_uid(int(data["before"][0][0]))
        sp.layerstack.set_selected_nodes([source])
        sp.layerstack.set_selection_type(source, sp.layerstack.SelectionType.Content)
        action("Cut layer(s)").trigger()
        data["after_cut"] = roots()
    elif phase == "paste":
        target = sp.layerstack.get_node_by_uid(int(data["before"][2][0]))
        sp.layerstack.set_selected_nodes([target])
        sp.layerstack.set_selection_type(target, sp.layerstack.SelectionType.Content)
        action("Paste layer(s)").trigger()
        data["after_paste"] = roots()
        data["uids_preserved"] = sorted(x[0] for x in data["before"]) == sorted(x[0] for x in data["after_paste"])
    elif phase == "undo":
        history("UNDO")
        data["undo"] = roots()
    elif phase == "redo":
        history("REDO")
        data["redo"] = roots()
    elif phase == "effect_setup":
        owner = sp.layerstack.get_root_layer_nodes(sp.textureset.get_active_stack())[0]
        position = sp.layerstack.InsertPosition.inside_node(owner, sp.layerstack.NodeStack.Content)
        effects = [sp.layerstack.insert_levels_effect(position) for _ in range(3)]
        data["effect_owner"] = str(owner.uid())
        data["effect_before"] = [str(n.uid()) for n in owner.content_effects()]
        sp.layerstack.set_selected_nodes([effects[0]])
    elif phase in ("effect_move", "effect_undo", "effect_redo"):
        if phase == "effect_move":
            action("Move effect(s) to top").trigger()
        else:
            history("UNDO" if phase == "effect_undo" else "REDO")
        owner = sp.layerstack.get_node_by_uid(int(data["effect_owner"]))
        data[phase] = [str(n.uid()) for n in owner.content_effects()]
    elif phase == "prototype":
        import os
        from MBToolkit_3DPainter.features.layer_graph.adapter import Adapter
        from MBToolkit_3DPainter.features.layer_graph import native_effect_order
        from MBToolkit_3DPainter.features.layer_graph.ordering import MoveIntent, plan_move

        previous = os.environ.get("MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER")
        os.environ["MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER"] = "1"
        try:
            adapter = Adapter(sp)
            scope = (data["effect_owner"], "content")
            before = adapter.scan()
            uid = before.chains[scope][-1]
            plan = plan_move(before, MoveIntent(before.context, (uid,), scope, "end"))
            native_effect_order.move(adapter, plan)
            data["prototype_expected"] = list(plan.destination_after)
            data["prototype_after"] = adapter.scan().chains[scope]
            assert data["prototype_after"] == data["prototype_expected"]
        finally:
            if previous is None:
                os.environ.pop("MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER", None)
            else:
                os.environ["MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER"] = previous
    elif phase == "prototype_matrix":
        import os
        from MBToolkit_3DPainter.features.layer_graph.adapter import Adapter
        from MBToolkit_3DPainter.features.layer_graph import native_effect_order
        from MBToolkit_3DPainter.features.layer_graph.ordering import MoveIntent, plan_move

        previous = os.environ.get("MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER")
        os.environ["MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER"] = "1"
        try:
            adapter = Adapter(sp)
            group = sp.layerstack.get_root_layer_nodes(sp.textureset.get_active_stack())[-1]
            owner = group.sub_layers()[-1].sub_layers()[0]
            if not owner.has_mask():
                owner.add_mask(sp.layerstack.MaskBackground.Black)
            position = sp.layerstack.InsertPosition.inside_node(owner, sp.layerstack.NodeStack.Mask)
            effects = [sp.layerstack.insert_levels_effect(position) for _ in range(5)]
            effects[0].set_visible(False)
            scope = (str(owner.uid()), "mask")
            matrix = []
            for source, placement, target in [(4, "end", None), (2, "after", 1),
                                                (2, "before", 3), (0, "start", None)]:
                before = adapter.scan()
                chain = before.chains[scope]
                plan = plan_move(before, MoveIntent(before.context, (chain[source],), scope,
                                                    placement, chain[target] if target is not None else None))
                native_effect_order.move(adapter, plan)
                moved = adapter.scan()
                assert tuple(moved.chains[scope]) == plan.destination_after
                history("UNDO")
                assert adapter.scan().chains == before.chains
                history("REDO")
                assert adapter.scan().chains == moved.chains
                matrix.append({"command": native_effect_order.command(before, plan),
                               "before": chain, "after": list(plan.destination_after), "undo_redo": True})
            data["prototype_mask_matrix"] = matrix
        finally:
            if previous is None:
                os.environ.pop("MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER", None)
            else:
                os.environ["MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER"] = previous
    else:
        raise ValueError("Unknown phase: " + phase)
    RESULTS.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


if "phase" in globals():
    report = run(globals()["phase"])