"""Real Qt signal/timer coverage, isolated from controller tests' host doubles."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional real Qt UI test")
def test_font_live_updates_offscreen(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
from types import SimpleNamespace
from unittest.mock import Mock
sys.modules["substance_painter"] = SimpleNamespace()
sys.modules["substance_painter"].project = SimpleNamespace(Metadata=lambda context: SimpleNamespace(list=lambda: []))
from PySide6 import QtWidgets, QtTest
from MBToolkit_3DPainter.features.font_tool import panel as module
application = QtWidgets.QApplication([])
stack = ["stack"]
module.active_stack = lambda: stack[0]
module.error = Mock()
module.available_font_resources = lambda: resources
resources = [SimpleNamespace(gui_name=lambda: "Font A", identifier=lambda: "a"),
             SimpleNamespace(gui_name=lambda: "Font B", identifier=lambda: "b")]
node = Mock()
node.uid.return_value = 42
source = Mock(resource_id="a")
params = SimpleNamespace(text="Original", auto_size=True, size=.1,
    horizontal_alignment=SimpleNamespace(name="Left"), line_spacing=1., character_spacing=0.)
source.get_parameters.return_value = params
panel = module.Panel(SimpleNamespace(events=SimpleNamespace(add=lambda callback: None)))
panel._selection_timer.stop()
panel._selected_source = Mock(return_value=(node, source))
panel._load_rotation = Mock()
panel._sync_selection()
panel._selection_timer.stop()
assert panel.text.toPlainText() == "Original"
assert panel.live_update.isChecked()
assert panel.size_slider.hasTracking()
assert not panel._update_timer.isActive()
panel._write_selected = Mock()

def wait():
    QtTest.QTest.qWait(350)

# A burst is coalesced into one write of the most recent control state.
panel.text.setPlainText("First")
QtTest.QTest.qWait(80)
panel.text.setPlainText("Latest")
assert panel._update_timer.isActive()
assert panel._pending_identity == ("stack", 42)
panel._write_selected.assert_not_called()
wait()
panel._write_selected.assert_called_once_with(node, source)
assert panel.text.toPlainText() == "Latest"
panel._write_selected.reset_mock()

# Every source control is wired, including the silently synchronized size slider.
changes = [lambda: panel.font.setCurrentIndex(1),
           lambda: panel.size.setValue(.5),
           lambda: panel.size_slider.setValue(600),
           lambda: panel.halign.setCurrentIndex(1),
           lambda: panel.line_spacing.setValue(1.5),
           lambda: panel.char_spacing.setValue(.2)]
for change in changes:
    change()
    assert panel._update_timer.isActive()
    panel._flush_live_update()
assert panel._write_selected.call_count == len(changes)
panel._write_selected.reset_mock()

# Searching/refreshing the catalog is not a font edit. If the current font is
# hidden, subsequent text edits must retain the source's font rather than pick
# the first search result implicitly.
panel.search.setText("Font A")
assert panel.font.currentIndex() == -1
assert not panel._update_timer.isActive()
panel.search.clear()
assert panel.font.currentIndex() == -1
panel.refresh()
panel._selection_timer.stop()
assert not panel._update_timer.isActive()
panel.load_selected()
panel._selection_timer.stop()
wait()
panel._write_selected.assert_not_called()

# Manual mode cancels queued edits, but Update text applies immediately.
panel.text.setPlainText("Pending")
panel.live_update.setChecked(False)
wait()
panel._write_selected.assert_not_called()
panel.text.setPlainText("Manual")
wait()
panel._write_selected.assert_not_called()
panel.update_button.click()
panel._write_selected.assert_called_once_with(node, source)
panel._write_selected.reset_mock()
panel.live_update.setChecked(True)
wait()
panel._write_selected.assert_called_once()
panel._write_selected.reset_mock()
panel.text.setPlainText("Immediate")
panel.update_button.click()
wait()
panel._write_selected.assert_called_once()
panel._write_selected.reset_mock()

# A selection change before the timer fires must never write to the new mask.
panel.text.setPlainText("Do not copy")
node.uid.return_value = 99
panel._flush_live_update()
panel._selection_timer.stop()
panel._write_selected.assert_not_called()
panel.update_selected()
panel._selection_timer.stop()
panel._write_selected.assert_not_called()
assert module.error.call_count == 1
module.error.reset_mock()
node.uid.return_value = 42

# The same node ID on a different texture stack is also a different target.
panel.text.setPlainText("Other stack")
stack[0] = "other"
panel._flush_live_update()
panel._selection_timer.stop()
panel._write_selected.assert_not_called()
stack[0] = "stack"

# Empty text cancels an earlier valid edit without opening a modal error.
panel.text.setPlainText("Valid")
panel.text.setPlainText("  ")
wait()
panel._write_selected.assert_not_called()
module.error.assert_not_called()

# Loading and reentrant source events cannot schedule feedback writes.
panel._loading = True
panel.text.setPlainText("Loading")
panel._loading = False
assert not panel._update_timer.isActive()
panel._write_selected.side_effect = lambda *args: panel._queue_live_update()
panel.text.setPlainText("Reentrant")
wait()
panel._write_selected.assert_called_once()
assert not panel._update_timer.isActive()
panel._write_selected.reset_mock()

# Live failures are non-modal and release the guard; a later edit can retry.
panel._write_selected.side_effect = RuntimeError("Host write failed")
panel.text.setPlainText("Failure")
wait()
assert "Live update failed" in panel.status.text()
assert panel.status.toolTip() == "Host write failed"
assert not panel._updating
module.error.assert_not_called()
panel._write_selected.side_effect = None
panel.text.setPlainText("Retry")
wait()
assert panel.status.text() == "Text mask updated"
assert panel.status.toolTip() == ""
panel._write_selected.reset_mock()

# Losing an editable selection cancels queued work and disables manual apply.
panel.text.setPlainText("Lost selection")
panel._selected_source.side_effect = ValueError("No text selected")
panel._sync_selection()
assert panel._selected_identity is None
assert not panel.update_button.isEnabled()
wait()
panel._write_selected.assert_not_called()
panel._selected_source.side_effect = None
panel._sync_selection()
panel._selection_timer.stop()

# Tool unloading stops both timers and rejects subsequent queued edits.
panel.text.setPlainText("Disposed")
panel.dispose()
assert not panel._update_timer.isActive()
assert not panel._selection_timer.isActive()
panel.request_refresh()
panel.text.setPlainText("After disposal")
wait()
panel._write_selected.assert_not_called()
assert not panel._selection_timer.isActive()
panel.close()
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(root / "painter_python" / "plugins"))
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr