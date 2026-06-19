import time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import poseLibrary
import animationLibrary


@dataclass
class ActionContext:
    piper: object
    tracker: object | None


def registerActions(ctx: ActionContext, registry: dict) -> None:

    def register(name: str):
        def decorator(func):
            registry[name] = func
            return func
        return decorator

    @register("llm_speak")
    def llmSpeak(executor, params: dict) -> None:
        text = params.get("text", "")
        if not text:
            return
        ctx.piper.textToSpeech(text)

    @register("llm_look_at_human")
    def llmLookAtHuman(executor, params: dict) -> None:
        duration = params.get("duration", 0.5)
        timeout = params.get("timeout", 1.5)
        fallback = params.get("fallback", [1, 0, 0])
        target = None
        if ctx.tracker is not None:
            elapsed = 0.0
            step = 0.05
            while elapsed < timeout:
                target = ctx.tracker.getLookAtTarget()
                if target is not None:
                    break
                time.sleep(step)
                elapsed += step
        if target is None:
            target = fallback
        executor.reachy.head.lookAt(target, duration=duration)

    def _playAnimation(reachyC, anim: dict, speed: float) -> None:
        keyframes = anim.get("keyframes", [])
        parts = anim.get("parts", [])
        stepDuration = anim.get("step_duration", 0.5) / speed
        for kf in keyframes:
            targetsR = targetsL = targetsH = None
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
        def moveRight():
            if reachyC.armRight.canMove:
                jd = dict(zip(reachyC.armRight.getJointsInOrder(), data["right"]))
                reachyC.armRight.safeGoto(jd, duration)
        def moveLeft():
            if reachyC.armLeft.canMove:
                jd = dict(zip(reachyC.armLeft.getJointsInOrder(), data["left"]))
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

    @register("llm_pose")
    def llmPose(executor, params: dict) -> None:
        label = params.get("label")
        arm = params.get("arm", "both")
        duration = params.get("duration", 0.6)
        speed = params.get("speed", 1.0)
        if not label:
            return
        anim = animationLibrary.getAnimation(label)
        if anim is not None:
            _playAnimation(executor.reachy, anim, speed)
        else:
            _playArmPose(executor.reachy, label, arm, duration)

    @register("llm_pose_sequence")
    def llmPoseSequence(executor, params: dict) -> None:
        labels = params.get("labels", [])
        arm = params.get("arm", "both")
        stepDuration = params.get("step_duration", 0.5)
        if not labels:
            return
        for label in labels:
            anim = animationLibrary.getAnimation(label)
            if anim is not None:
                _playAnimation(executor.reachy, anim, 1.0)
            else:
                _playArmPose(executor.reachy, label, arm, stepDuration)

    @register("llm_move_head")
    def llmMoveHead(executor, params: dict) -> None:
        pose = params.get("pose")
        duration = params.get("duration", 0.5)
        if not pose:
            return
        angles = poseLibrary.getHeadPose(pose)
        if angles is None:
            return
        executor.reachy.head.gotoHeadAngles(angles, duration)

    @register("llm_move_head_sequence")
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

    @register("llm_explain_arm")
    def llmExplainArm(executor, params: dict) -> None:
        pose = params.get("pose")
        arm = params.get("arm")
        duration = params.get("duration", 0.6)
        if not pose or not arm:
            return
        data = poseLibrary.getExplanationPose(pose)
        if data is None:
            return
        reachyArm = executor.reachy.armRight if arm == "right" else executor.reachy.armLeft
        if not reachyArm.canMove:
            return
        jd = dict(zip(reachyArm.getJointsInOrder(), data["joints"]))
        reachyArm.safeGoto(jd, duration)

    @register("llm_explain_arm_sequence")
    def llmExplainArmSequence(executor, params: dict) -> None:
        poses = params.get("poses", [])
        arm = params.get("arm", "right")
        stepDuration = params.get("step_duration", 0.5)
        if not poses:
            return
        reachyArm = executor.reachy.armRight if arm == "right" else executor.reachy.armLeft
        for label in poses:
            if not reachyArm.canMove:
                return
            data = poseLibrary.getExplanationPose(label)
            if data is None:
                continue
            jd = dict(zip(reachyArm.getJointsInOrder(), data["joints"]))
            reachyArm.safeGoto(jd, stepDuration)

    @register("llm_set_antenna")
    def llmSetAntenna(executor, params: dict) -> None:
        pose = params.get("pose")
        duration = params.get("duration", 0.5)
        if not pose:
            return
        data = poseLibrary.getAntennaPose(pose)
        if data is None:
            return
        leftAngle, rightAngle = data
        registry["set_antenna"](executor, {"antenna": "left", "angle": leftAngle, "duration": duration})
        registry["set_antenna"](executor, {"antenna": "right", "angle": rightAngle, "duration": duration})

    @register("llm_vibrate_antenna")
    def llmVibrateAntenna(executor, params: dict) -> None:
        registry["vibrate_antenna"](executor, params)