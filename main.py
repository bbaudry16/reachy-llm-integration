from textToSpeech import PiperTTS
from mistral import MistralClient
from speechToText import SpeechToText
import libs.reachyController as reachy
from reachy_sdk import trajectory as _traj
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor as _Pool

import threading
import time
from faceDetector import FaceTracker

MODEL_LOCALISATION : str = "./model/en_GB-semaine-medium.onnx"
SPEAKER_ID : int = 3


def face_tracking_loop(reachyC, tracker, active_flag: threading.Event):
    SMOOTHING       = 0.5
    UPDATE_INTERVAL = 0.25
    MOVE_DURATION   = 0.22

    current = [1.0, 0.0, 0.0]
    look_thread = None

    def send_look(target, duration):
        reachyC.head.lookAt(target, duration=duration)

    while True:
        if active_flag.is_set():
            time.sleep(0.1)
            continue

        target = tracker.get_look_at_target()
        if target is not None:
            current = [
                current[i] * SMOOTHING + target[i] * (1 - SMOOTHING)
                for i in range(3)
            ]

            if look_thread is None or not look_thread.is_alive():
                look_thread = threading.Thread(
                    target=send_look,
                    args=(current[:], MOVE_DURATION),
                    daemon=True
                )
                look_thread.start()

        time.sleep(UPDATE_INTERVAL)


@reachy.actionRegistry.register_action("speak_a_text")
def speakAText(executor, params):
    if not reachy.Validator(params, "speak_a_text").require("text").validate():
        return

    text = params["text"]
    reachy.consoleManager.MKprint("saying line : " + str(text), "action", reachy.consoleManager.Color.BRIGHT_MAGENTA)
    piper.textToSpeech(text)


@reachy.actionRegistry.register_action("look_at_human")
def look_at_human(executor, params):
    if not reachy.Validator(params, "look_at_human").require("duration").require("timeout").require("fallback").validate():
        return

    duration = params.get("duration")
    timeout  = params.get("timeout")
    fallback = params.get("fallback")

    target  = None
    elapsed = 0.0
    step    = 0.05

    while elapsed < timeout:
        target = tracker.get_look_at_target()
        if target is not None:
            break
        time.sleep(step)
        elapsed += step

    reachy.consoleManager.MKprint("looking at human : " + str(target), "action", reachy.consoleManager.Color.BRIGHT_MAGENTA)
    if target is None:
        target = fallback

    executor.reachy.head.lookAt(target, duration=duration)


@reachy.actionRegistry.register_action("move_head")
def move_head(executor, params):
    if not reachy.Validator(params, "move_head").require("angles").validate():
        return

    angles   = params.get("angles")   # [neck_roll, neck_pitch, neck_yaw]
    duration = params.get("duration", 0.5)

    reachyHead = executor.reachy.head
    disks      = reachyHead.getDisksInOrder()   # [neck_roll, neck_pitch, neck_yaw]

    limits = [
        reachyHead.DISK_NECK_ROLL,
        reachyHead.DISK_NECK_PITCH,
        reachyHead.DISK_NECK_YAW,
    ]

    clamped = {}
    for disk, angle, lim in zip(disks, angles, limits):
        safe = max(lim.minAngle, min(lim.maxAngle, angle))
        if safe != angle:
            reachy.consoleManager.MKprintSafety(
                f"{disk.name} clamped {angle:.1f}° → {safe:.1f}°",
                "move_head", reachy.consoleManager.Color.BRIGHT_BLUE
            )
        clamped[disk] = safe

    _traj.goto(clamped, duration=duration)


@reachy.actionRegistry.register_action("move_joints_sequence")
def move_joints_sequence(executor, params):
    if not reachy.Validator(params, "move_joints_sequence").require("arm").require("poses").require("step_duration").validate():
        return

    arm           = params.get("arm")
    poses         = params.get("poses")
    step_duration = params.get("step_duration")
    interpolation = params.get("interpolation")

    reachyArm = executor.reachy.armRight
    if arm == "left":
        reachyArm = executor.reachy.armLeft

    interp_obj = (reachyArm.getInterpoaltionByName(interpolation)
                  if interpolation else None)

    for joints in poses:
        if not reachyArm.canMove:
            reachy.consoleManager.MKprintSafety(
                "move_joints_sequence stopped — collision detected.",
                "move_joints_seq", reachy.consoleManager.Color.CYAN
            )
            return

        joint_dict = {joint: value for joint, value in zip(reachyArm.getJointsInOrder(), joints)}

        if interp_obj is None:
            reachyArm.safeGoto(joint_dict, step_duration)
        else:
            reachyArm.safeGoto(joint_dict, step_duration, interpolation=interp_obj)


@reachy.actionRegistry.register_action("move_head_sequence")
def move_head_sequence(executor, params):
    if not reachy.Validator(params, "move_head_sequence").require("poses").require("step_duration").validate():
        return

    poses         = params.get("poses")
    step_duration = params.get("step_duration")

    reachyHead = executor.reachy.head
    disks      = reachyHead.getDisksInOrder()

    limits = [
        reachyHead.DISK_NECK_ROLL,
        reachyHead.DISK_NECK_PITCH,
        reachyHead.DISK_NECK_YAW,
    ]

    for angles in poses:
        clamped = {}
        for disk, angle, lim in zip(disks, angles, limits):
            safe = max(lim.minAngle, min(lim.maxAngle, angle))
            if safe != angle:
                reachy.consoleManager.MKprintSafety(
                    f"{disk.name} clamped {angle:.1f}° → {safe:.1f}°",
                    "move_head_seq", reachy.consoleManager.Color.BRIGHT_BLUE
                )
            clamped[disk] = safe

        _traj.goto(clamped, duration=step_duration)


