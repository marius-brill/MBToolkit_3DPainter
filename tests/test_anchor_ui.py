"""Real offscreen Qt, isolated from existing minimal Qt module doubles."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional offscreen Qt")
def test_panel_controller_graph_dialog_and_teardown(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
from types import SimpleNamespace
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from PySide6 import QtWidgets, QtTest
from anchor_fixtures import FakeHost, Node, Reference
from MBToolkit_3DPainter.core.settings import Settings
from MBToolkit_3DPainter.features.anchor_manager.controller import Controller
from MBToolkit_3DPainter.features.anchor_manager.ui.manager_panel import Panel
from MBToolkit_3DPainter.features.anchor_manager.ui.dialogs import ReplaceDialog
application = QtWidgets.QApplication([])
host = FakeHost()
listeners = set()
events = SimpleNamespace(add=listeners.add, remove=listeners.discard)
settings = Settings(sys.argv[3])
app = SimpleNamespace(settings=settings)
controller = Controller(host.adapter, events, settings)
panel = Panel(app, controller)
panel.resize(1200, 720)
panel.show()
QtTest.QTest.qWait(150)
assert len(controller.index.anchors) == 2, controller.error
assert panel.library.topLevelItemCount() == 2
controller.select(host.adapter.key(host.anchor))
assert panel.uses.topLevelItemCount() == 2
panel.graph.view.rebuild()
assert len(panel.graph.view.edges) == 2
panel.query.setText('not-found')
QtTest.QTest.qWait(200)
assert panel.library.topLevelItemCount() == 0
panel.query.clear()
QtTest.QTest.qWait(200)
dialog = ReplaceDialog(controller, list(controller.index.references), panel)
assert len(dialog.selected_previews()) == 2
assert dialog.slots == tuple(controller.index.references)
dialog.reject()
panel.expand()
assert panel.expanded.isVisible()
panel.expanded.close()
panel.resize(600, 800)
QtTest.QTest.qWait(20)
assert panel.grab().width() > 0
old_revision = controller.revision
for i in range(5):
    controller.request_refresh()
QtTest.QTest.qWait(150)
assert controller.revision == old_revision
QtTest.QTest.qWait(300)
assert controller.revision == old_revision + 1
host.opened = False
controller.request_refresh()
assert not controller.index.anchors
QtTest.QTest.qWait(450)
assert 'Open a Substance' in controller.state
host.opened = True
controller.refresh()
QtTest.QTest.qWait(100)
host.adapter.roots = lambda: (_ for _ in ()).throw(RuntimeError('scan failed'))
controller.refresh()
QtTest.QTest.qWait(100)
assert controller.error == 'scan failed'
assert 'scan failed' in panel.status.text()
panel.dispose()
assert not listeners
assert not controller.poll.isActive() and not controller.pump.isActive()
panel.close()
assert not controller.visible or controller.disposed
print('Anchor UI checks passed')
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([sys.executable, "-B", "-c", script,
                             str(root / "painter_python" / "plugins"), str(root / "tests"), str(tmp_path)],
                            capture_output=True, text=True, env=env, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr