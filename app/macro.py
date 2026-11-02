"""A macro is a list of steps recorded by the secretary mouse.

Each step means "wait delay_ms, then do the action".
  click - click with `button` at (x, y)
  move  - just move the cursor to (x, y)
  wait  - pause only
  key   - press (action="press") or release (action="release") a key.
          Special keys (Ctrl, Enter, F5...) are stored by name in `key`,
          normal keys by virtual key code `vk` and character `char`.
  mouse_down - press and hold `button` at (x, y) (start of a hold or a drag & drop)
  mouse_up   - release `button` at (x, y)
  scroll     - turn the mouse wheel at (x, y): `dy` notches vertically (positive = up),
               `dx` notches horizontally (positive = right), the same signs as pynput.

File format versions: 1 and 2 had only click / move / wait / key steps,
version 3 adds mouse_down / mouse_up / scroll. Old files (v1, v2) load unchanged.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .i18n import tr

FORMAT_VERSION = 3
KINDS = ("click", "move", "wait", "key", "mouse_down", "mouse_up", "scroll")
# step kinds that have a screen position (x, y)
POSITIONAL = ("click", "move", "mouse_down", "mouse_up", "scroll")
# step kinds that use a mouse button
BUTTON_KINDS = ("click", "mouse_down", "mouse_up")
BUTTONS = ("left", "right", "middle")
KEY_ACTIONS = ("press", "release")


@dataclass
class Step:
    kind: str = "click"
    x: int = 0
    y: int = 0
    button: str = "left"
    delay_ms: int = 0
    double: bool = False
    # for key steps
    action: str = "press"
    key: str = ""               # special key name: "ctrl_l", "enter", "f5", "up"...
    char: str = ""              # character of a normal key ("a", "1", or a Cyrillic letter)
    vk: Optional[int] = None    # virtual key code (more reliable than the character: layout independent)
    # for scroll steps: wheel notches (positive dy = up, positive dx = right)
    dx: int = 0
    dy: int = 0

    def key_id(self):
        """What tells one key from another (to match press/release pairs)."""
        if self.key:
            return ("k", self.key)
        if self.vk is not None:
            return ("v", self.vk)
        return ("c", self.char.lower())

    def key_label(self) -> str:
        from .hotkeys import pretty_key, vk_name
        if self.key:
            return pretty_key(self.key)
        if self.char and self.char.isprintable() and self.char.strip():
            return self.char.upper() if len(self.char) == 1 else self.char
        if self.vk is not None:
            return pretty_key(vk_name(self.vk))
        return "?"

    def describe(self) -> str:
        """Step description for the table (in the current language)."""
        if self.kind == "click":
            b = tr("bn_" + self.button)
            return tr("step_dclick" if self.double else "step_click", button=b)
        if self.kind == "move":
            return tr("step_move")
        if self.kind == "key":
            return tr("step_key_" + self.action, key=self.key_label())
        if self.kind in ("mouse_down", "mouse_up"):
            return tr("step_" + self.kind, button=tr("bn_acc_" + self.button))
        if self.kind == "scroll":
            return describe_scroll(self.dx, self.dy)
        return tr("step_wait")

    def to_dict(self) -> dict:
        d = {"kind": self.kind, "delay_ms": int(self.delay_ms)}
        if self.kind in POSITIONAL:
            d.update(x=int(self.x), y=int(self.y))
        if self.kind == "click":
            d.update(button=self.button, double=bool(self.double))
        if self.kind in ("mouse_down", "mouse_up"):
            d["button"] = self.button
        if self.kind == "scroll":
            d.update(dx=int(self.dx), dy=int(self.dy))
        if self.kind == "key":
            d["action"] = self.action
            if self.key:
                d["key"] = self.key
            else:
                if self.char:
                    d["char"] = self.char
                if self.vk is not None:
                    d["vk"] = int(self.vk)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Step":
        if not isinstance(d, dict):
            raise ValueError("Шаг макроса должен быть объектом")
        kind = d.get("kind", "click")
        if kind not in KINDS:
            raise ValueError(f"Неизвестный тип шага: {kind!r}")
        button = d.get("button", "left")
        if button not in BUTTONS:
            raise ValueError(f"Неизвестная кнопка: {button!r}")
        step = cls(
            kind=kind,
            x=int(d.get("x", 0)),
            y=int(d.get("y", 0)),
            button=button,
            delay_ms=max(0, int(d.get("delay_ms", 0))),
            double=bool(d.get("double", False)),
        )
        if kind == "scroll":
            step.dx = int(d.get("dx", 0))
            step.dy = int(d.get("dy", 0))
        if kind == "key":
            action = d.get("action", "press")
            if action not in KEY_ACTIONS:
                raise ValueError(f"Неизвестное действие клавиши: {action!r}")
            step.action = action
            step.key = str(d.get("key", ""))[:32]
            step.char = str(d.get("char", ""))[:4]
            vk = d.get("vk")
            step.vk = int(vk) if vk is not None else None
            if not (step.key or step.char or step.vk is not None):
                raise ValueError("У шага-клавиши не указана клавиша")
        return step


@dataclass
class Macro:
    name: str = "Макрос"
    steps: List[Step] = field(default_factory=list)

    @property
    def click_count(self) -> int:
        """Clicks in the macro: a hold (mouse_down ... mouse_up) counts as one click, scrolling does not count."""
        return sum(1 for s in self.steps if s.kind in ("click", "mouse_down"))

    @property
    def key_count(self) -> int:
        return sum(1 for s in self.steps if s.kind == "key" and s.action == "press")

    @property
    def duration_ms(self) -> int:
        return sum(s.delay_ms for s in self.steps)

    def to_dict(self) -> dict:
        return {
            "app": "KotoClick",
            "version": FORMAT_VERSION,
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Macro":
        if not isinstance(d, dict) or not isinstance(d.get("steps"), list):
            raise ValueError("Это не файл макроса Котоклика")
        return cls(name=str(d.get("name", "Макрос")), steps=[Step.from_dict(s) for s in d["steps"]])

    def save(self, path) -> None:
        path = Path(path)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path) -> "Macro":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))


def compress_moves(steps: List[Step], min_distance: int = 3) -> List[Step]:
    """Drops nearly identical consecutive moves, adding up their delays,
    so a recording does not grow to thousands of steps."""
    out: List[Step] = []
    for s in steps:
        prev = out[-1] if out else None
        if (s.kind == "move" and prev is not None and prev.kind == "move"
                and abs(prev.x - s.x) < min_distance and abs(prev.y - s.y) < min_distance):
            prev.x, prev.y = s.x, s.y
            prev.delay_ms += s.delay_ms
            continue
        out.append(Step(**vars(s)))
    return out


def release_dangling_keys(steps: List[Step]) -> List[Step]:
    """If a key was pressed but not released before the recording ended, add a "release"
    so nothing stays held down on replay."""
    held = {}
    for s in steps:
        if s.kind != "key":
            continue
        if s.action == "press":
            held[s.key_id()] = s
        else:
            held.pop(s.key_id(), None)
    out = list(steps)
    for s in held.values():
        out.append(Step(kind="key", action="release", key=s.key, char=s.char, vk=s.vk, delay_ms=0))
    return out


def release_dangling_buttons(steps: List[Step]) -> List[Step]:
    """If a mouse button was pressed (mouse_down) but not released before the recording ended,
    add a mouse_up at the last known cursor position so the button never stays stuck on replay."""
    held = {}
    pos = None
    for s in steps:
        if s.kind in POSITIONAL:
            pos = (s.x, s.y)
        if s.kind == "mouse_down":
            held[s.button] = s
        elif s.kind == "mouse_up":
            held.pop(s.button, None)
    out = list(steps)
    for button, s in held.items():
        x, y = pos if pos is not None else (s.x, s.y)
        out.append(Step(kind="mouse_up", x=x, y=y, button=button, delay_ms=0))
    return out


def describe_scroll(dx: int, dy: int) -> str:
    """Table text of a scroll step: "Scroll up x3", "Scroll down x2, right x1"."""
    parts = []
    if dy:
        parts.append(tr("dir_up" if dy > 0 else "dir_down", n=abs(dy)))
    if dx:
        parts.append(tr("dir_right" if dx > 0 else "dir_left", n=abs(dx)))
    if not parts:
        return tr("step_scroll_none")
    return tr("step_scroll", dirs=", ".join(parts))
