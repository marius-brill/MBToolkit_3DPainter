# Architecture · 0.1.0

```text
painter_python/plugins/MBToolkit_3DPainter/
├── __init__.py                 Painter lifecycle (start/close/reload)
├── bootstrap.py                Owns menu, features, commands, settings and events
├── core/
│   ├── models.py               Settings validation + radial geometry (no Qt)
│   ├── settings.py             Atomic JSON save + import/export
│   ├── commands.py             Stable command catalog + opt-in local scripts
│   ├── feature.py              Dock lifecycle with Painter-managed widgets
│   └── events.py               Shared layer/project event hub
├── adapters/painter.py         Public Painter API wrappers and capability check
├── ui/                         Preferences dialog and common UI helpers
└── features/
    ├── pie_menus/              Radial QPainter popup, editor and shortcuts
    ├── channel_blending/       Per-channel blended modes + opacity panel
    └── font_tool/              SourceFont fill editor
```

Plugin dependencies flow from `bootstrap` into feature modules, never from one feature into another. `Commands` stores stable IDs so configurations can survive renaming UI labels. User scripts live in a user-specific configuration directory, not inside an installation or Git checkout.

`close_plugin()` tears down feature-owned Qt actions, docks and Painter callbacks. `reload_plugin()` drops package submodules after `close_plugin()` to avoid stale UI types on a Painter plugin reload. Initial startup checks Painter 10.1+ for PySide6 compatibility.

For the future: unit-testable controller layers, more Painter-native commands, configurable radial styles, selection-context permissions, better undo grouping, projection/resolution/background controls for fonts and version-specific Painter integration adapters. Text color is already implemented. See ROADMAP.md for implementation status and release gates.
