import sys
from pathlib import Path

PLUGINS = Path(__file__).resolve().parents[1] / "painter_python" / "plugins"
sys.path.insert(0, str(PLUGINS))
