"""KotoClick's "paws": auto-click, macro recording and replay.

All mouse and keyboard work goes through pynput. Each job runs in its own plain
thread (threading.Thread) that can be stopped at any moment via threading.Event.
Results are sent to the UI with Qt signals.
"""
import math
import threading
import time
from types import SimpleNamespace
from typing import Callable, Iterable, List, Optional

from PySide6.QtCore import QObject, Signal

from .hotkeys import key_to_name
from .i18n import tr
from .macro import (POSITIONAL, Macro, Step, compress_moves, release_dangling_buttons,
                    release_dangling_keys)


class BackendError(RuntimeError):
    pass


# ---- recording thresholds ----
# A press + release counts as one plain "click" step when it is shorter than this
# and the cursor moved less than CLICK_MAX_MOVE_PX between them. Anything longer or
# farther is a hold / drag and becomes mouse_down ... mouse_up.
CLICK_MAX_HOLD_S = 0.30
CLICK_MAX_MOVE_PX = 5
# Cursor path sampling: with "Record moves" on, and (sparser) while a button is held
# with "Record moves" off, so drag & drop still has a path.
MOVE_SAMPLE_S = 0.02
DRAG_SAMPLE_S = 0.05
# Wheel events closer than SCROLL_MERGE_GAP_S to the previous one, at (almost) the same
# spot and in the same direction, are summed into one scroll step (a step spans at most
# SCROLL_MERGE_SPAN_S so a long scroll keeps its rhythm).
SCROLL_MERGE_GAP_S = 0.08
SCROLL_MERGE_SPAN_S = 0.5
SCROLL_MERGE_PX = 5


def _pynput_mouse():
    try:
        from pynput import mouse
        return mouse
    except Exception as exc:  # noqa: BLE001
        raise BackendError(tr("err_mouse", err=exc)) from exc


def _pynput_keyboard():
    try:
        from pynput import keyboard
        return keyboard
    except Exception as exc:  # noqa: BLE001
        raise BackendError(tr("err_keyboard", err=exc)) from exc


def step_key_name(step: Step) -> str:
    """Short key name of a step, in the same form as hotkeys ('f6', 'a', 'esc')."""
    if step.key:
        return step.key
    return key_to_name(SimpleNamespace(char=step.char or None, vk=step.vk))


class PynputMouse:
    """Thin wrapper around pynput.mouse.Controller (replaced by a fake in tests)."""

    def __init__(self):
        self._mouse = _pynput_mouse()
        self._ctl = self._mouse.Controller()
        self._buttons = {
            "left": self._mouse.Button.left,
            "right": self._mouse.Button.right,
            "middle": self._mouse.Button.middle,
        }

    @property
    def position(self):
        x, y = self._ctl.position
        return int(x), int(y)

    def move_to(self, x, y):
        self._ctl.position = (int(x), int(y))

    def click(self, button="left", count=1):
        self._ctl.click(self._buttons[button], count)

    def press(self, button="left"):
        self._ctl.press(self._buttons[button])

    def release(self, button="left"):
        self._ctl.release(self._buttons[button])

    def scroll(self, dx=0, dy=0):
        self._ctl.scroll(int(dx), int(dy))


class PynputKeyboard:
    """Thin wrapper around pynput.keyboard.Controller (replaced by a fake in tests).
    Special keys are looked up by name (Key.ctrl_l), normal keys by virtual key code,
    and by character if there is no code."""

    def __init__(self):
        self._kb = _pynput_keyboard()
        self._ctl = self._kb.Controller()

    def resolve(self, step: Step):
        if step.key:
            key = getattr(self._kb.Key, step.key, None)
            if key is None:
                raise ValueError(f"Неизвестная клавиша: {step.key}")
            return key
        if step.vk is not None:
            return self._kb.KeyCode.from_vk(step.vk)
        return self._kb.KeyCode.from_char(step.char)

    def press(self, step: Step):
        self._ctl.press(self.resolve(step))

    def release(self, step: Step):
        self._ctl.release(self.resolve(step))


MouseFactory = Callable[[], object]


