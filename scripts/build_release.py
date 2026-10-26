"""Build an installable ZIP with a fixed Painter package directory."""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


NAME = "MBToolkit_3DPainter"


def build_release(destination, root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    runtime = root / "painter_python" / "plugins" / NAME
    if not (runtime / "__init__.py").is_file():
        raise ValueError("Canonical runtime entry point is missing")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for path in sorted(runtime.rglob("*.py")):
            if "__pycache__" not in path.parts:
                archive.write(path, (Path(NAME) / path.relative_to(runtime)).as_posix())
        for name in ("README.md", "LICENSE", "CHANGELOG.md"):
            archive.write(root / name, f"{NAME}/{name}")
        archive.write(root / "docs" / "ANCHOR_MANAGER.md", f"{NAME}/docs/ANCHOR_MANAGER.md")
        archive.write(root / "docs" / "LAYER_GRAPH.md", f"{NAME}/docs/LAYER_GRAPH.md")
    with ZipFile(destination) as archive:
        names = archive.namelist()
        if any(name.split("/")[0] != NAME for name in names) or f"{NAME}/__init__.py" not in names:
            raise ValueError("Invalid release layout")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    print(build_release(parser.parse_args().destination))