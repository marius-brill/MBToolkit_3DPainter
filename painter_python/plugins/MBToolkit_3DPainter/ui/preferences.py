"""Preferences, JSON import/export and explicitly trusted local Python actions."""
from PySide6 import QtCore, QtGui, QtWidgets
from ..core.models import SAFE_NAME
from ..ui.common import error


class Preferences(QtWidgets.QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("MBToolkit · Preferences")
        self.resize(560, 420)
        outer = QtWidgets.QVBoxLayout(self)
        tabs = QtWidgets.QTabWidget()
        outer.addWidget(tabs)

        feature_tab = QtWidgets.QWidget()
        feat = QtWidgets.QVBoxLayout(feature_tab)
        feat.addWidget(QtWidgets.QLabel("Enable features independently (changes apply immediately)."))
        self.toggles = {}
        for fid, name in (("pie_menus", "Pie Menu Creator"),
                          ("channel_blending", "All-Channel Blending"),
                          ("font_tool", "Font Tool")):
            check = QtWidgets.QCheckBox(name)
            check.setChecked(app.settings.enabled(fid))
            check.toggled.connect(lambda enabled, id=fid: self.switch(id, enabled))
            feat.addWidget(check)
            self.toggles[fid] = check
        feat.addStretch()
        tabs.addTab(feature_tab, "Features")

        pie = QtWidgets.QWidget()
        pie_layout = QtWidgets.QVBoxLayout(pie)
        pie_layout.addWidget(QtWidgets.QLabel("Create wheels, assign actions and keyboard shortcuts."))
        manage = QtWidgets.QPushButton("Manage Pie Menus...")
        manage.clicked.connect(self.app.open_pie_editor)
        pie_layout.addWidget(manage)
        pie_layout.addStretch()
        tabs.addTab(pie, "Pie Menus")

        custom = QtWidgets.QWidget()
        cl = QtWidgets.QVBoxLayout(custom)
        self.opt_in = QtWidgets.QCheckBox("Allow trusted custom Python actions")
        self.opt_in.setChecked(bool(app.settings.data["allow_custom_python"]))
        self.opt_in.toggled.connect(self._change_custom_permission)
        cl.addWidget(self.opt_in)
        note = QtWidgets.QLabel("WARNING: these scripts run with your user account's local permissions. "
                                "Only save and run Python you wrote or personally trust.")
        note.setWordWrap(True)
        cl.addWidget(note)
        self.script_name = QtWidgets.QLineEdit()
        self.script_name.setPlaceholderText("Script ID, e.g. my_action")
        cl.addWidget(self.script_name)
        self.script_text = QtWidgets.QPlainTextEdit()
        self.script_text.setPlainText("# Trusted local Python command\nimport substance_painter as sp\nprint('MBToolkit action')\n")
        cl.addWidget(self.script_text, 1)
        save_script = QtWidgets.QPushButton("Save Python action")
        save_script.clicked.connect(self._save_script)
        cl.addWidget(save_script)
        folder = QtWidgets.QPushButton("Open actions folder")
        folder.clicked.connect(self._open_scripts_folder)
        cl.addWidget(folder)
        tabs.addTab(custom, "Python Actions")

        general = QtWidgets.QWidget()
        gl = QtWidgets.QVBoxLayout(general)
        gl.addWidget(QtWidgets.QLabel("Preferences are stored in your user configuration directory."))
        config_path = QtWidgets.QLineEdit(str(app.settings.path))
        config_path.setReadOnly(True)
        gl.addWidget(config_path)
        for title, slot in (("Export settings JSON...", self._export),
                            ("Import settings JSON...", self._import)):
            btn = QtWidgets.QPushButton(title)
            btn.clicked.connect(slot)
            gl.addWidget(btn)
        gl.addStretch()
        tabs.addTab(general, "General")

        close = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        outer.addWidget(close)

    def switch(self, fid, enabled):
        previous = self.app.settings.enabled(fid)
        try:
            self.app.settings.set_enabled(fid, enabled)
            self.app.reconcile_features()
        except Exception as exc:
            self.app.settings.set_enabled(fid, previous)
            self.toggles[fid].blockSignals(True)
            self.toggles[fid].setChecked(previous)
            self.toggles[fid].blockSignals(False)
            error(self, "Enable/disable feature", exc)

    def _change_custom_permission(self, value):
        if value:
            answer = QtWidgets.QMessageBox.warning(
                self, "Allow arbitrary Python execution?",
                "MBToolkit will execute .py files from its local scripts directory when called by a pie. "
                "Scripts have the same filesystem and network access as Painter. Continue?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                self.opt_in.blockSignals(True)
                self.opt_in.setChecked(False)
                self.opt_in.blockSignals(False)
                return
        self.app.settings.data["allow_custom_python"] = value
        self.app.settings.save()

    def _save_script(self):
        name = self.script_name.text().strip()
        if not SAFE_NAME.fullmatch(name):
            return error(self, "Script name", "Use 1–64 letters, digits, hyphens or underscores.")
        scripts = self.app.settings.directory / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        target = scripts / (name + ".py")
        if target.exists():
            answer = QtWidgets.QMessageBox.question(self, "Replace script?", f"Overwrite {name}.py?")
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        try:
            target.write_text(self.script_text.toPlainText(), encoding="utf-8")
            QtWidgets.QMessageBox.information(self, "Saved", "Select Python: " + name + " in Pie Menu Editor.")
        except Exception as exc:
            error(self, "Write script", exc)

    def _open_scripts_folder(self):
        folder = self.app.settings.directory / "scripts"
        folder.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))

    def _export(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export settings", "MBToolkit-settings.json", "JSON (*.json)")
        if path:
            try:
                self.app.settings.export_to(path)
            except Exception as exc:
                error(self, "Export settings", exc)

    def _import(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import settings", "", "JSON (*.json)")
        if path:
            try:
                self.app.settings.import_from(path)
                # Imported files cannot silently enable arbitrary script execution.
                if self.app.settings.data.get("allow_custom_python"):
                    self.app.settings.data["allow_custom_python"] = False
                    self.app.settings.save()
                self.opt_in.blockSignals(True)
                self.opt_in.setChecked(False)
                self.opt_in.blockSignals(False)
                self.app.reconcile_features()
                self.app.refresh_pie_shortcuts()
                for id, check in self.toggles.items():
                    check.blockSignals(True)
                    check.setChecked(self.app.settings.enabled(id))
                    check.blockSignals(False)
            except Exception as exc:
                error(self, "Import settings", exc)
