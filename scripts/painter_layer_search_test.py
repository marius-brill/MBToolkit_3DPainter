"""Non-destructive live check: filter native row widgets, then restore UI state."""
import substance_painter as sp
from time import perf_counter
import MBToolkit_3DPainter as plugin
from MBToolkit_3DPainter.features.layer_search.native import row_owner


def snapshot():
    def walk(nodes):
        result = []
        for node in nodes:
            result.append((node.uid(), node.get_name(), node.is_visible()))
            children = getattr(node, "sub_layers", None)
            if callable(children):
                result.extend(walk(children()))
        return result
    stack = sp.textureset.get_active_stack()
    return (walk(sp.layerstack.get_root_layer_nodes(stack)),
            [node.uid() for node in sp.layerstack.get_selected_nodes(stack)])


controller = plugin._app.features["layer_search"].controller
assert controller.field is not None and controller.field.isVisible(), controller.status
before = snapshot()
rows = controller.filter.rows()
state = [(row, row.isHidden(), controller.filter.expander(row),
          controller.filter.expander(row).isChecked() if controller.filter.expander(row) else None)
         for row in rows]
records = controller.filter.build_index()
searchable = {row for row, record in records.items() if record[3]}
target = next(row for row in rows if row in searchable and controller.filter.label(row) and row_owner(row) is not None)
query = controller.filter.label(target)
timings = []
try:
    # Independent oracle: own-name matches, their descendants, and ancestors.
    labels = {row: controller.filter.label(row) for row in rows}
    parents = {row: row_owner(row) for row in rows}
    effect_query = next((controller.filter.label(row) for row in rows
                         if row not in searchable and controller.filter.label(row)), "levels")
    for term in (query, effect_query, "master", "copper", "steel", "no-match-mbtoolkit-982734"):
        matches = {row for row in searchable if term in labels[row]}
        expected = set(matches)
        for row in rows:
            parent = parents[row]
            while parent in parents:
                if parent in matches:
                    expected.add(row)
                if row in matches:
                    expected.add(parent)
                parent = parents[parent]
        start = perf_counter()
        controller.field.setText(term.upper())
        timings.append(round((perf_counter() - start) * 1000, 2))
        assert {row for row in rows if not row.isHidden()} == expected, term
    controller.field.setText(query.upper())
    visible = [controller.filter.label(row) for row in controller.filter.rows() if not row.isHidden()]
    assert query in visible, visible
    assert not row_owner(target).isHidden()
    controller.field.setText("no-match-mbtoolkit-982734")
    assert all(row.isHidden() for row in controller.filter.rows())
finally:
    controller.field.clear()
assert snapshot() == before, "Project layer data or selection changed"
assert all(row.isHidden() == hidden and (button is None or button.isChecked() == checked)
           for row, hidden, button, checked in state), "UI state was not restored"
print("PASS: native bar visible, nested folder filtering, no matches, restored UI and unchanged layer data/selection")
print({"rows": len(rows), "filter_ms": timings})