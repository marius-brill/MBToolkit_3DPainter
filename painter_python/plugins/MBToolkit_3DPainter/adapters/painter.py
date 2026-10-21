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
