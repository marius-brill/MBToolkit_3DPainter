# MBToolkit_3DPainter — Architecture and Roadmap

> Historical plan: the Performance Inspector was subsequently removed at the
> maintainer's request because it did not measure actual milliseconds. Its design
> and milestones below are superseded and are not active scope or backlog.
> See ROADMAP.md for the current three-feature scope.

**Maintainer:** Marius Brill  
**Initial plugin version:** 0.1.0  
**Application:** Adobe Substance 3D Painter  
**License recommendation:** MIT  
**Planning baseline:** 2026-10-21

## Vision and constraints

Create a public, modular, path-independent Painter productivity plugin. All features are independently enableable/disableable. The plugin must have its own top-level menu, support custom actions and shortcuts, restore user preferences between sessions, cleanly unload/reload, and run without administrator privileges or hard-coded local paths. Support Painter 10.1+ (the last-two-years baseline as of October 2026); test each supported release and capability-check future releases.

### Research conclusions

- Painter plugins expose `start_plugin()` / `close_plugin()` and can be packaged under the application's `python/plugins` path, or under a root exposed by `SUBSTANCE_PAINTER_PLUGINS_PATH` with `plugins`, `startup`, and `modules` directories.
- `substance_painter.ui.add_menu()` supports a dedicated main menu. `ui.add_dock_widget()` supports docked tools with persistent `objectName` layout state.
- Qt moved from PySide2 to PySide6 in Painter 10.1 (September 17, 2024). 10.1+ is therefore a practical baseline, with an adapter for future API changes.
- Layer nodes expose per-channel opacity and blending mode (`get_opacity`, `set_opacity`, `get_blending_mode`, `set_blending_mode`); Adobe publishes an example all-channel blend-mode editor.
- Painter supports font resources through `source.SourceFont` and `SourceFontParams`, including text, sizing, color, alignment, spacing and resolution. The API can create a fill layer and assign a font source.
- The documented Python API does **not** provide stroke access or a confirmed per-layer engine evaluation timer. Do not promise programmable viewport stamping or real layer-render `ms` timing until a supported implementation has been experimentally validated.

## Proposed repository layout

```text
MBToolkit_3DPainter/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
├── pyproject.toml
├── .github/
│   └── workflows/
│       ├── lint-and-test.yml
│       └── release.yml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   ├── COMPATIBILITY.md
│   └── FEATURES.md
├── painter_python/
│   ├── plugins/
│   │   └── MBToolkit_3DPainter/
│   │       ├── __init__.py        # Painter start_plugin/close_plugin
│   │       ├── metadata.py       # single source of version and ID
│   │       ├── bootstrap.py      # lifecycle, service assembly
│   │       ├── core/
│   │       │   ├── feature.py     # feature contracts and lifecycle
│   │       │   ├── registry.py    # feature/action registry
│   │       │   ├── commands.py    # stable action IDs and callbacks
│   │       │   ├── settings.py    # schema, migration, atomic save
│   │       │   ├── capabilities.py# version/API probing
│   │       │   ├── paths.py       # pathlib, QStandardPaths
│   │       │   ├── events.py      # centralized subscriptions
│   │       │   ├── shortcuts.py   # binding + conflicts
│   │       │   └── logging.py     # logs + diagnostics
│   │       ├── adapters/
│   │       │   ├── painter.py     # Painter API façade
│   │       │   └── qt.py          # Qt-specific imports/adapters
│   │       ├── ui/
│   │       │   ├── main_menu.py
│   │       │   ├── preferences.py
│   │       │   └── widgets/
│   │       ├── features/
│   │       │   ├── pie_menus/
│   │       │   │   ├── feature.py
│   │       │   │   ├── editor.py
│   │       │   │   ├── wheel.py
│   │       │   │   └── models.py
│   │       │   ├── channel_blending/
│   │       │   │   ├── feature.py
│   │       │   │   ├── panel.py
│   │       │   │   └── controller.py
│   │       │   ├── performance/
│   │       │   │   ├── feature.py
│   │       │   │   ├── panel.py
│   │       │   │   ├── analyzer.py
│   │       │   │   └── timing_backend.py
│   │       │   └── font_tool/
│   │       │       ├── feature.py
│   │       │       ├── panel.py
│   │       │       ├── font_catalog.py
│   │       │       └── source_controller.py
│   │       └── assets/
│   │           └── icons/
│   ├── startup/
│   └── modules/
├── tests/
│   ├── unit/
│   ├── qt/
│   └── integration/
└── examples/
    └── custom_actions/
```

The directory named `painter_python` is a distribution root. For manual installation, copy `painter_python/plugins/MBToolkit_3DPainter` into Painter's discovered `python/plugins` directory; for development, point `SUBSTANCE_PAINTER_PLUGINS_PATH` to the `painter_python` directory. The package uses normal Python `__init__.py`; validate package discovery on all target platforms as an initial smoke test.

## Architectural rules

