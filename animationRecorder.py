import json
import sys
import tty
import termios
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ANIMATION_FILE = "animations_library.json"
CATEGORIES = ("emotion", "conversational", "explanation")
JOINT_ORDER = ["shoulder_pitch", "shoulder_roll", "arm_yaw", "elbow_pitch", "forearm_yaw", "wrist_pitch", "wrist_roll", "gripper"]


def getKey() -> str:
    """Read a single keypress from stdin without echoing."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def getLine(prompt: str) -> str:
    """Print a prompt and read a line from stdin."""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return sys.stdin.readline().strip()


def setStiff(jointDict: dict, stiff: bool) -> None:
    """Set compliance state for all joints in the dict."""
    for j in jointDict.values():
        j.compliant = not stiff


def captureArm(arm, armId: str) -> list[float]:
    """
    Return the current joint positions for one arm.

    @param arm: Arm controller object.
    @param armId: Joint name prefix ('r' or 'l').
    @type armId: str
    @rtype: list
    """
    result = []
    for name in JOINT_ORDER:
        sided = f"{armId}_{name}"
        j = arm._joints.get(sided)
        result.append(round(j.present_position, 2) if j else 0.0)
    return result


def captureHead(reachyC) -> list[float]:
    """
    Return the current disk positions for the head.

    @rtype: list
    """
    return [round(j.present_position, 2) for j in reachyC.head.getDisksInOrder()]


def loadLibrary() -> dict:
    """
    Load the animation library from disk.

    @return: Library dict with 'animations' key.
    @rtype: dict
    """
    if not Path(ANIMATION_FILE).exists():
        return {"animations": []}
    try:
        content = Path(ANIMATION_FILE).read_text().strip()
        return json.loads(content) if content else {"animations": []}
    except json.JSONDecodeError:
        return {"animations": []}


def saveLibrary(lib: dict) -> None:
    """
    Save the animation library to disk.

    @param lib: Library dict to save.
    @type lib: dict
    """
    with open(ANIMATION_FILE, "w") as f:
        json.dump(lib, f, indent=2, ensure_ascii=False)
    print(f"  Saved {len(lib['animations'])} animation(s) to {ANIMATION_FILE}")


def printSummary(lib: dict) -> None:
    """Print a formatted summary of all animations in the library."""
    print("\nAnimation Library")
    anims = lib.get("animations", [])
    if not anims:
        print("  (empty)")
    for cat in CATEGORIES:
        group = [a for a in anims if a.get("category") == cat]
        if not group:
            continue
        print(f"  [{cat}]")
        for a in group:
            parts = a.get("parts", [])
            keyframes = len(a.get("keyframes", []))
            step = a.get("step_duration", "?")
            dur = round(keyframes * step, 2) if isinstance(step, (int, float)) else "?"
            role = f"  role:{a['role']}" if a.get("role") else ""
            arm = f"  arm:{a['arm']}" if a.get("arm") else ""
            print(f"    {a['label']:<20} keyframes:{keyframes}  step:{step}s  dur:{dur}s  parts:{parts}{role}{arm}")
            if a.get("description"):
                print(f"    {'':20} -> {a['description']}")
    print()


def askParts() -> list[str]:
    """Prompt the user to select which body parts to capture."""
    print("  Parts captured in each keyframe?")
    print("  r=right arm  l=left arm  h=head  (combine: rl / rh / lh / rlh)")
    raw = getLine("  -> ").lower().strip()
    parts = []
    if "r" in raw:
        parts.append("right")
    if "l" in raw:
        parts.append("left")
    if "h" in raw:
        parts.append("head")
    if not parts:
        print("  Nothing selected — defaulting to right+left+head")
        parts = ["right", "left", "head"]
    return parts


def askStepDuration() -> float:
    """Prompt the user for a step duration in seconds."""
    raw = getLine("  Step duration in seconds (Enter = 0.5): ").strip()
    try:
        v = float(raw)
        return v if v > 0 else 0.5
    except ValueError:
        return 0.5


def askCategory() -> str:
    """Prompt the user to select an animation category."""
    while True:
        raw = getLine("  Category (e=emotion / c=conversational / x=explanation): ").strip().lower()
        if raw in ("e", "emotion"):
            return "emotion"
        if raw in ("c", "conversational"):
            return "conversational"
        if raw in ("x", "explanation"):
            return "explanation"
        print("  type e, c or x")


def askArm() -> str:
    """Prompt the user to select which arm the animation represents."""
    while True:
        raw = getLine("  Arm this animation represents (r=right / l=left / both): ").strip().lower()
        if raw in ("r", "right"):
            return "right"
        if raw in ("l", "left"):
            return "left"
        if raw in ("b", "both"):
            return "both"
        print("  type r, l or both")


def previewKeyframes(reachyC, keyframes: list, parts: list, stepDuration: float) -> None:
    """
    Play back the recorded keyframes on the robot.

    @param reachyC: Reachy controller instance.
    @param keyframes: List of keyframe dicts.
    @type keyframes: list
    @param parts: Body parts to animate.
    @type parts: list
    @param stepDuration: Duration per keyframe step in seconds.
    @type stepDuration: float
    """
    from reachy_sdk import trajectory as traj

    if not keyframes:
        print("  No keyframes to preview.")
        return

    print(f"  Previewing {len(keyframes)} keyframes @ {stepDuration}s/step...")

    first = keyframes[0]
    if "right" in parts and "right" in first:
        jd = {j: v for j, v in zip(reachyC.armRight.getJointsInOrder(), first["right"])}
        reachyC.armRight.safeGoto(jd, duration=1.5)
    if "left" in parts and "left" in first:
        jd = {j: v for j, v in zip(reachyC.armLeft.getJointsInOrder(), first["left"])}
        reachyC.armLeft.safeGoto(jd, duration=1.5)
    if "head" in parts and "head" in first:
        disks = reachyC.head.getDisksInOrder()
        traj.goto({d: a for d, a in zip(disks, first["head"])}, duration=1.5)

    for i, kf in enumerate(keyframes):
        def moveRight(kf=kf):
            if "right" in parts and "right" in kf:
                jd = {j: v for j, v in zip(reachyC.armRight.getJointsInOrder(), kf["right"])}
                reachyC.armRight.safeGoto(jd, stepDuration)
        def moveLeft(kf=kf):
            if "left" in parts and "left" in kf:
                jd = {j: v for j, v in zip(reachyC.armLeft.getJointsInOrder(), kf["left"])}
                reachyC.armLeft.safeGoto(jd, stepDuration)
        def moveHead(kf=kf):
            if "head" in parts and "head" in kf:
                disks = reachyC.head.getDisksInOrder()
                traj.goto({d: a for d, a in zip(disks, kf["head"])}, duration=stepDuration)
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(moveRight), pool.submit(moveLeft), pool.submit(moveHead)]
            for f in futs:
                f.result()
        print(f"  [{i+1}/{len(keyframes)}]", end="\r")

    print("\n  Done.")


def main() -> None:
    import libs.reachyController as reachy

    print("Connecting to Reachy...")
    reachyC = reachy.ReachyController.instanciate("10.59.1.20")
    reachyC.reachy.turn_off("reachy")

    stiff = {"right": False, "left": False, "head": False}
    rightJoints = reachyC.armRight._joints
    leftJoints = reachyC.armLeft._joints
    headJoints = reachyC.head._disks

    lib = loadLibrary()
    keyframes: list = []

    print(f"\nAnimation Recorder — {ANIMATION_FILE}")
    print("  R=right  L=left  H=head  SPACE=capture keyframe")
    print("  ENTER=finish+save  U=undo  P=preview  C=clear  D=summary  Q=quit\n")
    printSummary(lib)
    reachyC.fans.turnOnAll()

    while True:
        key = getKey()
        reachyC.fans.tick()
        if key in ("r", "R"):
            stiff["right"] = not stiff["right"]
            setStiff(rightJoints, stiff["right"])
            print(f"  RIGHT -> {'STIFF' if stiff['right'] else 'compliant'}")

        elif key in ("l", "L"):
            stiff["left"] = not stiff["left"]
            setStiff(leftJoints, stiff["left"])
            print(f"  LEFT  -> {'STIFF' if stiff['left'] else 'compliant'}")

        elif key in ("h", "H"):
            stiff["head"] = not stiff["head"]
            setStiff(headJoints, stiff["head"])
            print(f"  HEAD  -> {'STIFF' if stiff['head'] else 'compliant'}")

        elif key == " ":
            kf = {"right": captureArm(reachyC.armRight, "r"), "left": captureArm(reachyC.armLeft, "l"), "head": captureHead(reachyC)}
            keyframes.append(kf)
            idx = len(keyframes)
            print(f"  Keyframe {idx} captured")
            print(f"    R: {kf['right']}")
            print(f"    L: {kf['left']}")
            print(f"    H: {kf['head']}")

        elif key in ("u", "U"):
            if keyframes:
                keyframes.pop()
                print(f"  Undo — {len(keyframes)} keyframe(s) remaining")
            else:
                print("  Nothing to undo.")

        elif key in ("p", "P"):
            if not keyframes:
                print("  No keyframes yet.")
            else:
                parts = askParts()
                stepDuration = askStepDuration()
                reachyC.reachy.turn_on("reachy")
                time.sleep(0.3)
                previewKeyframes(reachyC, keyframes, parts, stepDuration)
                reachyC.reachy.turn_off("reachy")

        elif key in ("\r", "\n"):
            if not keyframes:
                print("  No keyframes to save.")
                continue

            print(f"\n  Finishing animation with {len(keyframes)} keyframe(s).")
            parts = askParts()
            stepDuration = askStepDuration()
            label = getLine("  Label: ").strip()
            if not label:
                print("  No label — not saved.")
                continue

            desc = getLine("  Description (Enter to skip): ").strip()
            category = askCategory()

            anim = {
                "label": label,
                "category": category,
                "description": desc,
                "parts": parts,
                "step_duration": stepDuration,
                "timestamp": time.time(),
                "keyframes": [{p: kf[p] for p in parts if p in kf} for kf in keyframes],
            }

            if category == "explanation":
                arm = askArm()
                role = getLine("  Role (what this animation represents, e.g. 'orbit', 'origin'): ").strip()
                anim["arm"] = arm
                anim["role"] = role

            lib["animations"].append(anim)
            saveLibrary(lib)
            print(f"  Saved [{label}] [{category}]  {len(keyframes)} keyframes  step:{stepDuration}s")
            keyframes = []

        elif key in ("c", "C"):
            keyframes = []
            print("  Cleared — 0 keyframes.")

        elif key in ("d", "D"):
            printSummary(lib)

        elif key in ("q", "Q", "\x03"):
            if keyframes:
                print(f"  Warning: {len(keyframes)} unsaved keyframes will be lost.")
            saveLibrary(lib)
            print("\nSaved. Quitting.")
            reachyC.reachy.turn_off("reachy")
            reachyC.fans.turnOffAll()
            break


main()