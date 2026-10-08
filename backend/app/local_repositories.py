"""Process-local repository grants issued only after a native Desktop picker."""
from pathlib import Path
from threading import Lock

_lock = Lock()
_roots: set[str] = set()


def grant(path: str) -> str:
    from app.understanding.repository import ignored, linked
    candidate = Path(path).absolute()
    if any(linked(part) for part in (candidate, *candidate.parents)):
        raise ValueError("Linked paths are not permitted")
    root = candidate.resolve(strict=True)
    if not root.is_dir() or any(ignored(part) for part in root.parts[1:]):
        raise ValueError("Sensitive or invalid repository path")
    with _lock:
        _roots.add(str(root))
    return str(root)


def roots() -> list[str]:
    with _lock:
        return list(_roots)
