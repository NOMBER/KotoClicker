"""
Scheduler for the "cat shows off its Telegram bot" bubble.

Timing logic only: about every half hour (random 25-35 minutes), never right after start,
and never while clicking/recording/playing; then the bubble waits until the cat is free.
It opens nothing by itself: the link opens in the browser only if the user clicks it.
"""
from __future__ import annotations

import random

PROMO_URL = "https://t.me/DownGrabBot?start=KotoClick"
MIN_INTERVAL = 25 * 60
MAX_INTERVAL = 35 * 60
BUSY_RETRY = 60          # if busy, try again a minute after the cat is free
SHOW_SECONDS = 15


class PromoScheduler:
    def __init__(self, now: float, rng: random.Random | None = None,
                 min_interval=MIN_INTERVAL, max_interval=MAX_INTERVAL):
        self.rng = rng or random.Random()
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.due = now + self._interval()
        self.shown = 0

    def _interval(self) -> float:
        return self.rng.uniform(self.min_interval, self.max_interval)

    def check(self, now: float, busy: bool) -> bool:
        """Call periodically. True means: show the bubble right now."""
        if now < self.due:
            return False
        if busy:
            # postpone: show no earlier than BUSY_RETRY after the cat becomes free
            self.due = now + BUSY_RETRY
            return False
        self.due = now + self._interval()
        self.shown += 1
        return True

    def postpone(self, now: float):
        """The bubble was just shown out of turn: the next scheduled one comes no earlier than in 25-35 minutes."""
        self.due = max(self.due, now + self._interval())


# --- easter egg: 10 quick clicks on the cat and it tells about the bot itself ---
EGG_CLICKS = 10          # clicks in a row
EGG_GAP = 2.0            # gap between clicks under 2 s, otherwise the count restarts
EGG_COOLDOWN = 10 * 60   # at most once per 10 minutes


class EasterEgg:
    def __init__(self, clicks=EGG_CLICKS, gap=EGG_GAP, cooldown=EGG_COOLDOWN):
        self.clicks, self.gap, self.cooldown = clicks, gap, cooldown
        self.count = 0
        self.last_click = None
        self.last_shown = None

    def click(self, now: float) -> bool:
        """The cat was clicked. True means show the bubble (10 clicks in a row and 10 minutes passed)."""
        if self.last_click is None or now - self.last_click > self.gap:
            self.count = 0
        self.last_click = now
        self.count += 1
        if self.count < self.clicks:
            return False
        self.count = 0
        if self.last_shown is not None and now - self.last_shown < self.cooldown:
            return False          # shown recently: the cat just purrs
        self.last_shown = now
        return True