@reachy.actionRegistry.register_action("play_animation")
def play_animation(executor, params):
    if not reachy.Validator(params, "play_animation").require("name").validate():
        return

    name      = params.get("name")
    speed     = params.get("speed", 1.0)

    anim_file = Path(__file__).resolve().parent / "animations_library.json"
    if not anim_file.exists():
        reachy.consoleManager.MKprintWarning("animations_library.json not found.", "play_animation", reachy.consoleManager.Color.CYAN)
        return

    lib  = json.loads(anim_file.read_text())
    anim = next((a for a in lib.get("animations", []) if a["label"] == name), None)
    if anim is None:
        reachy.consoleManager.MKprintWarning(f"Animation '{name}' not found in library.", "play_animation", reachy.consoleManager.Color.CYAN)
        return

    keyframes     = anim.get("keyframes", [])
    parts         = anim.get("parts", [])
    step_duration = anim.get("step_duration", 0.5) / speed

    if not keyframes:
        reachy.consoleManager.MKprintWarning(f"Animation '{name}' has no keyframes.", "play_animation", reachy.consoleManager.Color.CYAN)
        return

    total = round(len(keyframes) * step_duration, 2)
    reachy.consoleManager.MKprint(
        f"Playing animation '{name}' — {len(keyframes)} keyframes "
        f"step:{step_duration:.2f}s  total:{total}s  (speed x{speed})",
        "play_animation", reachy.consoleManager.Color.CYAN
    )

    reachyC = executor.reachy

    # Play keyframe by keyframe in parallel — no blocking pre-move,
    # so play_animation works correctly inside a parallel block.
    for kf in keyframes:
        targets_r = targets_l = targets_h = None

        if "right" in parts and "right" in kf:
            targets_r = {j: v for j, v in zip(reachyC.armRight.getJointsInOrder(), kf["right"])}
        if "left" in parts and "left" in kf:
            targets_l = {j: v for j, v in zip(reachyC.armLeft.getJointsInOrder(), kf["left"])}
        if "head" in parts and "head" in kf:
            disks     = reachyC.head.getDisksInOrder()
            targets_h = {d: a for d, a in zip(disks, kf["head"])}

        def _right(tr=targets_r):
            if tr and reachyC.armRight.canMove:
                reachyC.armRight.safeGoto(tr, step_duration)

        def _left(tl=targets_l):
            if tl and reachyC.armLeft.canMove:
                reachyC.armLeft.safeGoto(tl, step_duration)

        def _head(th=targets_h):
            if th:
                _traj.goto(th, duration=step_duration)

        with _Pool(max_workers=3) as pool:
            futs = []
            if targets_r: futs.append(pool.submit(_right))
            if targets_l: futs.append(pool.submit(_left))
            if targets_h: futs.append(pool.submit(_head))
            for f in futs:
                f.result()

    reachy.consoleManager.MKprint(f"Animation '{name}' done.", "play_animation", reachy.consoleManager.Color.CYAN)


TALK_TO_HIM : bool = False
REACHY_IP   : str  = "10.59.1.20"

if __name__ == "__main__":

    reachyC = reachy.ReachyController.instanciate(REACHY_IP)
    piper   = PiperTTS(MODEL_LOCALISATION, SPEAKER_ID, 1)

    from prompt.test.librairy import build_system_prompt
    SYSTEM_PROMPT = build_system_prompt()

    client = MistralClient(systemPrompt=SYSTEM_PROMPT)
    stt    = SpeechToText(model="small", language="")

    llm_active = threading.Event()
    if TALK_TO_HIM and REACHY_IP != "localhost":
        tracker    = FaceTracker(reachyC, 10)
        tracker.start()
        face_thread = threading.Thread(
            target=face_tracking_loop,
            args=(reachyC, tracker, llm_active),
            daemon=True
        )
        face_thread.start()

    reachyC.turnOn()

    on   : bool = True
    stop : list = ["stop", "Stop.", "Stop", "stop..", "Stop ?"]

    while on:
        if TALK_TO_HIM:
            user_input = stt.listen(silence_threshold=0.03, silence_duration=1.5)
        else:
            user_input = input("you : ")

        reachyC.fans.tick()
        reachyC.fans.printState()

        if not user_input:
            continue
        if user_input in stop:
            on = False
            continue

        print(f"You : {user_input}")

        result = client.ask(user_input)
        speech = result.get("speech", "")
        ryi    = result.get("ryi", "")

        print(f"Reachy : {speech}")
        print(f"RYI :\n{ryi}\n")

        instructor = reachy.Instructor.loadFromString(ryi, reachyC)
        print(instructor.data)

        llm_active.set()
        if not instructor.data:
            piper.textToSpeech(speech)
        else:
            instructor.execute()
        llm_active.clear()

    reachyC.armLeft._debug_placeHandOnTable(3)
    reachyC.armRight._debug_placeHandOnTable(3)
    reachyC.turnOffSmooth()