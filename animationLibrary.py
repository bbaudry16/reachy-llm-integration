import json
from pathlib import Path

ANIMATIONS_FILE = Path(__file__).resolve().parent / "animations_library.json"

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if not ANIMATIONS_FILE.exists():
        _cache = {"animations": []}
        return _cache
    try:
        content = ANIMATIONS_FILE.read_text().strip()
        _cache = json.loads(content) if content else {"animations": []}
    except json.JSONDecodeError:
        _cache = {"animations": []}
    return _cache


def getAnimation(label: str) -> dict | None:
    return next((a for a in _load().get("animations", []) if a.get("label") == label), None)


def getLockedParts(label: str) -> list[str]:
    anim = getAnimation(label)
    if anim is None:
        return []
    return anim.get("parts", [])


def listByCategory(category: str) -> list[dict]:
    return [a for a in _load().get("animations", []) if a.get("category") == category]


def reload() -> None:
    global _cache
    _cache = None
    _load()