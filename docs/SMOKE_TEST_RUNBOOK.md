# Windows development smoke test

## Launch without persistent environment changes

From the repository root in PowerShell:

```powershell
& .\scripts\launch_painter.ps1
& .\scripts\launch_painter.ps1 -Launch
```

The first command performs preflight only. An alternate install can be supplied
using `-PainterExecutable` with its absolute executable path. The launcher uses
the repository location, sets discovery only while launching the child, restores
the calling environment, and refuses to replace an existing different discovery
configuration. Close Painter normally first; a running instance will not inherit
the new environment. Local execution policy may require an approved script policy.

This repository is itself inside a plugins directory in some development setups.
Its outer folder now has a forwarding entry point for direct user-plugin discovery.
For that layout, launch Painter normally without the external path. The launcher
is an alternative for checkouts outside the user plugins directory. Do not copy
the inner package over the repository root or enable two copies simultaneously.

## Capture read-only runtime diagnostics

1. Load MBToolkit_3DPainter through Painter's Python Plugins menu.
2. Open Painter's Python console and run the following, replacing the path with
   the absolute path of this repository's diagnostic script:

```python
import runpy
runpy.run_path(r"C:\path\to\repository\scripts\painter_diagnostics.py", run_name="__main__")
```

3. Save the printed JSON with the test report. Expected after successful startup:
   `plugin_started` true, `main_menu_count` 1, and the expected enabled features.
   The script does not import/start/reload the plugin or change project/settings
   data. It does expose local paths in its output; redact them before sharing.
4. Follow MANUAL_TESTS.md with a disposable project. Record console errors, GPU,
   actual Painter version, OS and each pass/fail. Diagnostics alone are not a pass.
5. Repeat the diagnostic capture after five normal plugin reloads. Menu,
   subscription, listener and shortcut counts should remain stable when feature
   and shortcut settings have not changed.

## Evidence status

Host-independent tests do not verify Painter discovery, rendering, dock ownership,
event delivery, shortcuts, undo, or reload safety. Never mark interactive checklist
items complete merely because the executable launched or a diagnostic count agrees.