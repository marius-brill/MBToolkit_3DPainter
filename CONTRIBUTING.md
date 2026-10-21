# Contributing

Contributions and issue reports are welcome. Maintainer: **Marius Brill**.

- Use feature branches and focused pull requests. Keep `substance_painter` APIs in adapters or individual feature modules.
- Avoid private Painter/Qt UI internals, fixed installation paths, unsafe automatic code execution or application-global monkey-patching.
- Include tests for Qt-independent behavior; attach screenshots, Painter version and OS for UI issues.
- Clean up every QAction, widget, timer and Painter event listener on `close_plugin()`.
- Keep documented feature limitations explicit; do not claim per-node render milliseconds from Python lookup durations.

Run `python -m pytest -q` and `ruff check` before submitting.
