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
    """
    Return the animation dict for the given label, or None if not found.

    @param label: Animation label.
    @type label: str
    @rtype: dict or None
    """
    return next((a for a in _load().get("animations", []) if a.get("label") == label), None)


def getLockedParts(label: str) -> list[str]:
    """
    Return the list of body parts used by the given animation.

    @param label: Animation label.
    @type label: str
    @rtype: list
    """
    anim = getAnimation(label)
    if anim is None:
        return []
    return anim.get("parts", [])


def listByCategory(category: str) -> list[dict]:
    """
    Return all animations matching the given category.

    @param category: Category name (e.g. 'emotion', 'conversational').
    @type category: str
    @rtype: list
    """
    return [a for a in _load().get("animations", []) if a.get("category") == category]


def reload() -> None:
    """Invalidate the cache and reload from disk."""
    global _cache
    _cache = None
    _load()