1. **One stable entry point:** `__init__.py` delegates to `bootstrap.start()` and `bootstrap.stop()`.
2. **Feature interface:** each feature exposes a stable ID, display name, availability predicate, start/stop hooks, commands, and settings/UI registration.
3. **Registry:** commands and feature IDs are canonical; pie menus reference command IDs, not Qt widget pointers or arbitrary source code.
4. **Adapters:** Painter operations are centralized in `adapters/painter.py`; Qt version specifics in `adapters/qt.py`. Avoid private Painter internals.
5. **Settings:** JSON with independent `schema_version` and plugin version, validated before use and migrated when changed. Use `QStandardPaths.AppConfigLocation` (or another documented user-writable app config path) and atomic writes. No fixed absolute user paths. Allow export/import of settings.
6. **Lifecycle:** stopping a feature removes its menus/shortcuts/widgets/timers/event subscriptions. `close_plugin()` cleans all features, including Qt parents and signal connections. Repeated reload cannot duplicate UI.
7. **Events:** subscribe to project and layer-stack changes once through a coordinator, debounce selection refreshes, and disconnect on unload.
8. **Main thread:** Qt widgets and Painter API changes are handled on their supported thread. Never block the UI with profiling or file operations.
9. **Security:** default pie commands must come from a registered, allowlisted command catalog. Custom Python actions are an explicit advanced opt-in, loaded only from files the user intentionally trusts; do not `eval` arbitrary config strings.
10. **Degrade gracefully:** version and capability checks determine whether actions are available; display disabled states with clear explanations instead of crashing.

## Proposed main menu

```text
MBToolkit
├── Pie Menus
│   ├── Open Pie Menu...
│   └── Manage Pie Menus...
├── Channel Blending...
├── Performance Monitor...
├── Font Tool...
├── Preferences...
├── Diagnostics...
├── Documentation
└── About MBToolkit
```

A single Preferences dialog has General, Features, Pie Menus, Shortcuts, Custom Actions, Appearance and Diagnostics tabs. Every feature has an enable toggle and only displays configurable settings relevant to that feature. The top-level menu persists even when every optional feature is turned off.

## Feature specification

### A. Pie Menu Creator

- User creates, renames, duplicates, removes and reorders multiple menus; assigns per-menu shortcuts; and chooses actions by browsing a searchable catalog.
- Qt overlay paints `N` equal angular wedges (360° / N); angle mapping is deterministic. Cursor hover highlights a wedge; click selects; Escape cancels. Show labels/icons, central dead zone, hover hint, and DPI-aware positioning within available screens.
- Default design supports 1–8 actions comfortably; allow up to 12 with warnings and optional nested submenus for more. Each slice can reference a command, nested menu, or trusted custom script.
- Dispatch commands by stable string ID through a registry. Native Painter commands must have an officially supported API handler; no fragile translated UI-label searches, private widget IDs, or synthetic keystrokes as the sole implementation.
- Qt shortcuts have application-level scope where appropriate. Check against known Painter actions for conflicts and report conflicts rather than silently replacing built-ins. Persist portable `QKeySequence` strings and let users reset them.
- Advanced Python actions are opt-in and can run packaged scripts with an explicit context object. Warn that Python scripts have the user's local permissions.

**Done when:** a user can create two different wheels, assign unique shortcuts, execute a built-in registered command, reorder segments, export settings, disable the feature and reload without shortcut duplication.

### B. All-Channel Blending Panel

- Dockable `Channel Blending` widget follows the active texture set/stack and exactly one selected supported layer.
- Show rows for all available channels, including custom channels, containing enable/available status, opacity slider + numeric entry, and blending mode dropdown. Opacity maps UI 0–100% to API 0.0–1.0.
- Use `node.get_opacity(channel)`, `node.set_opacity(value, channel)`, `node.get_blending_mode(channel)`, `node.set_blending_mode(mode, channel)`; enumerate channels from the active stack. Check `node.has_blending()` and node type.
- Ignore or clearly represent unsupported selection types (effects, mask stacks, multiple nodes) until specifically implemented. Refresh on layer/project events, preserve focus/slider editing and avoid recursive UI-to-model updates with signal blocking.
- Use coalesced slider updates to avoid excessive recomputation. Group multi-setting operations in `layerstack.ScopedModification()` where appropriate, with careful undo behavior.

**Done when:** Base Color, Roughness, Metallic, Normal, Height and project-specific channels appear appropriately, and edits correctly persist in Painter; switching selection does not leave stale callbacks.

### C. Performance Monitor

- v1: non-invasive inspector tree of texture sets, folders, layers, generators and effects; counts, subtree complexity, resolution/UDIM context where accessible, optional static heuristics and sorting. Label these as *complexity indicators*, not measured computation time.
- True per-layer engine `ms` requires a documented engine timing source or a validated instrumented benchmarking protocol with reliable completion notification. No such public, stable API has been verified; gate actual timing behind an optional backend interface.
- Never present `time.perf_counter()` around a Python property query as a GPU layer-computation measurement. Do not auto-toggle layer visibility or mutate user projects without explicit opt-in and save/restore safeguards.
- Future timing mode, if validated: perform controlled trials, warm-ups and repetitions; report median/min/max, resolution, GPU/Painter version, and noise. Separate end-to-end latency from layer GPU cost.

