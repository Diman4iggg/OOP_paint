from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class SnapshotCommand:
    label: str
    before_state: dict
    after_state: dict

    def undo(self, restore: Callable[[dict], None]) -> None:
        restore(self.before_state)

    def redo(self, restore: Callable[[dict], None]) -> None:
        restore(self.after_state)


class HistoryManager:
    def __init__(self):
        self.undo_stack: list[SnapshotCommand] = []
        self.redo_stack: list[SnapshotCommand] = []

    def push(self, command: SnapshotCommand) -> None:
        self.undo_stack.append(command)
        self.redo_stack.clear()

    def undo(self, restore: Callable[[dict], None]) -> None:
        if not self.undo_stack:
            return
        command = self.undo_stack.pop()
        command.undo(restore)
        self.redo_stack.append(command)

    def redo(self, restore: Callable[[dict], None]) -> None:
        if not self.redo_stack:
            return
        command = self.redo_stack.pop()
        command.redo(restore)
        self.undo_stack.append(command)

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
