import time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import libs.reachyController as reachyLib
import poseLibrary
import animationLibrary
import poseVariation


@dataclass
class ActionContext:
    piper: object
    tracker: object | None


_ctx: ActionContext | None = None


def registerContext(ctx: ActionContext) -> None:
    global _ctx
    _ctx = ctx


_ARM_ACTIONS = {
    "llm_arms", "llm_arms_sequence",
    "llm_pose", "llm_pose_sequence",
    "llm_explain_arm", "llm_explain_arm_sequence",
}

_HEAD_ACTIONS = {
    "llm_move_head", "llm_move_head_sequence", "llm_look_at_human",
}


def _actionName(action: dict) -> str:
    return next(iter(action))


def _actionParams(action: dict) -> dict:
    val = action[next(iter(action))]
    return val if isinstance(val, dict) else {}


def _claimedArms(action: dict) -> set:
    name = _actionName(action)
    if name not in _ARM_ACTIONS:
        return set()

    params = _actionParams(action)
    label = (
        params.get("label")
        or params.get("pose")
        or (params.get("labels") or params.get("poses") or [None])[0]
    )
    arm = params.get("arm", "both")

    if not label:
        return set()

    anim = animationLibrary.getAnimation(label)
    if anim is not None:
        parts = anim.get("parts", [])
        declared = {p for p in parts if p in ("right", "left")}
        if arm == "left" and declared == {"right"}:
            return {"left"}
        return declared

    if poseLibrary.getArmPose(label) is not None:
        if arm == "both":
            return {"right", "left"}
        return {arm} if arm in ("right", "left") else {"right", "left"}

    if arm in ("right", "left"):
        return {arm}

    return set()


def _claimedHead(action: dict) -> bool:
    name = _actionName(action)
    if name in _HEAD_ACTIONS:
        return True

    if name in _ARM_ACTIONS:
        params = _actionParams(action)
        label = params.get("label") or (params.get("labels") or [None])[0]
        if label:
            anim = animationLibrary.getAnimation(label)
            if anim and "head" in anim.get("parts", []):
                return True
    return False


def _safeParallelFilter(params: list) -> list:
    reserved_arms: set = set()
    head_reserved: bool = False
    safe: list = []
    for action in params:
        arms = _claimedArms(action)
        head = _claimedHead(action)
        arm_conflict = arms & reserved_arms
        head_conflict = head and head_reserved
        if arm_conflict or head_conflict:
            parts = []
            if arm_conflict:
                parts.append(f"arms {arm_conflict}")
            if head_conflict:
                parts.append("head")
            print(f"  [safe_parallel] DROPPED '{_actionName(action)}' — {' and '.join(parts)} already reserved")
            continue
        reserved_arms |= arms
        if head:
            head_reserved = True
        safe.append(action)
    return safe


_MIRROR_INDICES = {1, 2, 4, 6}


def _mirrorJoints(joints: list) -> list:
    """Return a mirrored copy of a right-arm joint list for the left arm."""
    return [-v if i in _MIRROR_INDICES else v for i, v in enumerate(joints)]


def _playAnimation(reachyC, anim: dict, speed: float, mirror: bool = False) -> None:
    keyframes = anim.get("keyframes", [])
    parts = anim.get("parts", [])
    stepDuration = anim.get("step_duration", 0.5) / speed
    for kf in keyframes:
        targetsR = targetsL = targetsH = None
        if mirror:
            # Play right-side animation on left arm with mirrored joints
            if "right" in parts and "right" in kf:
                targetsL = dict(zip(reachyC.armLeft.getJointsInOrder(), _mirrorJoints(kf["right"])))
        else:
            if "right" in parts and "right" in kf:
                targetsR = dict(zip(reachyC.armRight.getJointsInOrder(), kf["right"]))
            if "left" in parts and "left" in kf:
                targetsL = dict(zip(reachyC.armLeft.getJointsInOrder(), kf["left"]))
        if "head" in parts and "head" in kf:
            targetsH = kf["head"]
        def moveRight(tr=targetsR):
            if tr and reachyC.armRight.canMove:
                reachyC.armRight.safeGoto(tr, stepDuration)
        def moveLeft(tl=targetsL):
            if tl and reachyC.armLeft.canMove:
                reachyC.armLeft.safeGoto(tl, stepDuration)
        def moveHead(th=targetsH):
            if th:
                reachyC.head.gotoHeadAngles(th, stepDuration)
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = []
            if targetsR:
                futs.append(pool.submit(moveRight))
            if targetsL:
                futs.append(pool.submit(moveLeft))
            if targetsH:
                futs.append(pool.submit(moveHead))
            for f in futs:
                f.result()


def _playArmPose(reachyC, label: str, arm: str, duration: float) -> None:
    data = poseLibrary.getArmPose(label)
    if data is None:
        return
    if data["min_duration"] is not None:
        duration = max(duration, data["min_duration"])
    rightJoints = poseVariation.applyVariation(data["right"], "right")
    leftJoints  = poseVariation.applyVariation(data["left"],  "left")
    def moveRight():
        if reachyC.armRight.canMove:
            jd = dict(zip(reachyC.armRight.getJointsInOrder(), rightJoints))
            reachyC.armRight.safeGoto(jd, duration)
    def moveLeft():
        if reachyC.armLeft.canMove:
            jd = dict(zip(reachyC.armLeft.getJointsInOrder(), leftJoints))
            reachyC.armLeft.safeGoto(jd, duration)
    if arm == "both":
        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(moveRight), pool.submit(moveLeft)]
            for f in futs:
                f.result()
    elif arm == "right":
        moveRight()
    elif arm == "left":
        moveLeft()


