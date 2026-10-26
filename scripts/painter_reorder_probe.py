"""Read-only native reorder investigation; run inside Painter, not normal Python.

Does not call moveRows, mimeData, dropMimeData, action.trigger, selection setters,
or private slots. Import with runpy.run_path(path)["report"] for remote JSON output.
"""


def _attempt(callback):
    try:
        return callback()
    except Exception as exc:
        return {"error": type(exc).__name__ + ": " + str(exc)}


def _hierarchy(sp):
    if not sp.project.is_open():
        return None
    pending = [("", "layers", sp.layerstack.get_root_layer_nodes(sp.textureset.get_active_stack()))]
    result = []
    seen = set()
    while pending:
        owner, domain, nodes = pending.pop()
        for order, node in enumerate(nodes):
            uid = str(node.uid())
            if uid in seen:
                raise ValueError("Duplicate native node in hierarchy")
            seen.add(uid)
            kind = node.get_type().name
            result.append((uid, owner, domain, order, kind, node.get_name(), node.is_visible()))
            if isinstance(node, sp.layerstack.LayerNode):
                pending.append((uid, "content", node.content_effects()))
                if node.has_mask():
                    pending.append((uid, "mask", node.mask_effects()))
            if kind == "GroupLayer":
                pending.append((uid, "layers", node.sub_layers()))
    return result


def collect():
    import substance_painter as sp
    from PySide6 import QtCore, QtGui, QtWidgets

    window = sp.ui.get_main_window()
    before = _hierarchy(sp)
    dirty_before = sp.project.needs_saving() if before is not None else None
    stack = sp.textureset.get_active_stack() if before is not None else None
    selected_before = tuple(str(node.uid()) for node in sp.layerstack.get_selected_nodes(stack)) if stack else ()
    result = {"version": tuple(sp.application.version_info()), "hierarchy": before,
              "models": [], "objects": [], "actions": [], "attached_actions": []}
    for obj in window.findChildren(QtCore.QObject):
        meta = obj.metaObject()
        name = meta.className()
        if any(word in name for word in ("LayersStack", "ActionsStack", "LayerListModel", "DragAndDrop")):
            result["objects"].append({
                "class": name, "name": obj.objectName(),
                "methods": [bytes(meta.method(i).methodSignature()).decode()
                            for i in range(meta.methodOffset(), meta.methodCount())],
                # Unknown QVariant values may have no Python converter. Names only.
                "dynamic_properties": [bytes(key).decode() for key in obj.dynamicPropertyNames()],
            })
        if isinstance(obj, QtCore.QAbstractItemModel) and any(word in name for word in ("Layer", "Action")):
            rows = []
            for row in range(min(obj.rowCount(), 100)):
                index = obj.index(row, 0)
                rows.append({"row": row, "internal_id": index.internalId(),
                             "flags": str(obj.flags(index)),
                             "display": _attempt(lambda: str(obj.data(index, QtCore.Qt.ItemDataRole.DisplayRole)))})
            result["models"].append({
                "class": name, "row_count": obj.rowCount(), "rows": rows,
                "roles": {int(key): bytes(value).decode() for key, value in obj.roleNames().items()},
                "mime_types": obj.mimeTypes(), "drag_actions": str(obj.supportedDragActions()),
                "drop_actions": str(obj.supportedDropActions()),
            })
        if isinstance(obj, QtGui.QAction):
            text = obj.text()
            if any(word in (text + " " + obj.objectName()).casefold()
                   for word in ("move", "paste", "cut", "order")):
                result["actions"].append({"name": obj.objectName(), "text": text,
                                          "enabled": obj.isEnabled()})
    # QWidget.actions() includes actions not parented to the widget tree. Call the
    # base method explicitly: plugin widgets may use `actions` as a data attribute.
    for widget in window.findChildren(QtWidgets.QWidget):
        if widget.metaObject().className() != "Alg::LayersStackView":
            continue
        for action in QtWidgets.QWidget.actions(widget):
            if any(word in (action.text() + " " + action.objectName()).casefold()
                   for word in ("move", "paste", "cut")):
                result["attached_actions"].append({"name": action.objectName(), "text": action.text(),
                                                   "enabled": action.isEnabled()})
    after = _hierarchy(sp)
    dirty_after = sp.project.needs_saving() if after is not None else None
    selected_after = tuple(str(node.uid()) for node in sp.layerstack.get_selected_nodes(stack)) if stack else ()
    result["unchanged"] = {"hierarchy": before == after, "dirty_state": dirty_before == dirty_after,
                           "selection": selected_before == selected_after}
    result["dirty_before"] = dirty_before
    result["dirty_after"] = dirty_after
    return result


if __name__ in ("__main__", "<run_path>"):
    report = collect()