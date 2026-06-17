"""
Pose Recorder — captures joint angles for exact replay via move_joints.
Collision checking is preserved through safeGoto inside move_joints.

Controls:
  R  → toggle RIGHT arm   stiff/compliant
  L  → toggle LEFT arm    stiff/compliant
  H  → toggle HEAD        stiff/compliant
  SPACE → capture + annotate
  S  → save library
  P  → print summary
  Q  → quit
"""

import json, sys, tty, termios, time
from pathlib import Path

LIBRARY_FILE = "poses_library.json"

JOINT_ORDER = [
    "shoulder_pitch", "shoulder_roll", "arm_yaw",
    "elbow_pitch", "forearm_yaw",
    "wrist_pitch", "wrist_roll", "gripper"
]

CATEGORIES = ("emotion", "conversational")


def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def get_line(prompt):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return sys.stdin.readline().strip()


def set_stiff(joint_dict, stiff):
    for j in joint_dict.values():
        j.compliant = not stiff


def capture_arm_joints(arm, arm_id):
    result = []
    for name in JOINT_ORDER:
        sided = f"{arm_id}_{name}"
        j = arm._joints.get(sided)
        result.append(round(j.present_position, 2) if j else 0.0)
    return result


def capture_head(reachyC):
    return [round(j.present_position, 2) for j in reachyC.head.getDisksInOrder()]


def capture_antennas(reachyC):
    head = reachyC.head._reachyHead
    def get_ant(names):
        for n in names:
            j = getattr(head, n, None)
            if j is not None:
                return round(j.present_position, 1)
        return 0.0
    return get_ant(["l_antenna", "left_antenna"]), get_ant(["r_antenna", "right_antenna"])


def load_library():
    if not Path(LIBRARY_FILE).exists():
        return {"arms": [], "head": [], "antennas": []}
    try:
        content = Path(LIBRARY_FILE).read_text().strip()
        return json.loads(content) if content else {"arms": [], "head": [], "antennas": []}
    except json.JSONDecodeError:
        return {"arms": [], "head": [], "antennas": []}


def save_library(lib):
    with open(LIBRARY_FILE, "w") as f:
        json.dump(lib, f, indent=2, ensure_ascii=False)


def ask_category():
    """Ask the user to pick a category. Returns 'emotion' or 'conversational'."""
    while True:
        raw = get_line("  Category (e=emotion / c=conversational): ").strip().lower()
        if raw in ("e", "emotion"):
            return "emotion"
        if raw in ("c", "conversational"):
            return "conversational"
        print("  → type 'e' or 'c'")


def print_summary(lib):
    print("\n── Library ──────────────────────────────────────")
    for section in ("arms", "head", "antennas"):
        entries = lib[section]
        print(f"  {section} ({len(entries)} poses):")
        for cat in CATEGORIES:
            group = [e for e in entries if e.get("category") == cat]
            if group:
                print(f"    [{cat}]")
                for e in group:
                    print(f"      {e['label']:<18} {e.get('description','')}")
    print("─────────────────────────────────────────────────\n")


def main():
    import libs.reachyController as reachy

    print("Connecting to Reachy...")
    reachyC = reachy.ReachyController.instanciate("10.59.1.20")
    reachyC.reachy.turn_off("reachy")

    stiff = {"right": False, "left": False, "head": False}
    right_joints = reachyC.armRight._joints
    left_joints  = reachyC.armLeft._joints
    head_joints  = reachyC.head._disks

    lib = load_library()

    print(f"\nPose Recorder — {LIBRARY_FILE}")
    print("  R=right  L=left  H=head  SPACE=capture  S=save  P=summary  Q=quit\n")
    print_summary(lib)

    while True:
        reachyC.fans.tick()
        key = get_key()

        if key in ('r', 'R'):
            stiff["right"] = not stiff["right"]
            set_stiff(right_joints, stiff["right"])
            print(f"  RIGHT → {'STIFF' if stiff['right'] else 'compliant'}")

        elif key in ('l', 'L'):
            stiff["left"] = not stiff["left"]
            set_stiff(left_joints, stiff["left"])
            print(f"  LEFT  → {'STIFF' if stiff['left'] else 'compliant'}")

        elif key in ('h', 'H'):
            stiff["head"] = not stiff["head"]
            set_stiff(head_joints, stiff["head"])
            print(f"  HEAD  → {'STIFF' if stiff['head'] else 'compliant'}")

        elif key == ' ':
            r_joints = capture_arm_joints(reachyC.armRight, "r")
            l_joints = capture_arm_joints(reachyC.armLeft,  "l")
            look     = capture_head(reachyC)
            try:
                ant_l, ant_r = capture_antennas(reachyC)
            except Exception:
                ant_l, ant_r = 0.0, 0.0

            print("\n── Captured ─────────────────────────────────────")
            print(f"  R joints: {r_joints}")
            print(f"  L joints: {l_joints}")
            print(f"  Head:     neck_roll={look[0]}°  neck_pitch={look[1]}°  neck_yaw={look[2]}°")
            print(f"  Ant:      L={ant_l}°  R={ant_r}°")
            print("─────────────────────────────────────────────────")

            print("  What? a=arms  h=head  n=antennas  all=all  skip=nothing")
            choice = get_line("  → ").strip().lower()
            if choice == "skip":
                print("  Skipped.")
                continue

            label = get_line("  Label: ").strip()
            if not label:
                print("  No label — skipped.")
                continue

            desc     = get_line("  Description (Enter to skip): ").strip()
            category = ask_category()

            base = {
                "label":       label,
                "category":    category,
                "description": desc,
                "timestamp":   time.time(),
            }

            if choice in ("a", "all"):
                lib["arms"].append({**base,
                    "right_joints": r_joints,
                    "left_joints":  l_joints,
                })
                print(f"  ✓ Arms [{label}] [{category}]")

            if choice in ("h", "all"):
                lib["head"].append({**base, "angles": look})
                print(f"  ✓ Head [{label}] [{category}]")

            if choice in ("n", "all"):
                lib["antennas"].append({**base, "left": ant_l, "right": ant_r})
                print(f"  ✓ Antennas [{label}] [{category}]")

            save_library(lib)

        elif key in ('s', 'S'):
            save_library(lib)
            print(f"  Saved — arms:{len(lib['arms'])} head:{len(lib['head'])} antennas:{len(lib['antennas'])}")

        elif key in ('p', 'P'):
            print_summary(lib)

        elif key in ('q', 'Q', '\x03'):
            save_library(lib)
            print("\nSaved. Quitting.")
            reachyC.reachy.turn_off("reachy")
            reachyC.fans.turnOffAll()
            break



main()