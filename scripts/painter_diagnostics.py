"""Read-only console diagnostics. Does not start/reload the plugin or edit projects."""
import json
import os
import platform
import sys


def collect_report(painter, widgets):
    """Accept host modules explicitly so report behavior can be tested without Painter."""
    package = sys.modules.get("MBToolkit_3DPainter")
    app = getattr(package, "_app", None)
    window = painter.ui.get_main_window()
    report = {
        "painter_version": list(painter.application.version_info()),
        "python_version": platform.python_version(),
        "os": platform.platform(),
        "external_plugin_path": os.environ.get("SUBSTANCE_PAINTER_PLUGINS_PATH"),
        "plugin_imported": package is not None,
        "plugin_path": getattr(package, "__file__", None),
        "plugin_started": app is not None,
        "main_menu_count": len([
            menu for menu in window.findChildren(widgets.QMenu)
            if menu.objectName() == "MBToolkit_MainMenu"
        ]),
        "interactive_checks": "NOT RUN; use docs/MANUAL_TESTS.md",
    }
    if app is not None:
        report.update({
            "active_features": sorted(app.active),
            "settings_path": str(app.settings.path),
            "event_connections": len(app.events.connected),
            "event_listeners": len(app.events.listeners),
            "pie_shortcuts": len(app.features["pie_menus"].shortcuts),
        })
    return report


def main():
    import substance_painter as painter
    from PySide6 import QtWidgets

    print(json.dumps(collect_report(painter, QtWidgets), indent=2))


if __name__ == "__main__":
    main()