from MBToolkit_3DPainter.core.settings import Settings
from MBToolkit_3DPainter.core.commands import Commands
import pytest


def test_allowlisted_command(tmp_path):
    command = Commands(Settings(tmp_path))
    actions = []
    command.register("test.run", "Execute", lambda: actions.append(True))
    command.execute("test.run")
    assert actions == [True]
    with pytest.raises(ValueError):
        command.register("test.run", "Duplicate", lambda: None)


def test_script_gate(tmp_path):
    settings = Settings(tmp_path)
    directory = settings.directory / "scripts"
    directory.mkdir()
    (directory / "safe.py").write_text("result = 5\n")
    cmd = Commands(settings)
    assert ("python:safe", "Python: safe") in cmd.catalog()
    with pytest.raises(PermissionError):
        cmd.execute("python:safe")
    settings.data["allow_custom_python"] = True
    cmd.execute("python:safe")
    with pytest.raises(ValueError):
        cmd.execute("python:../escape")
