from MBToolkit_3DPainter.core.models import clean_config, default_settings, normalized_angle_index
import pytest


def test_default_features():
    config = default_settings()
    assert set(config["features"]) == {"pie_menus", "channel_blending", "font_tool"}
    assert "mb.performance" not in config["pie_menus"][0]["actions"]
    assert config["schema_version"] == 1


def test_validation_migration_and_restrictions():
    old = {"features": {"font_tool": {"enabled": False}},
           "pie_menus": [{"id": "good", "name": "Test", "shortcut": "",
                         "actions": ["mb.fonts"]*25}, {"id": "../bad", "actions": []},
                        {"id": "good", "actions": []}]}
    cfg = clean_config(old)
    assert cfg["features"]["font_tool"]["enabled"] is False
    assert len(cfg["pie_menus"]) == 1
    assert len(cfg["pie_menus"][0]["actions"]) == 12
    assert cfg["allow_custom_python"] is False


def test_rejects_newer_settings_schema():
    with pytest.raises(ValueError):
        clean_config({"schema_version": 42})


@pytest.mark.parametrize("schema", [0, 1])
def test_retired_inspector_removed_without_losing_other_settings(schema):
    raw = {"schema_version": schema,
           "features": {"performance": {"enabled": True}, "font_tool": {"enabled": False}},
           "pie_menus": [{"id": "custom", "name": "Custom", "shortcut": "Ctrl+1",
                          "actions": ["mb.performance", "mb.fonts", "python:trusted", "mb.performance"]},
                         {"id": "old", "name": "Old", "actions": ["mb.performance"]}]}
    result = clean_config(raw)
    assert "performance" not in result["features"]
    assert result["features"]["font_tool"]["enabled"] is False
    assert result["pie_menus"][0] == {
        "id": "custom", "name": "Custom", "shortcut": "Ctrl+1",
        "actions": ["mb.fonts", "python:trusted"]}
    assert result["pie_menus"][1]["actions"] == []
    assert clean_config(result) == result


def test_custom_pie_names_survive_validation_and_follow_filtered_actions():
    raw = {"pie_menus": [{"id": "main", "actions": ["mb.fonts", "mb.performance", None, "mb.blending"],
                          "action_names": [" Typography ", "Retired", "Invalid", "Mix"]}]}
    config = clean_config(raw)
    menu = config["pie_menus"][0]
    assert menu["actions"] == ["mb.fonts", "mb.blending"]
    assert menu["action_names"] == ["Typography", "Mix"]
    assert clean_config(config) == config


def test_custom_pie_names_repair_invalid_and_missing_names():
    config = clean_config({"pie_menus": [{"id": "main", "actions": ["a", "b", "c"],
                                          "action_names": [None, "x"*100]}]})
    assert config["pie_menus"][0]["action_names"] == ["", "x"*80, ""]


def test_geometry():
    assert normalized_angle_index(0, -100, 4) == 0
    assert normalized_angle_index(100, 0, 4) == 1
    assert normalized_angle_index(0, 100, 4) == 2
    assert normalized_angle_index(-100, 0, 4) == 3
    assert normalized_angle_index(10, 10, 0) is None
    assert all(0 <= normalized_angle_index(12, -10, n) < n for n in range(1, 13))
