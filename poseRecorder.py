import json
import sys
import tty
import termios
import time
from pathlib import Path

LIBRARY_FILE = "poses_library.json"
CATEGORIES = ("emotion", "conversational", "explanation")
JOINT_ORDER = ["shoulder_pitch", "shoulder_roll", "arm_yaw", "elbow_pitch", "forearm_yaw", "wrist_pitch", "wrist_roll", "gripper"]


def getKey() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def getLine(prompt: str) -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return sys.stdin.readline().strip()


def setStiff(jointDict: dict, stiff: bool) -> None:
    for j in jointDict.values():
        j.compliant = not stiff


def captureArm(arm, armId: str) -> list[float]:
    result = []
    for name in JOINT_ORDER:
        sided = f"{armId}_{name}"
        j = arm._joints.get(sided)
        result.append(round(j.present_position, 2) if j else 0.0)
    return result


def captureHead(reachyC) -> list[float]:
    return [round(j.present_position, 2) for j in reachyC.head.getDisksInOrder()]


def captureAntennas(reachyC) -> tuple[float, float]:
    head = reachyC.head._reachyHead
    def getAnt(names):
        for n in names:
            j = getattr(head, n, None)
            if j is not None:
                return round(j.present_position, 1)
        return 0.0
    return getAnt(["l_antenna", "left_antenna"]), getAnt(["r_antenna", "right_antenna"])


def loadLibrary() -> dict:
    if not Path(LIBRARY_FILE).exists():
        return {"arms": [], "head": [], "antennas": []}
    try:
        content = Path(LIBRARY_FILE).read_text().strip()
        return json.loads(content) if content else {"arms": [], "head": [], "antennas": []}
    except json.JSONDecodeError:
        return {"arms": [], "head": [], "antennas": []}


def saveLibrary(lib: dict) -> None:
    with open(LIBRARY_FILE, "w") as f:
        json.dump(lib, f, indent=2, ensure_ascii=False)


def askCategory() -> str:
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
    while True:
        raw = getLine("  Arm (r=right / l=left): ").strip().lower()
        if raw in ("r", "right"):
            return "right"
        if raw in ("l", "left"):
            return "left"
        print("  type r or l")


def printSummary(lib: dict) -> None:
    print("\n── Library ──────────────────────────────────────")
    for section in ("arms", "head", "antennas"):
        entries = lib[section]
        print(f"  {section} ({len(entries)} poses):")
        for cat in CATEGORIES:
            group = [e for e in entries if e.get("category") == cat]
            if not group:
                continue
            print(f"    [{cat}]")
            for e in group:
                role = f"  role:{e['role']}" if e.get("role") else ""
                arm = f"  arm:{e['arm']}" if e.get("arm") else ""
                print(f"      {e['label']:<18} {e.get('description', '')}{role}{arm}")
    print("─────────────────────────────────────────────────\n")


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

    print(f"\nPose Recorder — {LIBRARY_FILE}")
    print("  R=right  L=left  H=head  SPACE=capture  S=save  P=summary  Q=quit\n")
    printSummary(lib)

    while True:
        reachyC.fans.tick()
        key = getKey()

        if key in ("r", "R"):
            stiff["right"] = not stiff["right"]
            setStiff(rightJoints, stiff["right"])
            print(f"  RIGHT → {'STIFF' if stiff['right'] else 'compliant'}")

        elif key in ("l", "L"):
            stiff["left"] = not stiff["left"]
            setStiff(leftJoints, stiff["left"])
            print(f"  LEFT  → {'STIFF' if stiff['left'] else 'compliant'}")

        elif key in ("h", "H"):
            stiff["head"] = not stiff["head"]
            setStiff(headJoints, stiff["head"])
            print(f"  HEAD  → {'STIFF' if stiff['head'] else 'compliant'}")

        elif key == " ":
            rJoints = captureArm(reachyC.armRight, "r")
            lJoints = captureArm(reachyC.armLeft, "l")
            look = captureHead(reachyC)
            try:
                antL, antR = captureAntennas(reachyC)
            except Exception:
                antL, antR = 0.0, 0.0

            print("\n── Captured ─────────────────────────────────────")
            print(f"  R joints: {rJoints}")
            print(f"  L joints: {lJoints}")
            print(f"  Head:     roll={look[0]}  pitch={look[1]}  yaw={look[2]}")
            print(f"  Ant:      L={antL}  R={antR}")
            print("─────────────────────────────────────────────────")

            print("  What? a=arms  h=head  n=antennas  all=all  skip=nothing")
            choice = getLine("  → ").strip().lower()
            if choice == "skip":
                print("  Skipped.")
                continue

            label = getLine("  Label: ").strip()
            if not label:
                print("  No label — skipped.")
                continue

            desc = getLine("  Description (Enter to skip): ").strip()
            category = askCategory()

            base = {"label": label, "category": category, "description": desc, "timestamp": time.time()}

            if choice in ("a", "all"):
                if category == "explanation":
                    arm = askArm()
                    role = getLine("  Role (what this arm represents, e.g. 'orbit', 'origin', 'rise'): ").strip()
                    joints = rJoints if arm == "right" else lJoints
                    lib["arms"].append({**base, "arm": arm, "role": role, "joints": joints})
                    print(f"  ✓ Arm [{label}] [{category}] arm:{arm} role:{role}")
                else:
                    lib["arms"].append({**base, "right_joints": rJoints, "left_joints": lJoints})
                    print(f"  ✓ Arms [{label}] [{category}]")

            if choice in ("h", "all"):
                lib["head"].append({**base, "angles": look})
                print(f"  ✓ Head [{label}] [{category}]")

            if choice in ("n", "all"):
                lib["antennas"].append({**base, "left": antL, "right": antR})
                print(f"  ✓ Antennas [{label}] [{category}]")

            saveLibrary(lib)

        elif key in ("s", "S"):
            saveLibrary(lib)
            print(f"  Saved — arms:{len(lib['arms'])} head:{len(lib['head'])} antennas:{len(lib['antennas'])}")

        elif key in ("p", "P"):
            printSummary(lib)

        elif key in ("q", "Q", "\x03"):
            saveLibrary(lib)
            print("\nSaved. Quitting.")
            reachyC.reachy.turn_off("reachy")
            reachyC.fans.turnOffAll()
            break


main()