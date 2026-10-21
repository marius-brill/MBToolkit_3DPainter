"""Read-only diagnostic reporting without requiring the host."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace


def load_diagnostics():
    path = Path(__file__).resolve().parents[1] / "scripts" / "painter_diagnostics.py"
    spec = importlib.util.spec_from_file_location("painter_diagnostics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_does_not_import_or_start_plugin(monkeypatch):
    module = load_diagnostics()
    monkeypatch.delitem(module.sys.modules, "MBToolkit_3DPainter", raising=False)
    menus = [SimpleNamespace(objectName=lambda: "MBToolkit_MainMenu"),
             SimpleNamespace(objectName=lambda: "Other")]
    painter = SimpleNamespace(
        application=SimpleNamespace(version_info=lambda: (10, 1, 0)),
        ui=SimpleNamespace(get_main_window=lambda: SimpleNamespace(findChildren=lambda cls: menus)))
    report = module.collect_report(painter, SimpleNamespace(QMenu=object))
    assert report["main_menu_count"] == 1
    assert report["plugin_started"] is False
    assert report["plugin_imported"] is False
    assert "MBToolkit_3DPainter" not in module.sys.modules


def test_report_includes_started_plugin_state(monkeypatch):
    module = load_diagnostics()
    app = SimpleNamespace(
        active={"pie_menus"}, settings=SimpleNamespace(path=Path("settings.json")),
        events=SimpleNamespace(connected=[object()], listeners={object()}),
        features={"pie_menus": SimpleNamespace(shortcuts=[])})
    monkeypatch.setitem(module.sys.modules, "MBToolkit_3DPainter",
                        SimpleNamespace(_app=app, __file__="plugin/__init__.py"))
    painter = SimpleNamespace(
        application=SimpleNamespace(version_info=lambda: (10, 1, 0)),
        ui=SimpleNamespace(get_main_window=lambda: SimpleNamespace(findChildren=lambda cls: [])))
    report = module.collect_report(painter, SimpleNamespace(QMenu=object))
    assert report["plugin_started"] is True
    assert report["active_features"] == ["pie_menus"]
    assert report["event_connections"] == 1
    assert report["pie_shortcuts"] == 0