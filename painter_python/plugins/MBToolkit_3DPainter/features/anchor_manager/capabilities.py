"""Explicit capability gates, rather than version-based promises."""
from dataclasses import dataclass
from enum import Enum


class Support(Enum):
    SUPPORTED = "SUPPORTED"
    READ_ONLY = "READ_ONLY"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Capability:
    state: Support
    reason: str


def probe(sp) -> dict[str, Capability]:
    ls = sp.layerstack
    result = {}
    for name, method in (("discovery", "get_root_layer_nodes"), ("navigate", "set_selected_nodes"),
                         ("create", "insert_anchor_point_effect"), ("delete", "delete_node"),
                         ("undo", "ScopedModification")):
        present = callable(getattr(ls, method, None))
        result[name] = Capability(Support.SUPPORTED if present else Support.UNSUPPORTED,
                                  f"Public layerstack.{method} {'available' if present else 'unavailable'}; runtime preflight required")
    result["rename"] = Capability(
        Support.SUPPORTED if callable(getattr(getattr(ls, "Node", None), "set_name", None)) else Support.UNSUPPORTED,
        "Requires Node.set_name and editable project")
    result["replace"] = Capability(Support.PARTIAL,
        "Fill sources only; preserve reference settings; candidates limited to proven equivalent anchor ordering")
    result["procedural"] = Capability(Support.PARTIAL,
        "Public image_inputs are scanned recursively; hidden/non-image parameter references are not guaranteed observable")
    result["disconnect"] = Capability(Support.UNSUPPORTED,
        "Reset/default semantics have not been validated; navigate to native properties instead")
    result["thumbnail"] = Capability(Support.UNSUPPORTED, "No verified arbitrary anchor output thumbnail API")
    return result