def _playExplainPose(reachyC, label: str, arm: str, duration: float) -> None:
    data = poseLibrary.getExplanationPose(label)
    if data is None:
        return
    reachyArm = reachyC.armRight if arm == "right" else reachyC.armLeft
    if not reachyArm.canMove:
        return
    side = "right" if arm == "right" else "left"
    joints = poseVariation.applyVariation(data["joints"], side)
    jd = dict(zip(reachyArm.getJointsInOrder(), joints))
    reachyArm.safeGoto(jd, duration)


def _resolveArms(reachyC, label: str, arm: str, duration: float, speed: float) -> None:
    anim = animationLibrary.getAnimation(label)
    if anim is not None:
        parts = anim.get("parts", [])
        # Right-only animation requested on left arm → mirror
        mirror = (arm == "left" and "right" in parts and "left" not in parts)
        _playAnimation(reachyC, anim, speed, mirror=mirror)
        return
    if poseLibrary.getArmPose(label) is not None:
        _playArmPose(reachyC, label, arm, duration)
        return
    if arm in ("right", "left"):
        _playExplainPose(reachyC, label, arm, duration)

@reachyLib.register_control_action("parallel")
def safeParallel(executor, params: list) -> None:
    if not isinstance(params, list):
        return
    safe = _safeParallelFilter(params)
    with ThreadPoolExecutor(max_workers=max(1, len(safe))) as pool:
        futures = [pool.submit(executor.executeInstruction, action) for action in safe]
        for future in futures:
            future.result()

@reachyLib.register_action("llm_speak")
def llmSpeak(executor, params: dict) -> None:
    text = params.get("text", "")
    if not text or _ctx is None:
        return
    _ctx.piper.textToSpeech(text)


@reachyLib.register_action("llm_look_at_human")
def llmLookAtHuman(executor, params: dict) -> None:
    duration = params.get("duration", 0.5)
    timeout = params.get("timeout", 1.5)
    fallback = params.get("fallback", [1, 0, 0])
    target = None
    if _ctx is not None and _ctx.tracker is not None:
        elapsed = 0.0
        step = 0.05
        while elapsed < timeout:
            target = _ctx.tracker.getLookAtTarget()
            if target is not None:
                break
            time.sleep(step)
            elapsed += step
    if target is None:
        target = fallback
    executor.reachy.head.lookAt(target, duration=duration)


@reachyLib.register_action("llm_arms")
def llmArms(executor, params: dict) -> None:
    label = params.get("label")
    arm = params.get("arm", "both")
    duration = params.get("duration", 0.6)
    speed = params.get("speed", 1.0)
    if not label:
        return
    _resolveArms(executor.reachy, label, arm, duration, speed)


@reachyLib.register_action("llm_arms_sequence")
def llmArmsSequence(executor, params: dict) -> None:
    labels = params.get("labels", [])
    arm = params.get("arm", "both")
    stepDuration = params.get("step_duration", 0.5)
    speed = params.get("speed", 1.0)
    if not labels:
        return
    for label in labels:
        _resolveArms(executor.reachy, label, arm, stepDuration, speed)


@reachyLib.register_action("llm_pose")
def llmPose(executor, params: dict) -> None:
    llmArms(executor, params)


@reachyLib.register_action("llm_pose_sequence")
def llmPoseSequence(executor, params: dict) -> None:
    labels = params.get("labels", params.get("poses", []))
    llmArmsSequence(executor, {**params, "labels": labels})


@reachyLib.register_action("llm_explain_arm")
def llmExplainArm(executor, params: dict) -> None:
    label = params.get("pose", params.get("label"))
    llmArms(executor, {**params, "label": label})


@reachyLib.register_action("llm_explain_arm_sequence")
def llmExplainArmSequence(executor, params: dict) -> None:
    labels = params.get("poses", params.get("labels", []))
    llmArmsSequence(executor, {**params, "labels": labels})


@reachyLib.register_action("llm_move_head")
def llmMoveHead(executor, params: dict) -> None:
    pose = params.get("pose")
    duration = params.get("duration", 0.5)
    if not pose:
        return
    angles = poseLibrary.getHeadPose(pose)
    if angles is None:
        return
    executor.reachy.head.gotoHeadAngles(angles, duration)


@reachyLib.register_action("llm_move_head_sequence")
def llmMoveHeadSequence(executor, params: dict) -> None:
    poses = params.get("poses", [])
    stepDuration = params.get("step_duration", 0.4)
    if not poses:
        return
    for label in poses:
        angles = poseLibrary.getHeadPose(label)
        if angles is None:
            continue
        executor.reachy.head.gotoHeadAngles(angles, stepDuration)


@reachyLib.register_action("llm_set_antenna")
def llmSetAntenna(executor, params: dict) -> None:
    pose = params.get("pose")
    duration = params.get("duration", 0.5)
    if not pose:
        return
    data = poseLibrary.getAntennaPose(pose)
    if data is None:
        return
    leftAngle, rightAngle = data
    leftAngle, rightAngle = poseVariation.applyAntennaVariation(leftAngle, rightAngle)
    reachyLib.ACTION_REGISTRY["set_antenna"](executor, {"antenna": "left", "angle": leftAngle, "duration": duration})
    reachyLib.ACTION_REGISTRY["set_antenna"](executor, {"antenna": "right", "angle": rightAngle, "duration": duration})


@reachyLib.register_action("llm_vibrate_antenna")
def llmVibrateAntenna(executor, params: dict) -> None:
    reachyLib.ACTION_REGISTRY["vibrate_antenna"](executor, params)