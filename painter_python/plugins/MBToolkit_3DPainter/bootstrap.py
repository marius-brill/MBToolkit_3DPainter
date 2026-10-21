"""Application assembly and single-owner lifecycle."""
from PySide6 import QtWidgets
import substance_painter as sp
from .metadata import DISPLAY_NAME, VERSION, MAINTAINER, MIN_PAINTER
from .core.settings import Settings
from .core.commands import Commands
from .core.events import EventBus
from .core.feature import DockFeature
from .adapters.painter import compatible, add_fill_layer
from .ui.common import error
from .ui.preferences import Preferences
from .features.pie_menus.feature import Feature as PieFeature
from .features.channel_blending.panel import Panel as BlendPanel
from .features.font_tool.panel import Panel as FontPanel


class Blending(DockFeature):
    id = "channel_blending"
    label = "MBToolkit · Channel Blending"
    def create_panel(self):
        return BlendPanel(self.app)


class Fonts(DockFeature):
    id = "font_tool"
    label = "MBToolkit · Font Tool"
    def create_panel(self):
        return FontPanel(self.app)


class Toolkit:
    def __init__(self):
        self.main_window = None
        self.menu = None
        self.menus = {}
        self.settings = None
        self.events = EventBus()
        self.commands = None
        self.features = {}
        self.active = set()
        self.preferences = None

    def start(self):
        if not compatible():
            raise RuntimeError(f"MBToolkit requires Painter {MIN_PAINTER[0]}.{MIN_PAINTER[1]}+ with PySide6")
        self.main_window = sp.ui.get_main_window()
        self.settings = Settings()
        self.settings.load()
        self.commands = Commands(self.settings)
        self.events.start()
        self.features = {"pie_menus": PieFeature(self), "channel_blending": Blending(self),
                         "font_tool": Fonts(self)}
        self._register_commands()
        self._create_menu()
        self.reconcile_features()

    def _register_commands(self):
        for id, label, fn in (
            ("mb.preferences", "MBToolkit Preferences", self.open_preferences),
            ("mb.pies.edit", "Manage Pie Menus", self.open_pie_editor),
            ("mb.blending", "Open Channel Blending", lambda: self.show_feature("channel_blending")),
            ("mb.fonts", "Open Font Tool", lambda: self.show_feature("font_tool")),
            ("painter.add_fill", "Painter: Add Fill Layer", add_fill_layer),
            ("painter.add_paint", "Painter: Add Paint Layer", self._add_paint),
            ("painter.add_group", "Painter: Add Folder", self._add_group),
        ):
            self.commands.register(id, label, fn)

    def _add_paint(self):
        from .adapters.painter import active_stack
        stack = active_stack()
        if stack is None:
            raise RuntimeError("Open a project first")
        sp.layerstack.insert_paint(sp.layerstack.InsertPosition.from_textureset_stack(stack))

    def _add_group(self):
        from .adapters.painter import active_stack
        stack = active_stack()
        if stack is None:
            raise RuntimeError("Open a project first")
        sp.layerstack.insert_group(sp.layerstack.InsertPosition.from_textureset_stack(stack))

    def _action(self, parent, title, callback, feature=None):
        action = parent.addAction(title)
        action.triggered.connect(lambda *_: self._safe_call(callback))
        if feature:
            self.menus[feature] = action
        return action

    def _safe_call(self, callback):
        try:
            callback()
        except Exception as exc:
            error(self.main_window, "MBToolkit", exc)

    def _create_menu(self):
        self.menu = QtWidgets.QMenu(DISPLAY_NAME, self.main_window)
        self.menu.setObjectName("MBToolkit_MainMenu")
        pie = self.menu.addMenu("Pie Menus")
        self.menus["pie_menus"] = pie.menuAction()
        pie.aboutToShow.connect(lambda: self._populate_pie_menu(pie))
        self._action(self.menu, "Channel Blending...", lambda: self.show_feature("channel_blending"), "channel_blending")
        self._action(self.menu, "Font Tool...", lambda: self.show_feature("font_tool"), "font_tool")
        self.menu.addSeparator()
        self._action(self.menu, "Preferences...", self.open_preferences)
        self._action(self.menu, "About...", self.about)
        sp.ui.add_menu(self.menu)

    def _populate_pie_menu(self, pie):
        pie.clear()
        self._action(pie, "Manage Pie Menus...", self.open_pie_editor)
        pie.addSeparator()
        for menu in self.settings.data["pie_menus"]:
            self._action(pie, menu["name"] + "...",
                         lambda id=menu["id"]: self.features["pie_menus"].show_wheel(id))

    def reconcile_features(self):
        for fid, feature in self.features.items():
            enabled = self.settings.enabled(fid)
            if enabled and fid not in self.active:
                try:
                    feature.start()
                    self.active.add(fid)
                except Exception:
                    try:
                        feature.stop()
                    except Exception:
                        pass
                    raise
            if not enabled and fid in self.active:
                feature.stop()
                self.active.discard(fid)
        for fid, action in self.menus.items():
            action.setEnabled(self.settings.enabled(fid))

    def refresh_pie_shortcuts(self):
        if "pie_menus" in self.active:
            self.features["pie_menus"].rebuild_shortcuts()

    def show_feature(self, fid):
        if fid not in self.active:
            raise RuntimeError("Enable this feature in Preferences first")
        self.features[fid].show()

    def open_pie_editor(self):
        if "pie_menus" not in self.active:
            raise RuntimeError("Enable Pie Menu Creator in Preferences first")
        self.features["pie_menus"].editor()

    def open_preferences(self):
        if self.preferences is not None:
            self.preferences.raise_()
            self.preferences.activateWindow()
            return
        self.preferences = Preferences(self, self.main_window)
        self.preferences.finished.connect(lambda *_: setattr(self, "preferences", None))
        self.preferences.show()

    def about(self):
        QtWidgets.QMessageBox.information(self.main_window, "About MBToolkit",
            f"MBToolkit_3DPainter v{VERSION}\nMaintainer: {MAINTAINER}\n"
            "Modular open-source Substance 3D Painter toolkit.\n"
            "Font tool uses Fill Layers, not viewport brush stamps.")

    def stop(self):
        if self.preferences is not None:
            preferences = self.preferences
            self.preferences = None
            preferences.close()
            preferences.deleteLater()
        for fid in reversed(tuple(self.active)):
            try:
                self.features[fid].stop()
            except Exception:
                import traceback
                traceback.print_exc()
        self.active.clear()
        self.events.stop()
        if self.menu is not None:
            sp.ui.delete_ui_element(self.menu)
            self.menu = None
        self.menus.clear()
