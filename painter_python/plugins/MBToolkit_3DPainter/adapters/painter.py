"""Version-aware public Painter operations. Never call undocumented UI internals."""
import substance_painter as sp
from ..metadata import MIN_PAINTER


def compatible():
    return tuple(sp.application.version_info()) >= MIN_PAINTER


def active_stack():
    if not sp.project.is_open():
        return None
    return sp.textureset.get_active_stack()


def selected_single_layer():
    stack = active_stack()
    if stack is None:
        return stack, None
    selected = sp.layerstack.get_selected_nodes(stack)
    if len(selected) != 1:
        return stack, None
    return stack, selected[0]


def available_font_resources():
    return sorted(sp.resource.search("u:font"), key=lambda r: r.gui_name().casefold())


def owning_layer(node):
    """Resolve effects to their owning layer without climbing out of folders."""
    while node is not None and not isinstance(node, sp.layerstack.LayerNode):
        node = node.get_parent()
    return node


def insertion_above_selection(stack):
    selected = sp.layerstack.get_selected_nodes(stack)
    if len(selected) > 1:
        raise ValueError("Select one layer, or clear the selection before creating a layer")
    if selected:
        layer = owning_layer(selected[0])
        if layer is None:
            raise ValueError("Cannot resolve the selected node to a layer")
        return sp.layerstack.InsertPosition.above_node(layer)
    return sp.layerstack.InsertPosition.from_textureset_stack(stack)


def create_layer(kind, *, select=True, above=None):
    stack = active_stack()
    if stack is None:
        raise RuntimeError("Open a Painter project first")
    insert = {"fill": sp.layerstack.insert_fill, "paint": sp.layerstack.insert_paint,
              "group": sp.layerstack.insert_group}[kind]
    position = sp.layerstack.InsertPosition.above_node(above) if above is not None else insertion_above_selection(stack)
    node = insert(position)
    if select:
        sp.layerstack.set_selected_nodes([node])
    return node


def selected_owning_layer():
    _stack, node = selected_single_layer()
    if node is None:
        raise ValueError("Select one layer first")
    layer = owning_layer(node)
    if layer is None:
        raise ValueError("Select a layer or one of its effects")
    return layer


def add_mask(layer, white=False):
    if layer.has_mask():
        raise ValueError("The target already has a mask; it will not be replaced")
    layer.add_mask(sp.layerstack.MaskBackground.White if white else sp.layerstack.MaskBackground.Black)
    return layer


def add_mask_fill(layer):
    if not layer.has_mask():
        raise ValueError("The target needs a mask before adding a mask Fill effect")
    return sp.layerstack.insert_fill(sp.layerstack.InsertPosition.inside_node(layer, sp.layerstack.NodeStack.Mask))


def add_fill_layer():
    stack = active_stack()
    if stack is None:
        raise RuntimeError("Open a Painter project first")
    return sp.layerstack.insert_fill(sp.layerstack.InsertPosition.from_textureset_stack(stack))


def add_text_paint_layer(resource_id):
    """Create paint content with a separate procedural text mask, never rasterized text."""
    stack = active_stack()
    if stack is None:
        raise RuntimeError("Open a Painter project first")
    node = sp.layerstack.insert_paint(sp.layerstack.InsertPosition.from_textureset_stack(stack))
    try:
        node.add_mask(sp.layerstack.MaskBackground.Black)
        position = sp.layerstack.InsertPosition.inside_node(node, sp.layerstack.NodeStack.Mask)
        effect = sp.layerstack.insert_fill(position)
        effect.set_name("MB Text Mask")
        source = effect.set_source(None, resource_id)
        return node, effect, source
    except Exception:
        sp.layerstack.delete_node(node)
        raise
