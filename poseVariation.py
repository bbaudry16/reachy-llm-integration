"""
poseVariation.py
────────────────
Adds subtle randomness to static arm poses so Reachy never holds
the exact same position twice.

HOW IT WORKS
  1. Compare every joint of the target pose against the neutral reference.
  2. Find the joint with the largest absolute delta (= the "expressive" joint).
  3. Apply a random offset ∈ [-MAX_VARIATION_DEG, +MAX_VARIATION_DEG] to that
     joint, clamped so the result stays inside JOINT_LIMITS.
  4. Only joints listed in VARIABLE_JOINTS are candidates for variation;
     joints absent from that list are never touched.

CONFIGURATION (edit freely)
  MAX_VARIATION_DEG  – maximum random offset in degrees (global ceiling)
  VARIABLE_JOINTS    – which joint indices may receive variation
                       (index = position in the 8-value JOINT_ORDER list)
  JOINT_LIMITS       – hard safety limits per joint index [min, max]
"""

import random
from typing import Optional

import poseLibrary


# ── Configuration ─────────────────────────────────────────────────────────────

# Maximum random offset applied to the chosen joint (degrees).
# The actual offset is drawn uniformly from [-MAX, +MAX].
MAX_VARIATION_DEG: float = 20.0

# Maximum random offset applied to each antenna angle (degrees).
# Applied independently to left and right antennas.
MAX_ANTENNA_VARIATION_DEG: float = 8.0

# Joint indices (0-based, matching JOINT_ORDER) that are allowed to vary.
# JOINT_ORDER = [shoulder_pitch, shoulder_roll, arm_yaw, elbow_pitch,
#                forearm_yaw, wrist_pitch, wrist_roll, gripper]
#
# Defaults: shoulder_pitch(0), shoulder_roll(1), arm_yaw(2), elbow_pitch(3)
# Wrist/gripper joints are excluded — they are too close to mechanical limits.
VARIABLE_JOINTS: list[int] = [0, 1, 2, 3]

# Safety clamp per joint index [min_deg, max_deg].
# None means no clamp for that joint.
JOINT_LIMITS: dict[int, tuple[float, float]] = {
    0: (-130.0,  50.0),   # shoulder_pitch
    1: ( -80.0,  80.0),   # shoulder_roll
    2: ( -90.0,  90.0),   # arm_yaw
    3: (-130.0,   0.0),   # elbow_pitch
    4: ( -90.0,  90.0),   # forearm_yaw
    5: ( -50.0,  50.0),   # wrist_pitch
    6: ( -60.0,  60.0),   # wrist_roll
    7: ( -70.0,  70.0),   # gripper
}


# ── Internal helpers ──────────────────────────────────────────────────────────

_neutral_cache: Optional[dict] = None   # {"right": [...], "left": [...]}


def _getNeutral() -> dict:
    """Return the neutral arm pose, cached after first load."""
    global _neutral_cache
    if _neutral_cache is not None:
        return _neutral_cache
    data = poseLibrary.getArmPose("neutral")
    if data is None:
        _neutral_cache = {"right": [0.0] * 8, "left": [0.0] * 8}
    else:
        _neutral_cache = {"right": list(data["right"]), "left": list(data["left"])}
    return _neutral_cache


def _pickVariableJoint(joints: list[float], neutral: list[float]) -> int:
    """
    Among VARIABLE_JOINTS, return the index with the largest |delta|
    vs the neutral reference. Falls back to VARIABLE_JOINTS[0] if joints
    is shorter than expected.
    """
    best_idx = VARIABLE_JOINTS[0]
    best_delta = -1.0
    for idx in VARIABLE_JOINTS:
        if idx >= len(joints) or idx >= len(neutral):
            continue
        delta = abs(joints[idx] - neutral[idx])
        if delta > best_delta:
            best_delta = delta
            best_idx = idx
    return best_idx


def _clamp(value: float, idx: int) -> float:
    limits = JOINT_LIMITS.get(idx)
    if limits is None:
        return value
    lo, hi = limits
    return max(lo, min(hi, value))


# ── Public API ────────────────────────────────────────────────────────────────

def applyVariation(joints: list[float], side: str) -> list[float]:
    """
    Return a copy of `joints` with a random offset on the most expressive joint.

    Parameters
    ----------
    joints : list[float]
        The 8 joint values for one arm (right or left).
    side : str
        "right" or "left" — selects the correct neutral reference.

    Returns
    -------
    list[float]
        A new list (never modifies the input) with one joint slightly varied.
    """
    neutral = _getNeutral().get(side, [0.0] * 8)
    result = list(joints)

    idx = _pickVariableJoint(result, neutral)
    offset = random.uniform(-MAX_VARIATION_DEG, MAX_VARIATION_DEG)
    result[idx] = _clamp(result[idx] + offset, idx)

    return result


def invalidateNeutralCache() -> None:
    """Call this if poses_library.json is reloaded at runtime."""
    global _neutral_cache
    _neutral_cache = None


def applyAntennaVariation(left: float, right: float) -> tuple[float, float]:
    """
    Return (left, right) antenna angles with independent random offsets.
    The offset amplitude is controlled by MAX_ANTENNA_VARIATION_DEG,
    separate from the arm-joint MAX_VARIATION_DEG.

    Parameters
    ----------
    left  : float  – target left antenna angle (degrees)
    right : float  – target right antenna angle (degrees)

    Returns
    -------
    tuple[float, float] – (varied_left, varied_right)
    """
    varied_left  = left  + random.uniform(-MAX_ANTENNA_VARIATION_DEG, MAX_ANTENNA_VARIATION_DEG)
    varied_right = right + random.uniform(-MAX_ANTENNA_VARIATION_DEG, MAX_ANTENNA_VARIATION_DEG)
    return varied_left, varied_right