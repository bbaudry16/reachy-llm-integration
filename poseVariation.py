"""
Adds subtle randomness to static arm poses so Reachy never holds the exact same position twice.

Joint indices follow JOINT_ORDER:
  [shoulder_pitch, shoulder_roll, arm_yaw, elbow_pitch, forearm_yaw, wrist_pitch, wrist_roll, gripper]

Only joints listed in VARIABLE_JOINTS are candidates for variation.
The joint with the largest deviation from neutral is selected and offset by a random amount,
then clamped to JOINT_LIMITS.
"""

import random
from typing import Optional

import poseLibrary


MAX_VARIATION_DEG: float = 20.0

MAX_ANTENNA_VARIATION_DEG: float = 8.0

VARIABLE_JOINTS: list[int] = [0, 1, 2, 3]

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


_neutral_cache: Optional[dict] = None


def _getNeutral() -> dict:
    """
    Return the neutral arm pose, cached after first load.

    @rtype: dict
    """
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
    Return the index in VARIABLE_JOINTS with the largest absolute delta from neutral.

    @param joints: Current joint values.
    @type joints: list
    @param neutral: Neutral joint values.
    @type neutral: list
    @rtype: int
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


def applyVariation(joints: list[float], side: str) -> list[float]:
    """
    Return a copy of joints with a random offset applied to the most expressive joint.

    @param joints: The 8 joint values for one arm.
    @type joints: list
    @param side: 'right' or 'left'.
    @type side: str
    @return: New joint list with one joint slightly varied.
    @rtype: list
    """
    neutral = _getNeutral().get(side, [0.0] * 8)
    result = list(joints)

    idx = _pickVariableJoint(result, neutral)
    offset = random.uniform(-MAX_VARIATION_DEG, MAX_VARIATION_DEG)
    result[idx] = _clamp(result[idx] + offset, idx)

    return result


def invalidateNeutralCache() -> None:
    """Invalidate the neutral pose cache. Call if poses_library.json is reloaded at runtime."""
    global _neutral_cache
    _neutral_cache = None


def applyAntennaVariation(left: float, right: float) -> tuple[float, float]:
    """
    Return antenna angles with independent random offsets applied to each side.

    @param left: Target left antenna angle in degrees.
    @type left: float
    @param right: Target right antenna angle in degrees.
    @type right: float
    @return: (varied_left, varied_right)
    @rtype: tuple
    """
    varied_left  = left  + random.uniform(-MAX_ANTENNA_VARIATION_DEG, MAX_ANTENNA_VARIATION_DEG)
    varied_right = right + random.uniform(-MAX_ANTENNA_VARIATION_DEG, MAX_ANTENNA_VARIATION_DEG)
    return varied_left, varied_right