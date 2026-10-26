"""Opt-in native effect QAction prototype, not a public Painter move API.

One command per operation: no clipboard, cursor simulation or chained undo steps.
Only English action labels on the host version tested live are recognized.
"""
import os

from .ordering import revalidate_move


def available(sp):
    return (os.environ.get("MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER") == "1"
            and tuple(sp.application.version_info()) == (11, 0, 3))


def command(snapshot, plan):
    revalidate_move(snapshot, plan)
    if plan.noop:
        return None
    if plan.source != plan.intent.destination or plan.source[1] not in ("content", "mask"):
        raise ValueError("Native effect-order prototype only moves effects within their existing stack")
    if len(plan.moved) != 1:
        raise ValueError("Native effect-order prototype supports one effect at a time")
    if any(node.kind == "AnchorPointEffect" for node in snapshot.nodes.values()):
        raise ValueError("Anchor dependencies are not verified for the effect-order prototype")
    uid = plan.moved[0]
    old = plan.source_before.index(uid)
    new = plan.destination_after.index(uid)
    if new == 0:
        return "Move effect(s) to top"
    if new == len(plan.destination_after) - 1:
        return "Move effect(s) to bottom"
    if abs(new - old) == 1:
        return "Move effect(s) " + ("up" if new < old else "down")
    raise ValueError("Prototype supports adjacent moves or either stack boundary; move in single steps")


def _action(sp, label):
    from PySide6 import QtWidgets

    if QtWidgets.QApplication.activeModalWidget() or QtWidgets.QApplication.activePopupWidget():
        raise ValueError("Close dialogs and popups before reordering effects")
    panels = [w for w in sp.ui.get_main_window().findChildren(QtWidgets.QWidget)
              if w.metaObject().className() == "Alg::LayersStackView"]
    matches = [a for panel in panels for a in QtWidgets.QWidget.actions(panel) if a.text() == label]
    if len(matches) != 1 or not matches[0].isEnabled():
        raise ValueError("No unique enabled English native effect-order action: " + label)
    return matches[0]


def move(adapter, plan):
    if not available(adapter.sp):
        raise ValueError("Effect-order prototype requires MBTOOLKIT_EXPERIMENTAL_EFFECT_ORDER=1 on Painter 11.0.3")
    adapter._ready(plan.intent.context)
    before = adapter.scan()
    label = command(before, plan)
    if label is None:
        return False
    # Selection changes must remain outside ScopedModification.
    adapter.navigate_many(plan.moved, plan.intent.context)
    action = _action(adapter.sp, label)
    adapter._ready(plan.intent.context)
    revalidate_move(adapter.scan(), plan)
    action.trigger()
    after = adapter.scan()
    expected_chains = {scope: tuple(chain) for scope, chain in before.chains.items()}
    expected_chains[plan.source] = plan.destination_after
    if (after.context != before.context or after.nodes != before.nodes
            or {scope: tuple(chain) for scope, chain in after.chains.items()} != expected_chains):
        # Never blindly Undo: another native operation could own the latest step.
        raise ValueError("Native effect order did not match the plan. Inspect Painter and use Undo if needed")
    return True