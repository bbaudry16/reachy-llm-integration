import json
from pathlib import Path

POSES_FILE = Path(__file__).resolve().parent / "poses_library.json"

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if not POSES_FILE.exists():
        _cache = {"arms": [], "head": [], "antennas": []}
        return _cache
    try:
        content = POSES_FILE.read_text().strip()
        _cache = json.loads(content) if content else {"arms": [], "head": [], "antennas": []}
    except json.JSONDecodeError:
        _cache = {"arms": [], "head": [], "antennas": []}
    return _cache


def _find(section: str, label: str) -> dict | None:
    entries = _load().get(section, [])
    return next((e for e in entries if e.get("label") == label), None)


def getArmPose(label: str) -> dict | None:
    """
    Return right/left joint lists and optional min_duration for the given arm pose.

    @param label: Pose label.
    @type label: str
    @rtype: dict or None
    """
    entry = _find("arms", label)
    if entry is None:
        return None
    return {"right": entry.get("right_joints", []), "left": entry.get("left_joints", []), "min_duration": entry.get("min_duration", None)}


def getExplanationPose(label: str) -> dict | None:
    """
    Return the explanation pose data for the given label.

    @param label: Pose label.
    @type label: str
    @rtype: dict or None
    """
    entry = _find("arms", label)
    if entry is None or entry.get("category") != "explanation":
        return None
    return {"arm": entry.get("arm"), "joints": entry.get("joints", []), "role": entry.get("role", "")}


def getHeadPose(label: str) -> list | None:
    """
    Return the head angles for the given pose label.

    @param label: Pose label.
    @type label: str
    @rtype: list or None
    """
    entry = _find("head", label)
    if entry is None:
        return None
    return entry.get("angles")


def getAntennaPose(label: str) -> tuple[float, float] | None:
    """
    Return (left, right) antenna angles for the given pose label.

    @param label: Pose label.
    @type label: str
    @rtype: tuple or None
    """
    entry = _find("antennas", label)
    if entry is None:
        return None
    return (entry.get("left", 0.0), entry.get("right", 0.0))


def listByCategory(section: str, category: str) -> list[dict]:
    """
    Return all entries in a section matching the given category.

    @param section: Library section ('arms', 'head', 'antennas').
    @type section: str
    @param category: Category name.
    @type category: str
    @rtype: list
    """
    return [e for e in _load().get(section, []) if e.get("category") == category]


def reload() -> None:
    """Invalidate the cache and reload from disk."""
    global _cache
    _cache = None
    _load()