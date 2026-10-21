"""Allow this checkout to load directly from Painter's user plugins directory.

The distributed package remains the single implementation of the lifecycle.
Only this fixed, local entry point is executed; no user-supplied path is evaluated.
"""
from pathlib import Path as _Path

_runtime = (_Path(__file__).resolve().parent / "painter_python" / "plugins"
            / "MBToolkit_3DPainter")
if not (_runtime / "__init__.py").is_file():
    raise ImportError(f"MBToolkit runtime package is missing: {_runtime}")

# Relative imports and reloads resolve directly to the canonical runtime modules.
__path__ = [str(_runtime)]
_entry = _runtime / "__init__.py"
exec(compile(_entry.read_text(encoding="utf-8"), str(_entry), "exec"), globals())