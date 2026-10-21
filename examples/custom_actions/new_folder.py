"""Example trusted Python action; copy into MBToolkit Preferences → Python Actions."""
import substance_painter as sp

stack = sp.textureset.get_active_stack()
if stack is None:
    raise RuntimeError("Open a project")
position = sp.layerstack.InsertPosition.from_textureset_stack(stack)
folder = sp.layerstack.insert_group(position)
folder.set_name("New Folder from MBToolkit")
