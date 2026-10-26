"""A single painter event subscription; listeners use Qt-friendly delayed updates."""
import substance_painter as sp


class EventBus:
    def __init__(self):
        self.listeners = set()
        self.connected = []
        self.project_epoch = 0

    def start(self):
        connected_classes = {cls for cls, _callback in self.connected}
        for event_name in ("LayerStacksModelDataChanged", "ProjectEditionEntered", "ProjectEditionLeft",
                           "ProjectOpened", "ProjectCreated", "ProjectClosed"):
            event_cls = getattr(sp.event, event_name, None)
            if event_cls and event_cls not in connected_classes:
                callback = self._notify
                sp.event.DISPATCHER.connect(event_cls, callback)
                self.connected.append((event_cls, callback))
                connected_classes.add(event_cls)

    def add(self, callback):
        self.listeners.add(callback)

    def remove(self, callback):
        self.listeners.discard(callback)

    def _notify(self, _event):
        if type(_event).__name__ in ("ProjectOpened", "ProjectCreated", "ProjectClosed"):
            self.project_epoch += 1
        for callback in tuple(self.listeners):
            try:
                callback()
            except Exception:
                import traceback
                traceback.print_exc()

    def stop(self):
        failed = []
        for cls, callback in reversed(self.connected):
            try:
                sp.event.DISPATCHER.disconnect(cls, callback)
            except Exception:
                import traceback
                traceback.print_exc()
                failed.append((cls, callback))
        self.connected = list(reversed(failed))
        self.listeners.clear()
