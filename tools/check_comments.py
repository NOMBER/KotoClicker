"""Checks that all developer comments in the project are in English (no Cyrillic).

What is checked:
  * *.py: COMMENT tokens (via tokenize), docstrings and bare string expressions used as comments;
  * *.bat: REM lines;
  * requirements*.txt: lines starting with "#".
User-visible Russian strings (the UI texts in i18n.py, the phrases in phrases.py, README) are
string literals or documentation and are deliberately NOT checked.
   python tools/check_comments.py [-v]
Exits with code 1 if anything is found."""
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CYR = re.compile(r"[\u0400-\u04FF]")
SKIP_DIRS = {".venv", "__pycache__", ".kvenv", "build", "dist"}


def _docstrings(src: str):
    """(line, text) of every docstring and bare string expression."""
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            yield node.lineno, node.value.value


def scan_py(path: Path):
    src = path.read_text(encoding="utf-8")
    hits = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT and CYR.search(tok.string):
            hits.append((tok.start[0], "comment", tok.string))
    for line, text in _docstrings(src):
        if CYR.search(text):
            hits.append((line, "docstring", text.strip().splitlines()[0]))
    return hits


def scan_text(path: Path, is_comment):
    hits = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if is_comment(line.strip()) and CYR.search(line):
            hits.append((n, "comment", line.strip()))
    return hits


def scan(root: Path = ROOT):
    """{relative path: [(line, kind, text), ...]} for files with Cyrillic in comments."""
    result = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or SKIP_DIRS.intersection(path.relative_to(root).parts):
            continue
        name = path.name.lower()
        if name.endswith(".py"):
            hits = scan_py(path)
        elif name.endswith(".bat"):
            hits = scan_text(path, lambda s: s.lower().startswith("rem ") or s.lower() == "rem" or s.startswith("::"))
        elif name.startswith("requirements") and name.endswith(".txt"):
            hits = scan_text(path, lambda s: s.startswith("#"))
        else:
            continue
        if hits:
            result[str(path.relative_to(root))] = hits
    return result


def main():
    result = scan()
    total = sum(len(h) for h in result.values())
    for rel, hits in result.items():
        print(f"{rel}: {len(hits)}")
        if "-v" in sys.argv:
            for line, kind, text in hits:
                print(f"   {line}: [{kind}] {text[:90]}")
    print("Cyrillic in comments/docstrings:", total)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