**Done when:** inspector accurately reports structure and its labeled proxy metrics; all unsupported timing columns say unavailable, not invented `ms` values.

### D. Font Tool

- Search installed/available Painter font resources (`resource.Type.FONT` / `resource.search("u:font")`); do not assume OS font directories. Support TTF/OTF fonts that Painter can import/embed, with license limitations.
- Create/edit a `FillLayerNode` using a `SourceFont` and `SourceFontParams`. Controls: text, font, size or auto size, alignment, color, spacing, resolution and background parameters; projection/transform controls only through documented APIs.
- A Qt preview can display a text approximation but cannot be treated as a pixel-identical Painter rendering. Save/reopen font settings via the source, not a redundant unlinked copy.
- Native brush workflows may be assisted by choosing a text resource, but a fully automated on-mesh click-to-stamp cannot be promised without a supported Painter input/stroke API.

**Done when:** a user can search compatible font resources, create a font-based fill, edit it, and reopen the tool without losing source parameters.

## Example configuration schema (illustrative)

```json
{
  "schema_version": 1,
  "plugin_version_last_run": "0.1.0",
  "features": {
    "pie_menus": {"enabled": true},
    "channel_blending": {"enabled": true},
    "performance": {"enabled": false},
    "font_tool": {"enabled": false}
  },
  "pie_menus": [
    {
      "id": "primary",
      "name": "Primary",
      "shortcut": "Ctrl+Alt+Space",
      "actions": ["painter.layer.add_fill", "mbtoolkit.blending.open"]
    }
  ],
  "custom_python_actions_enabled": false
}
```

The default shortcut above is only an example; ship with a tested non-conflicting default or no binding at all. Store feature defaults in a single schema that can migrate old configurations.

## Planned milestones

| Version | Scope | Acceptance criterion |
|---|---|---|
| **0.1.0** | Bootstrapping, plugin top menu, settings migration, feature toggles, lifecycle, registry, first fully working blending panel | Install, disable/re-enable, reload and uninstall safely; blend multiple channels |
| **0.2.0** | Pie menu overlay, editor, command catalog, shortcuts, settings import/export | Multiple user-created radial menus remain correct after relaunch |
| **0.3.0** | Font tool based on documented SourceFont fill resources | Create and edit font fill layers via supported API |
| **0.4.0** | Performance structure inspector; evaluate timing-backend feasibility | Accurate hierarchy + explicit labeling of estimates/unavailable timings |
| **0.5.x** | UX polish, compatibility sweeps, release packaging, optional verified additions | Cross-platform manual test report, reproducible packaged release |
| **1.0.0** | Stable plugin interfaces and user config schema; docs/examples | No known critical crash or data-loss bugs in supported release matrix |

## Test matrix and release gates

- Smoke tests on each supported Painter release and OS accessible to maintainers: package discovery, top menu, docks, settings storage, actions, shortcuts, cleanup and reload.
- Unit tests with mocked Painter adapters for config migration, wheel geometry, action registry, feature switches and path handling.
- Qt tests: high DPI, multi-monitor cursor placement, keyboard navigation, focus restoration, widget destruction and event disconnect.
- Editor tests: project absent, project change, no layer, unsupported layer/effect, mask, multiple selected layers, undo/redo, texture set switch, custom channel change.
- Packaging: no dependence on current working directory or developer-specific installation path; no external dependencies beyond Painter-bundled Python/PySide for core plugin.
- CI: Ruff/pytest, package construction, version metadata checks. CI cannot replace manual in-Painter tests.

## Principal technical risks

1. Unsupported Painter internals may change without notice — prefer documented Python API and isolated adapters.
2. Keyboard shortcuts may conflict with native Painter shortcuts or inactive windows — test Qt shortcut contexts and explain collision handling.
3. Qt object lifecycle on plugin reload may retain callbacks/widgets — centralized teardown and repeated-reload smoke tests.
4. Repeated slider updates may cause costly recomputation — throttle/coalesce and preserve undo semantics.
5. No confirmed engine profiling timing API — avoid misleading millisecond columns; keep timing backend experimental.
6. Python API lacks stroke access — prioritize font fills and separately investigate brush handoff.
7. External user Python commands can execute arbitrary code — opt-in with warnings and never evaluate arbitrary JSON strings.

## Official research references

- Python plugin loader: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/writing-plugins/substance-painter-plugins
- External plugin path: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/tutorials/load-external-python-plugins
- UI module: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/ui
- Qt6 migration: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/tutorials/qt6-migration
- Official blending panel example: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/examples/blending-mode
- Layer navigation and blend API: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/navigation
- Font source API: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/source-module/font
- Paint stroke limitation: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/layers-and-effects/paint
- Painter layer-performance guidance: https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/technical-support/performance-guidelines/layer-management
- Layerstack scoped modifications: https://experienceleague.adobe.com/en/docs/substance-3d-dev/painter-python/api/substancepainter-package/layerstack-module/edition
