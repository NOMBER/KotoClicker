"""
Macro library: each macro is a separate JSON file in the macros/ folder
(next to the app, see paths.library_dir). File name = macro name in the list.
"""
import json
import os
import re
from pathlib import Path
from typing import List, Optional

from .macro import Macro

_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_NAME = 60


def safe_name(name: str, fallback: str = "Макрос") -> str:
    """A name that can be used as a file name on Windows."""
    name = _BAD_CHARS.sub("_", " ".join(str(name).split()))
    name = name.strip(" .")[:MAX_NAME].strip(" .")
    if not name or name.upper() in _RESERVED:
        name = fallback
    return name


class MacroLibrary:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    # --- listing ---
    def names(self) -> List[str]:
        files = [p for p in self.folder.glob("*.json") if p.is_file()]
        return sorted((p.stem for p in files), key=str.casefold)

    def path(self, name: str) -> Path:
        return self.folder / f"{name}.json"

    def exists(self, name: str) -> bool:
        return self.path(name).is_file()

    def unique_name(self, name: str, ignore: Optional[str] = None) -> str:
        base = safe_name(name)
        taken = {n.casefold() for n in self.names() if n != ignore}
        if base.casefold() not in taken:
            return base
        i = 2
        while f"{base} ({i})".casefold() in taken:
            i += 1
        return f"{base} ({i})"

    # --- files ---
    def load(self, name: str) -> Macro:
        macro = Macro.load(self.path(name))
        macro.name = name
        return macro

    def save(self, name: str, macro: Macro) -> None:
        """Atomic write: write to a temporary file first, then replace."""
        macro.name = name
        target = self.path(name)
        tmp = target.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(macro.to_dict(), fh, ensure_ascii=False, indent=2)
        os.replace(tmp, target)

    def create(self, name: str, macro: Optional[Macro] = None) -> str:
        name = self.unique_name(name)
        self.save(name, macro if macro is not None else Macro(name=name))
        return name

    def rename(self, old: str, new: str) -> str:
        new = self.unique_name(new, ignore=old)
        if new == old:
            return old
        src, dst = self.path(old), self.path(new)
        if new.casefold() == old.casefold():       # case change only: Windows does not distinguish case
            tmp = self.folder / f".{old}.renaming"
            os.replace(src, tmp)
            src = tmp
        os.replace(src, dst)
        try:   # update the name stored inside the file too
            m = Macro.load(dst)
            self.save(new, m)
        except (OSError, ValueError, TypeError, KeyError):
            pass
        return new

    def delete(self, name: str) -> None:
        self.path(name).unlink(missing_ok=True)

    def duplicate(self, name: str, new_name: str) -> str:
        macro = self.load(name)
        return self.create(new_name, Macro(name=new_name, steps=list(macro.steps)))

    def import_file(self, src) -> str:
        """Copy a foreign macro file into the library (after checking that it is valid)."""
        macro = Macro.load(src)
        return self.create(macro.name if macro.name and macro.name != "Макрос" else Path(src).stem, macro)

    # --- migration of old macros (pre-library version) ---
    def migrate(self, autosave: Path, old_dirs=(), autosave_name: str = "Макрос") -> List[str]:
        """Old autosave_macro.json -> a macro in the library (the file itself is renamed to .bak),
        files from old folders are copied (originals stay in place)."""
        added = []
        autosave = Path(autosave)
        if autosave.is_file():
            try:
                macro = Macro.load(autosave)
                if macro.steps:
                    name = macro.name if macro.name and macro.name != "Макрос" else autosave_name
                    added.append(self.create(name, macro))
                os.replace(autosave, autosave.with_suffix(".json.bak"))
            except (OSError, ValueError, TypeError, KeyError):
                pass
        for d in old_dirs:
            d = Path(d)
            if not d.is_dir() or d.resolve() == self.folder.resolve():
                continue
            for f in sorted(d.glob("*.json")):
                try:
                    macro = Macro.load(f)
                except (OSError, ValueError, TypeError, KeyError):
                    continue
                if self.exists(safe_name(f.stem)):
                    continue
                name = self.unique_name(f.stem)
                self.save(name, macro)
                added.append(name)
        return added
