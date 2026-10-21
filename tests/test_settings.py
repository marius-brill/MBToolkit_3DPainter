from MBToolkit_3DPainter.core.settings import Settings
import json
import pytest


def test_settings_roundtrip(tmp_path):
    s = Settings(tmp_path)
    s.load()
    s.set_enabled("font_tool", False)
    assert json.loads(s.path.read_text())["features"]["font_tool"]["enabled"] is False
    again = Settings(tmp_path)
    again.load()
    assert again.enabled("font_tool") is False
    again.export_to(tmp_path / "export.json")
    again.set_enabled("font_tool", True)
    again.import_from(tmp_path / "export.json")
    assert again.enabled("font_tool") is False


def test_legacy_inspector_settings_load_and_import(tmp_path):
    legacy = {"features": {"performance": {"enabled": True}},
              "pie_menus": [{"id": "main", "actions": ["mb.performance", "mb.fonts"]}]}
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    settings = Settings(tmp_path)
    settings.load()
    assert "performance" not in settings.data["features"]
    assert settings.data["pie_menus"][0]["actions"] == ["mb.fonts"]
    settings.import_from(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "performance" not in saved["features"]
    assert saved["pie_menus"][0]["actions"] == ["mb.fonts"]


def test_does_not_overwrite_future_schema(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text('{"schema_version": 100}')
    s = Settings(tmp_path)
    with pytest.raises(RuntimeError):
        s.load()
    assert json.loads(p.read_text()) == {"schema_version": 100}
