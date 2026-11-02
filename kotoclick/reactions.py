"""
The cat's reactions to click rate: pure logic without Qt (easy to test).

Once per frame (~30 times a second) the window passes the engine's total click counter here.
No "per click" signals: even with a 1 ms interval the UI only gets the counter
difference between frames.

Cat moods:
  calm    - calm (clicking slowly or idle)
  lively  - perked up (>= LIVELY_CPS clicks per second)
  hyper   - paws are a blur (>= HYPER_CPS)
  disco   - "vibe disco": >= DISCO_CPS clicks per second for longer than DISCO_AFTER seconds.
            Ends when the rate stays below DISCO_EXIT_CPS for longer than DISCO_COOLDOWN seconds
            (hysteresis, so the disco does not flicker).
"""
import math
from collections import deque

LIVELY_CPS = 4.0
HYPER_CPS = 9.0
DISCO_CPS = 15.0
DISCO_AFTER = 5.0
DISCO_EXIT_CPS = 10.0
DISCO_COOLDOWN = 1.5
RATE_WINDOW = 1.0           # window (seconds) over which the rate is measured
FADE_IN = 1.0               # seconds for the disco to fade in
FADE_OUT = 1.6              # seconds to fade out
MOOD_SLACK = 1.5            # clicks/s: hysteresis between calm / lively / hyper


class ClickRate:
    """Sliding estimate of "clicks per second" from samples of the total counter."""

    def __init__(self, window: float = RATE_WINDOW):
        self.window = window
        self._samples = deque()      # (time, counter)
        self.cps = 0.0

    def reset(self):
        self._samples.clear()
        self.cps = 0.0

    def feed(self, total: int, now: float) -> int:
        """Add a sample. Returns how many new clicks happened since the previous sample."""
        new = 0
        if self._samples:
            new = max(0, total - self._samples[-1][1])
            if total < self._samples[-1][1]:       # the counter was reset: start over
                self._samples.clear()
        self._samples.append((now, total))
        while len(self._samples) > 2 and now - self._samples[1][0] >= self.window:
            self._samples.popleft()
        t0, c0 = self._samples[0]
        span = now - t0
        self.cps = (total - c0) / span if span >= 0.2 else 0.0
        return new


class Mood:
    """Mood state machine + smooth disco "volume" (0..1)."""

    def __init__(self, disco_cps=DISCO_CPS, disco_after=DISCO_AFTER,
                 exit_cps=DISCO_EXIT_CPS, cooldown=DISCO_COOLDOWN):
        self.disco_cps = disco_cps
        self.disco_after = disco_after
        self.exit_cps = exit_cps
        self.cooldown = cooldown
        self.reset()

    def reset(self):
        self.state = "calm"
        self.disco = False
        self.intensity = 0.0
        self._fast_since = None
        self._slow_since = None
        self._last = None

    def update(self, cps: float, now: float, disco_allowed: bool = True) -> str:
        dt = 0.0 if self._last is None else max(0.0, min(0.5, now - self._last))
        self._last = now

        if not self.disco:
            if cps >= self.disco_cps and disco_allowed:
                if self._fast_since is None:
                    self._fast_since = now
                if now - self._fast_since >= self.disco_after:
                    self.disco = True
                    self._slow_since = None
            else:
                self._fast_since = None
        else:
            if not disco_allowed:
                self.disco = False
            elif cps < self.exit_cps:
                if self._slow_since is None:
                    self._slow_since = now
                if now - self._slow_since >= self.cooldown:
                    self.disco = False
            else:
                self._slow_since = None
            if not self.disco:
                self._fast_since = None

        if self.disco:
            self.intensity = min(1.0, self.intensity + dt / FADE_IN)
            self.state = "disco"
        else:
            self.intensity = max(0.0, self.intensity - dt / FADE_OUT)
            # a little slack so the status does not flicker at the thresholds
            hyper_at = HYPER_CPS - MOOD_SLACK if self.state in ("hyper", "disco") else HYPER_CPS
            lively_at = LIVELY_CPS - MOOD_SLACK if self.state != "calm" else LIVELY_CPS
            if cps >= hyper_at:
                self.state = "hyper"
            elif cps >= lively_at:
                self.state = "lively"
            else:
                self.state = "calm"
        return self.state


class HatWiggle:
    """Swing of the "hat" (headset): each click adds energy,
    which decays smoothly while the hat swings at a constant frequency.
    So a single click gives a visible "nod", and fast clicks a steady shake without jerks."""

    FREQ = 5.5          # swings per second
    DECAY = 0.22        # seconds for the energy to fall by a factor of e
    KICK = 0.75         # energy added per click

    def __init__(self):
        self.energy = 0.0
        self.phase = 0.0

    def kick(self, clicks: int = 1):
        if clicks <= 0:
            return
        if self.energy < 0.05:
            self.phase = 0.0          # from rest: start the "nod" right away
        self.energy = min(1.0, self.energy + self.KICK * min(clicks, 3))

    def step(self, dt: float):
        self.phase = (self.phase + dt * self.FREQ) % 1.0
        self.energy *= math.exp(-dt / self.DECAY)
        if self.energy < 0.003:
            self.energy = 0.0

    def pose(self):
        """(angle in degrees, hop 0..1) for the current frame."""
        s = math.sin(self.phase * 2 * math.pi)
        return 6.0 * self.energy * s, self.energy * abs(s)
