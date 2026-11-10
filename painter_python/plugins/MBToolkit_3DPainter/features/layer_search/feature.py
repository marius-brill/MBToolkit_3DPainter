"""Optional native-panel integration; unsupported layouts are left untouched."""


class Feature:
    def __init__(self, app):
        self.app = app
        self.controller = None

    def start(self):
        from .native import LayerSearch
        self.controller = LayerSearch(self.app.main_window)
        self.controller.start()

    def stop(self):
        if self.controller is not None:
            self.controller.stop()
            self.controller.deleteLater()
            self.controller = None