class Engine(QObject):
    """Runs one active job at a time: clicking, recording or replay."""

    clickerStopped = Signal()
    playerStopped = Signal()
    playerProgress = Signal(int, int)      # step number, loop number
    stepRecorded = Signal(object)          # Step
    error = Signal(str)

    def __init__(self, mouse_factory: MouseFactory = PynputMouse,
                 keyboard_factory: Callable[[], object] = PynputKeyboard, parent=None):
        super().__init__(parent)
        self._mouse_factory = mouse_factory
        self._keyboard_factory = keyboard_factory
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._listener = None
        self._key_listener = None
        self._rec_keys_held = set()
        self._rec_excluded = set()
        self._rec_lock = threading.Lock()
        self._rec_steps: List[Step] = []
        self._rec_last = 0.0
        self._rec_last_move = 0.0
        self._rec_moves = False
        self._rec_pending = None      # a press not yet known to be a click or a hold: (Step, time)
        self._rec_down = {}           # button -> (mouse_down Step, press time) of held buttons
        self._rec_scroll_t = 0.0      # time of the last wheel event
        self._rec_scroll_start = 0.0  # time of the first wheel event of the current scroll step
        self.clicks = 0          # click counter of the current session (read by a UI timer)
        self.total_clicks = 0    # total since the app started

    # ---------- common ----------
    def _wait_finished(self):
        """If the previous thread is just finishing, give it a second to finish."""
        t = self._thread
        if t is not None and t.is_alive() and self._stop.is_set():
            t.join(timeout=1.0)

    @property
    def busy(self) -> bool:
        return ((self._thread is not None and self._thread.is_alive())
                or self._listener is not None or self._key_listener is not None)

    def cursor_position(self):
        try:
            return self._mouse_factory().position
        except Exception:  # noqa: BLE001
            return None

    def stop_all(self):
        self._stop.set()
        if self.recording:
            self.stop_recording()
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=1.0)

    def _spawn(self, target, *args):
        self._stop.clear()
        self._thread = threading.Thread(target=target, args=args, name="kotoclick-worker", daemon=True)
        self._thread.start()

    def _count_click(self, n=1):
        self.clicks += n
        self.total_clicks += n

    # ---------- simple auto-click ----------
    def start_clicking(self, interval_s: float, button: str = "left", double: bool = False,
                       repeat: Optional[int] = None) -> bool:
        self._wait_finished()
        if self.busy:
            return False
        try:
            mouse = self._mouse_factory()
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
            return False
        self.clicks = 0
        self._spawn(self._click_loop, mouse, max(0.001, interval_s), button, double, repeat)
        return True

    def _click_loop(self, mouse, interval, button, double, repeat):
        next_time = time.perf_counter()
        done = 0
        try:
            while not self._stop.is_set():
                mouse.click(button, 2 if double else 1)   # click where the cursor is now
                self._count_click(1)
                done += 1
                if repeat is not None and done >= repeat:
                    break
                # Steady rhythm: wait until the "next beat", not just `interval`
                next_time += interval
                delay = next_time - time.perf_counter()
                if delay < 0:
                    next_time = time.perf_counter()
                    delay = 0
                if self._stop.wait(delay):
                    break
        except Exception as exc:  # noqa: BLE001
            self.error.emit(tr("err_click", err=exc))
        finally:
            self.clickerStopped.emit()

    # ---------- macro replay ----------
    def start_playback(self, macro: Macro, loops: Optional[int] = None,
                       skip_keys: Iterable[str] = ()) -> bool:
        """skip_keys: key names that must not be pressed on replay
        (KotoClick's own hotkeys, so a macro cannot switch itself off)."""
        self._wait_finished()
        if self.busy or not macro.steps:
            return False
        skip = {k for k in skip_keys if k}
        steps = [Step(**vars(s)) for s in macro.steps   # a copy: the table may be edited while playing
                 if not (s.kind == "key" and step_key_name(s) in skip)]
        if not steps:
            return False
        try:
            mouse = self._mouse_factory()
            keyboard = self._keyboard_factory() if any(s.kind == "key" for s in steps) else None
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
            return False
        self.clicks = 0
        self._spawn(self._play_loop, mouse, keyboard, steps, loops)
        return True

    def _play_loop(self, mouse, keyboard, steps, loops):
        loop = 0
        held = {}   # keys the macro is currently holding down
        held_buttons = set()   # mouse buttons the macro is currently holding down
        try:
            while not self._stop.is_set() and (loops is None or loop < loops):
                for i, step in enumerate(steps):
                    if step.delay_ms and self._stop.wait(step.delay_ms / 1000.0):
                        return
                    if self._stop.is_set():
                        return
                    if step.kind in POSITIONAL:
                        mouse.move_to(step.x, step.y)
                    if step.kind == "click":
                        mouse.click(step.button, 2 if step.double else 1)
                        self._count_click(1)
                    elif step.kind == "mouse_down":
                        mouse.press(step.button)
                        held_buttons.add(step.button)
                        self._count_click(1)        # a hold counts as one click (scroll does not count)
                    elif step.kind == "mouse_up":
                        mouse.release(step.button)
                        held_buttons.discard(step.button)
                    elif step.kind == "scroll":
                        mouse.scroll(step.dx, step.dy)
                    elif step.kind == "key":
                        if step.action == "press":
                            keyboard.press(step)
                            held[step.key_id()] = step
                        else:
                            keyboard.release(step)
                            held.pop(step.key_id(), None)
                    self.playerProgress.emit(i, loop)
                loop += 1
                # guard against an "empty" macro without pauses: do not burn 100% CPU
                if not any(s.delay_ms for s in steps) and self._stop.wait(0.01):
                    return
        except Exception as exc:  # noqa: BLE001
            self.error.emit(tr("err_play", err=exc))
        finally:
            # Stopped in the middle of a macro: release everything still held down
            for step in held.values():
                try:
                    keyboard.release(step)
                except Exception:  # noqa: BLE001
                    pass
            for button in sorted(held_buttons):
                try:
                    mouse.release(button)
                except Exception:  # noqa: BLE001
                    pass
            self.playerStopped.emit()

    # ---------- macro recording ----------
    @property
    def recording(self) -> bool:
        return self._listener is not None or self._key_listener is not None

    def start_recording(self, record_moves: bool = False, record_keys: bool = False,
                        excluded_keys: Iterable[str] = ()) -> bool:
        """record_keys: also record the keyboard (only while recording!).
        excluded_keys: KotoClick's hotkeys, never recorded."""
        if self.busy:
            return False
        try:
            mouse = _pynput_mouse()
            keyboard = _pynput_keyboard() if record_keys else None
            self._rec_steps = []
            self._rec_moves = record_moves
            self._rec_keys_held = set()
            self._rec_excluded = {k for k in excluded_keys if k}   # Esc only if it is assigned as the stop key
            self._rec_last = time.perf_counter()
            self._rec_last_move = 0.0
            self._rec_pending = None
            self._rec_down = {}
            self._rec_scroll_t = self._rec_scroll_start = 0.0
            self._listener = mouse.Listener(on_click=self._on_click, on_move=self._on_move,
                                            on_scroll=self._on_scroll)
            self._listener.daemon = True
            self._listener.start()
            if keyboard is not None:
                self._key_listener = keyboard.Listener(on_press=self._on_key_press,
                                                       on_release=self._on_key_release)
                self._key_listener.daemon = True
                self._key_listener.start()
            return True
        except Exception as exc:  # noqa: BLE001
            self._stop_listeners()
            self.error.emit(tr("err_record", err=exc))
            return False

    def _stop_listeners(self):
        for attr in ("_listener", "_key_listener"):
            lst = getattr(self, attr)
            setattr(self, attr, None)
            if lst is not None:
                try:
                    lst.stop()
                except Exception:  # noqa: BLE001
                    pass

    def stop_recording(self, drop_last_click_within: float = 0.0) -> List[Step]:
        """Stops recording and returns the steps.
        drop_last_click_within: if recording was stopped with the button in the window,
        the last click (on the "Stop" button itself) is dropped. The same goes for a press
        on that button that is still undecided, held, or just released as a short hold.
        Buttons and keys still held at the end get a release step, so nothing stays stuck."""
        self._stop_listeners()
        now = time.perf_counter()
        with self._rec_lock:
            steps = list(self._rec_steps)
            since_last = now - self._rec_last
            pending = self._rec_pending
            down = dict(self._rec_down)
            self._rec_pending = None
            self._rec_down = {}
        window = drop_last_click_within
        if pending is not None:
            step, t = pending
            if not (window and now - t < window):
                steps.append(step)      # a real press that is still held: keep it (mouse_up is added below)
        elif window and steps:
            self._drop_own_click(steps, down, now, since_last, window)
        return release_dangling_buttons(release_dangling_keys(compress_moves(steps)))

    @staticmethod
    def _drop_own_click(steps, down, now, since_last, window):
        """Removes the press on KotoClick's own "Stop" button from the end of `steps` (in place)."""
        # index of the last step that is not a cursor move
        j = len(steps) - 1
        while j >= 0 and steps[j].kind == "move":
            j -= 1
        if j < 0:
            return
        last = steps[j]
        if last.kind == "click" and j == len(steps) - 1 and since_last < window:
            steps.pop()
        elif last.kind == "mouse_down" and last.button in down and now - down[last.button][1] < window:
            del steps[j:]               # still held on the Stop button: drop the press and its path
        elif last.kind == "mouse_up" and since_last < window:
            k = j - 1
            while k >= 0 and steps[k].kind == "move":
                k -= 1
            if k >= 0 and steps[k].kind == "mouse_down" and steps[k].button == last.button:
                del steps[k:]           # a short hold on the Stop button

    def _elapsed_ms(self) -> int:
        now = time.perf_counter()
        ms = int(round((now - self._rec_last) * 1000))
        self._rec_last = now
        return ms

    # How mouse buttons are recorded:
    #   press   -> remembered as "pending" (its delay is measured right now, nothing is stored yet);
    #   release -> if it came quickly (< CLICK_MAX_HOLD_S) and near the press point
    #              (< CLICK_MAX_MOVE_PX), the pending press becomes one ordinary "click" step;
    #              otherwise mouse_down (at the press point and time) + mouse_up are stored.
    # A pending press is turned into mouse_down earlier, as soon as anything else must be
    # stored after it (the cursor moved far enough, the hold got long enough, a wheel turn,
    # a key, another button), so the order and the delays of all steps stay exactly as they happened.

    def _promote_pending(self) -> List[Step]:
        """Turns the pending press into a stored mouse_down (call with _rec_lock held)."""
        if self._rec_pending is None:
            return []
        step, t = self._rec_pending
        self._rec_pending = None
        self._rec_steps.append(step)
        self._rec_down[step.button] = (step, t)
        return [step]

    def _emit_all(self, steps):
        for step in steps:
            self.stepRecorded.emit(step)

    def _on_click(self, x, y, button, pressed):
        name = getattr(button, "name", "")
        if name not in ("left", "right", "middle"):
            return
        x, y = int(x), int(y)
        out: List[Step] = []
        with self._rec_lock:
            now = time.perf_counter()
            if pressed:
                if name in self._rec_down or (self._rec_pending and self._rec_pending[0].button == name):
                    return      # a duplicate press event of a button that is already down
                out += self._promote_pending()   # another button is pressed while one is held
                step = Step(kind="mouse_down", x=x, y=y, button=name, delay_ms=self._elapsed_ms())
                self._rec_pending = (step, now)
            else:
                pending = self._rec_pending
                if pending is not None and pending[0].button == name:
                    step, t = pending
                    self._rec_pending = None
                    if (now - t < CLICK_MAX_HOLD_S
                            and math.hypot(x - step.x, y - step.y) < CLICK_MAX_MOVE_PX):
                        click = Step(kind="click", x=step.x, y=step.y, button=name, delay_ms=step.delay_ms)
                        self._rec_steps.append(click)
                        out.append(click)
                    else:
                        self._rec_steps.append(step)
                        up = Step(kind="mouse_up", x=x, y=y, button=name, delay_ms=self._elapsed_ms())
                        self._rec_steps.append(up)
                        out += [step, up]
                elif name in self._rec_down:
                    out += self._promote_pending()
                    self._rec_down.pop(name)
                    up = Step(kind="mouse_up", x=x, y=y, button=name, delay_ms=self._elapsed_ms())
                    self._rec_steps.append(up)
                    out.append(up)
                # else: the button was pressed before recording started, nothing to release
        self._emit_all(out)

    def _on_move(self, x, y):
        x, y = int(x), int(y)
        out: List[Step] = []
        with self._rec_lock:
            now = time.perf_counter()
            if self._rec_pending is not None:
                step, t = self._rec_pending
                if (math.hypot(x - step.x, y - step.y) < CLICK_MAX_MOVE_PX
                        and now - t < CLICK_MAX_HOLD_S):
                    return      # tiny jitter during a normal click: not recorded
                out += self._promote_pending()   # it is a hold / drag after all
            dragging = bool(self._rec_down)
            if self._rec_moves or dragging:
                interval = MOVE_SAMPLE_S if self._rec_moves else DRAG_SAMPLE_S
                if now - self._rec_last_move >= interval:
                    self._rec_last_move = now
                    step = Step(kind="move", x=x, y=y, delay_ms=self._elapsed_ms())
                    self._rec_steps.append(step)
                    out.append(step)
        self._emit_all(out)

    def _on_scroll(self, x, y, dx, dy):
        x, y, dx, dy = int(x), int(y), int(dx), int(dy)
        if not (dx or dy):
            return
        out: List[Step] = []
        with self._rec_lock:
            now = time.perf_counter()
            out += self._promote_pending()
            last = self._rec_steps[-1] if self._rec_steps else None
            if (last is not None and last.kind == "scroll" and not out
                    and now - self._rec_scroll_t <= SCROLL_MERGE_GAP_S
                    and now - self._rec_scroll_start <= SCROLL_MERGE_SPAN_S
                    and abs(x - last.x) <= SCROLL_MERGE_PX and abs(y - last.y) <= SCROLL_MERGE_PX
                    and last.dx * dx >= 0 and last.dy * dy >= 0):
                # the same wheel movement goes on: add the notches to the previous step
                last.dx += dx
                last.dy += dy
                # _rec_last is left at the step's start, so the next delay also covers the
                # merged notches and the macro's total duration stays as recorded
                out.append(last)            # re-sent: the UI refreshes the row of the same object
            else:
                step = Step(kind="scroll", x=x, y=y, dx=dx, dy=dy, delay_ms=self._elapsed_ms())
                self._rec_steps.append(step)
                self._rec_scroll_start = now
                out.append(step)
            self._rec_scroll_t = now
        self._emit_all(out)

    def _key_step(self, key, action):
        """A key step from a pynput event (or None if this key must not be recorded)."""
        name = key_to_name(key)
        if not name or name in self._rec_excluded:
            return None
        special = getattr(key, "name", None)
        if special:
            return Step(kind="key", action=action, key=special)
        char = getattr(key, "char", None) or ""
        if not (char.isprintable() and char.strip()):
            char = ""   # with Ctrl held, Windows sends control characters: store only the code
        vk = getattr(key, "vk", None)
        if not char and vk is None:
            return None
        return Step(kind="key", action=action, char=char, vk=vk)

    def _on_key_press(self, key):
        step = self._key_step(key, "press")
        if step is None:
            return
        with self._rec_lock:
            kid = step.key_id()
            if kid in self._rec_keys_held:
                return   # auto-repeat of a held key (or a duplicate event): one press
            self._rec_keys_held.add(kid)
            out = self._promote_pending()   # a key during a mouse press: the press is a hold
            step.delay_ms = self._elapsed_ms()
            self._rec_steps.append(step)
        self._emit_all(out + [step])

    def _on_key_release(self, key):
        step = self._key_step(key, "release")
        if step is None:
            return
        with self._rec_lock:
            kid = step.key_id()
            if kid not in self._rec_keys_held:
                return   # the press happened before recording started: no release needed
            self._rec_keys_held.discard(kid)
            # The character on release may differ (Shift released first): take it from the press
            for prev in reversed(self._rec_steps):
                if prev.kind == "key" and prev.action == "press" and prev.key_id() == kid:
                    step.char = prev.char
                    break
            out = self._promote_pending()
            step.delay_ms = self._elapsed_ms()
            self._rec_steps.append(step)
        self._emit_all(out + [step])
