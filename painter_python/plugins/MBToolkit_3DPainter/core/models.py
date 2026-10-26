"""Qt-free data models and validation for persistent settings."""
import copy
import re

FEATURES = {
    "pie_menus": True,
    "channel_blending": True,
    "font_tool": True,
    "anchor_manager": False,
    "layer_graph": False,
}
MAX_PIE_ACTIONS = 12
SAFE_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def default_settings():
    return {
        "schema_version": 2,
        "plugin_version_last_run": "0.1.0",
        "features": {name: {"enabled": on} for name, on in FEATURES.items()},
        "pie_menus": [{"id": "main", "name": "Main", "shortcut": "",
                       "actions": ["mb.blending", "mb.fonts", "mb.preferences"]}],
        "allow_custom_python": False,
        "macros": [],
        "anchor_manager": {"auto_refresh": True, "filter": "All", "sort": "Name",
                           "graph_mode": "Focus", "splitter": [], "zoom": 1.0, "expanded_geometry": ""},
    }


def clean_config(raw):
    """Repair malformed/older documents without executing or importing anything."""
    cfg = default_settings()
    if not isinstance(raw, dict):
        return cfg
    ver = raw.get("schema_version", 0)
    if not isinstance(ver, int) or ver > 2 or ver < 0:
        raise ValueError("Settings schema is newer than this plugin supports")
    for feature in FEATURES:
        item = raw.get("features", {}).get(feature, {}) if isinstance(raw.get("features"), dict) else {}
        if isinstance(item, dict) and isinstance(item.get("enabled"), bool):
            cfg["features"][feature]["enabled"] = item["enabled"]
    cfg["allow_custom_python"] = raw.get("allow_custom_python") is True
    anchor = raw.get("anchor_manager", {})
    if isinstance(anchor, dict):
        options = cfg["anchor_manager"]
        if isinstance(anchor.get("auto_refresh"), bool):
            options["auto_refresh"] = anchor["auto_refresh"]
        for key, values in (("filter", ("All", "Used", "Unused", "Issues")),
                            ("sort", ("Name", "Uses", "Stack Order", "Source Type")),
                            ("graph_mode", ("Focus", "Overview", "Issues"))):
            if anchor.get(key) in values:
                options[key] = anchor[key]
        sizes = anchor.get("splitter")
        if isinstance(sizes, list) and len(sizes) == 3 and all(type(s) is int and 0 <= s <= 10000 for s in sizes):
            options["splitter"] = list(sizes)
        zoom = anchor.get("zoom")
        if type(zoom) in (int, float) and .25 <= zoom <= 2.5:
            options["zoom"] = float(zoom)
        geometry = anchor.get("expanded_geometry")
        if isinstance(geometry, str) and len(geometry) <= 4096 and all(c in "0123456789abcdef" for c in geometry):
            options["expanded_geometry"] = geometry
    macros = raw.get("macros", [])
    if not isinstance(macros, list):
        raise ValueError("Macros must be a list")
    from .macros import validate_macro
    used_macros = set()
    for macro in macros:
        validate_macro(macro)
        if macro["id"] in used_macros or len(used_macros) >= 100:
            raise ValueError("Duplicate macro identifier or too many macros")
        used_macros.add(macro["id"])
        cfg["macros"].append({"id": macro["id"], "name": macro["name"].strip()[:80],
                              "description": str(macro.get("description", ""))[:500],
                              "steps": list(macro["steps"])})
    menus = raw.get("pie_menus")
    if isinstance(menus, list):
        result, used = [], set()
        for menu in menus[:30]:
            if not isinstance(menu, dict):
                continue
            identifier = menu.get("id")
            if not isinstance(identifier, str) or not SAFE_NAME.fullmatch(identifier) or identifier in used:
                continue
            used.add(identifier)
            actions = menu.get("actions", [])
            if not isinstance(actions, list):
                actions = []
            # Remove the retired inspector command from older saved/imported pies.
            indices = [i for i, a in enumerate(actions) if isinstance(a, str) and len(a) <= 150
                       and a != "mb.performance"][:MAX_PIE_ACTIONS]
            actions = [actions[i] for i in indices]
            result.append({"id": identifier,
                           "name": str(menu.get("name", identifier))[:80],
                           "shortcut": str(menu.get("shortcut", ""))[:80],
                           "actions": actions})
            names = menu.get("action_names")
            if isinstance(names, list):
                result[-1]["action_names"] = [
                    names[i].strip()[:80] if i < len(names) and isinstance(names[i], str) else ""
                    for i in indices]
        cfg["pie_menus"] = result
    return cfg


def normalized_angle_index(x, y, count):
    """Slice zero is top; indices proceed clockwise. Screen y points downward."""
    import math
    if count < 1:
        return None
    angle = (math.degrees(math.atan2(y, x)) + 90 + 360) % 360
    return int(angle / (360.0 / count)) % count


def clone_config(cfg):
    return copy.deepcopy(cfg)
