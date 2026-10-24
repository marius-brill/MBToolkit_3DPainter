"""Declarative, bounded macros. No source code or expressions are evaluated."""
from .models import SAFE_NAME
from contextlib import nullcontext


OPERATIONS = {
    "painter.add_fill": "Create Fill Layer",
    "painter.add_paint": "Create Paint Layer",
    "painter.add_group": "Create Folder",
    "painter.black_mask": "Add Black Mask to Target",
    "painter.white_mask": "Add White Mask to Target",
    "painter.mask_fill": "Add Fill to Target Mask",
}
MAX_STEPS = 64


def validate_macro(macro):
    if not isinstance(macro, dict) or not isinstance(macro.get("id"), str) or not SAFE_NAME.fullmatch(macro["id"]):
        raise ValueError("Invalid macro identifier")
    if not isinstance(macro.get("name"), str) or not macro["name"].strip():
        raise ValueError("Give the macro a name")
    steps = macro.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError(f"Macros need between 1 and {MAX_STEPS} steps")
    if any(not isinstance(step, str) or step not in OPERATIONS for step in steps):
        raise ValueError("Macro contains an unsupported operation")
    return macro


class MacroRunner:
    def __init__(self, operations, initial_target, modification=None, completed=None):
        self.operations = operations
        self.initial_target = initial_target
        self.running = False
        self.modification = modification or (lambda name: nullcontext())
        self.completed = completed or (lambda target: None)

    def run(self, macro):
        validate_macro(macro)
        if self.running:
            raise RuntimeError("A macro is already running")
        self.running = True
        try:
            with self.modification("MBToolkit: " + macro["name"]):
                target = self._execute(macro)
            self.completed(target)
            return target
        finally:
            self.running = False

    def _execute(self, macro):
        target = None
        for index, step in enumerate(macro["steps"], 1):
            try:
                if step in ("painter.add_fill", "painter.add_paint", "painter.add_group"):
                    target = self.operations[step](target)
                else:
                    if target is None:
                        target = self.initial_target()
                    # Effects must not replace the owning layer as the next step's target.
                    self.operations[step](target)
            except Exception as exc:
                raise RuntimeError(
                    f"{macro['name']}: step {index} ({OPERATIONS[step]}) failed: {exc}. "
                    "Later steps were not run; earlier changes may remain. Use Painter Undo if needed."
                ) from exc
        return target