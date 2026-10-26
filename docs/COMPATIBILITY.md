# Compatibility

**Target:** Adobe Substance 3D Painter **10.1+**, including releases in the last two years from October 2026 and future releases *only where APIs remain compatible*. Adobe switched from PySide2 to PySide6 in 10.1. Features gate on documented APIs and report failures instead of silently guessing.

**Verification status:** Not run inside any Adobe Substance 3D Painter binary in the development container, so all host versions and platforms are currently **unverified**. Do not label a version "supported" in a GitHub release until it passes the interactive checklist.

- 10.0 and earlier: intentionally unsupported (Qt5/PySide2).
- 10.1–current: targeted but unverified; this plugin is for **Painter only**.
- Future: never guarantee compatibility with untested releases.
- OS: target Windows, Linux and macOS where Painter is available.
- Settings locations and scripts: Qt's `QStandardPaths.AppConfigLocation`; no fixed drives or user home folders.

See [MANUAL_TESTS.md](MANUAL_TESTS.md) for the release criteria.

## Anchor Manager

Installed 11.0.3 / API 0.3.4 wrappers were inspected on October 24, 2026; interactive host testing remains pending.
The optional feature uses runtime gates, and deliberately reports partial usage coverage for unverified inputs.
See [ANCHOR_MANAGER.md](ANCHOR_MANAGER.md) for the per-operation matrix, known gaps, local tests and required host checklist.
