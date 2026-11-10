"""Native search tested with real Qt in isolation from fake-host imports."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Optional offscreen Qt")
def test_native_layer_search():
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
sys.path.insert(0, sys.argv[1])
from PySide6 import QtCore, QtGui, QtWidgets
from MBToolkit_3DPainter.features.layer_search.native import LayerSearch
app = QtWidgets.QApplication([])
window = QtWidgets.QMainWindow()
dock = QtWidgets.QDockWidget('Layers', window)
window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
content = QtWidgets.QWidget()
layout = QtWidgets.QVBoxLayout(content)
tree = QtWidgets.QTreeView()
layout.addWidget(tree)
dock.setWidget(content)
model = QtGui.QStandardItemModel()
folder = QtGui.QStandardItem('Materials')
nested = QtGui.QStandardItem('Details')
gold = QtGui.QStandardItem('Gold trim')
silver = QtGui.QStandardItem('Silver')
nested.appendRow(gold)
folder.appendRow(nested)
folder.appendRow(silver)
model.appendRow(folder)
model.appendRow(QtGui.QStandardItem('Wood'))
model.appendRow(QtGui.QStandardItem('Already hidden'))
tree.setModel(model)
tree.setRowHidden(2, QtCore.QModelIndex(), True)
selection = tree.selectionModel()
search = LayerSearch(window)
search.start()
assert search.field is not None, search.status
assert layout.itemAt(0).widget() is search.field
assert search.field.maximumHeight() == 24
search.field.setText('GOLD')
assert not tree.isRowHidden(0, QtCore.QModelIndex())
assert tree.isExpanded(folder.index()) and tree.isExpanded(nested.index())
assert tree.isRowHidden(1, folder.index())
assert tree.isRowHidden(1, QtCore.QModelIndex())
assert not tree.isRowHidden(0, nested.index())
assert tree.model() is model and tree.selectionModel() is selection
search.field.setText('Materials')
assert not tree.isRowHidden(1, folder.index())
search.field.setText('no match')
assert tree.isRowHidden(0, QtCore.QModelIndex())
search.field.clear()
assert not tree.isRowHidden(0, QtCore.QModelIndex())
assert not tree.isExpanded(folder.index()) and not tree.isExpanded(nested.index())
assert tree.isRowHidden(2, QtCore.QModelIndex())
search.field.setText('copper')
gold.setText('Copper trim')
app.processEvents()
assert not tree.isRowHidden(0, nested.index())
new = QtGui.QStandardItem('Copper leaf')
model.appendRow(new)
app.processEvents()
assert not tree.isRowHidden(new.row(), QtCore.QModelIndex())
model.removeRow(1)
app.processEvents()
search.stop()
assert not search.poll.isActive() and not search.refresh.isActive()
assert not tree.isRowHidden(0, QtCore.QModelIndex())
assert not tree.isExpanded(folder.index())
app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
assert not content.findChildren(QtWidgets.QLineEdit)
search.start()
assert len(content.findChildren(QtWidgets.QLineEdit)) == 1
search.field.setText('anything')
replacement = QtGui.QStandardItemModel()
replacement.appendRow(QtGui.QStandardItem('New stack'))
tree.setModel(replacement)
search.discover()
app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
assert search.filter.model is replacement
assert not tree.isRowHidden(0, QtCore.QModelIndex())
search.field.setText('missing')
replacement.clear()
replacement.appendRow(QtGui.QStandardItem('missing'))
app.processEvents()
assert not tree.isRowHidden(0, QtCore.QModelIndex())
search.stop()
app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
# Ambiguous/native-incompatible layouts must not receive a search field.
other = QtWidgets.QTreeView(content)
layout.addWidget(other)
other.setModel(QtGui.QStandardItemModel())
search.start()
assert search.field is None
search.stop()
other.setParent(None)
dock.setWindowTitle('Layer Graph')
search.start()
assert search.field is None
search.stop()
print('Native layer search checks passed')
from types import SimpleNamespace
from MBToolkit_3DPainter.features.layer_search.native import WidgetFilter
class Row(QtWidgets.QWidget):
    def metaObject(self):
        return SimpleNamespace(className=lambda: 'Alg::ListWidget')
class EditLabel(QtWidgets.QWidget):
    def metaObject(self):
        return SimpleNamespace(className=lambda: 'Alg::EditLabel')
class LayerView(QtWidgets.QWidget):
    def metaObject(self):
        return SimpleNamespace(className=lambda: 'Alg::LayerView')
native = QtWidgets.QWidget()
parent = Row(native)
child = Row(parent)
sibling = Row(parent)
grandchild = Row(child)
unrelated = Row(native)
for row, text in ((parent, 'Folder'), (child, 'Nested layer'), (sibling, 'Sibling'),
                  (grandchild, 'Effect'), (unrelated, 'Wood')):
    edit = EditLabel(row)
    QtWidgets.QLabel(text, edit)
    if row is not grandchild:
        LayerView(row)
    row.show()
button = QtWidgets.QToolButton(parent)
button.setObjectName('wrappedWidget_collapsableButton')
button.setCheckable(True)
button.show()
child.hide()
button.clicked.connect(lambda checked: child.setVisible(checked))
button.clicked.connect(lambda checked: sibling.setVisible(checked))
filter = WidgetFilter(native)
filter.apply('NESTED')
assert not parent.isHidden() and not child.isHidden() and unrelated.isHidden()
assert sibling.isHidden() and not grandchild.isHidden()
assert button.isChecked()
index = filter.index
filter.apply('NESTED')
assert filter.index is index, 'Typing should reuse the widget index'
filter.apply('folder')
assert not child.isHidden() and not sibling.isHidden() and not grandchild.isHidden()
filter.apply('effect')
assert all(row.isHidden() for row in (parent, child, grandchild, sibling, unrelated))
filter.apply('NESTED')
assert sibling.isHidden() and not grandchild.isHidden()
filter.apply('missing')
assert all(row.isHidden() for row in (parent, child, unrelated))
filter.restore()
assert not parent.isHidden() and child.isHidden() and not unrelated.isHidden()
assert not button.isChecked()
assert not sibling.isHidden()
filter.invalidate()
edit = sibling.findChildren(EditLabel)[0]
edit.findChildren(QtWidgets.QLabel)[0].setText('Nested sibling')
filter.apply('nested')
assert not sibling.isHidden()
filter.restore()
print('Native widget-list search checks passed')
'''
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(root / "painter_python" / "plugins")],
        capture_output=True, text=True, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr