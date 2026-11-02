"""Nice line breaks in the cat's bubble (and in hints).

Display only: the phrase bank is not changed. nbsp() inserts non-breaking spaces (U+00A0)
so that short words (prepositions, conjunctions, pronouns: Russian "v", "s", "i", "ya",
"na", "ne" (in Cyrillic)..., English "I", "a", "to", "of"...) never hang at the end of a line, a dash never
moves to the start of the next line, and the last word is never left alone on its line.
HTML tags (the link in the bot bubble, <b> in tips) are left untouched.
"""
from __future__ import annotations

import html
import re
import textwrap

NBSP = "\u00a0"

# words of 1-2 letters are always glued to the next word; these ones too
_GLUE_WORDS = {
    # Russian
    "без", "для", "над", "под", "при", "про", "из-за", "что", "как", "это", "мне", "она", "они", "его", "её",
    "ещё", "уже", "вот", "нам", "вам", "тот", "так", "или", "все", "всё", "где", "чем", "чтобы", "если",
    # English
    "the", "and", "for", "but", "not", "you", "are", "was", "has", "can", "our", "his", "her", "its", "who",
    "all", "any", "too", "with", "your", "from",
}
# max length of a glued chunk created to avoid an orphan last word
_MAX_TAIL = 20

_WORD_SPACE = re.compile(r"(?<![\w\-])([^\W_]+(?:-[^\W_]+)?)( +)(?=\S)")
_DASH = re.compile(r" +([—–])")
_NUMBER = re.compile(r"(?<![\w.,])(\d{1,4})( +)(?=[^\W\d_])")
_TAG = re.compile(r"(<[^>]+>)")


def _is_short(word: str) -> bool:
    return len(word) <= 2 or word.lower() in _GLUE_WORDS


def _glue_segment(seg: str) -> str:
    seg = _WORD_SPACE.sub(lambda m: m.group(1) + (NBSP if _is_short(m.group(1)) else m.group(2)), seg)
    seg = _NUMBER.sub(lambda m: m.group(1) + NBSP, seg)
    seg = _DASH.sub(lambda m: NBSP + m.group(1), seg)
    return seg


def _glue_tail(parts: list) -> None:
    """Glue the last two words (in the last text chunk) if the tail would be short."""
    for i in range(len(parts) - 1, -1, -1):
        seg = parts[i]
        if _TAG.fullmatch(seg) or not seg.strip():
            continue
        stripped = seg.rstrip()
        cut = stripped.rfind(" ")
        if cut <= 0:
            return
        # length of the future non-breaking chunk: everything from the previous normal space to the end
        prev = stripped.rfind(" ", 0, cut)
        chunk = stripped[prev + 1:]
        if len(chunk) <= _MAX_TAIL:
            parts[i] = stripped[:cut] + NBSP + stripped[cut + 1:] + seg[len(stripped):]
        return


def nbsp(text: str, tail: bool = True) -> str:
    """Insert non-breaking spaces for display. Calling it again does no harm."""
    if not text:
        return text
    parts = _TAG.split(text)
    parts = [p if _TAG.fullmatch(p) else _glue_segment(p) for p in parts]
    if tail:
        _glue_tail(parts)
    return "".join(parts)


def tooltip_html(text: str, width: int = 40) -> str:
    """Multi-line tooltip: explicit <br> so Windows does not show one long line."""
    lines = textwrap.wrap(nbsp(text, tail=False), width=width, break_long_words=False, break_on_hyphens=False)
    body = "<br>".join(html.escape(line, quote=False) for line in lines)
    return f"<p style='white-space:pre'>{body}</p>"
