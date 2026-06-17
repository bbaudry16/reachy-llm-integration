"""
Animation Recorder — builds animations keyframe by keyframe.

Workflow:
  1. Toggle stiff/compliant per part (R / L / H)
  2. Move the robot to a pose manually
  3. Press SPACE to capture that keyframe
  4. Repeat for each keyframe
  5. Press ENTER to finish and save the animation

Controls:
  R      → toggle RIGHT arm   stiff/compliant
  L      → toggle LEFT arm    stiff/compliant
  H      → toggle HEAD        stiff/compliant
  SPACE  → capture current pose as a keyframe
  ENTER  → finish current animation (annotate + save)
  U      → undo last keyframe
  P      → preview current keyframes on the robot
  C      → clear all keyframes (start over)
  D      → display library summary
  Q      → quit
"""

import json, sys, tty, termios, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ANIMATION_FILE = "animations_library.json"
CATEGORIES     = ("emotion", "conversational")

JOINT_ORDER = [
    "shoulder_pitch", "shoulder_roll", "arm_yaw",
    "elbow_pitch", "forearm_yaw",
    "wrist_pitch", "wrist_roll", "gripper"
]


# ─── Terminal helpers ──────────────────────────────────────────────────────────

def get_key():
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def get_line(prompt: str) -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return sys.stdin.readline().strip()


# ─── Stiffness ────────────────────────────────────────────────────────────────

def set_stiff(joint_dict, stiff: bool):
    for j in joint_dict.values():
        j.compliant = not stiff


# ─── Capture helpers ──────────────────────────────────────────────────────────

def capture_arm(arm, arm_id: str) -> list:
    result = []
    for name in JOINT_ORDER:
        sided = f"{arm_id}_{name}"
        j     = arm._joints.get(sided)
        result.append(round(j.present_position, 2) if j else 0.0)
    return result


def capture_head(reachyC) -> list:
    return [round(j.present_position, 2) for j in reachyC.head.getDisksInOrder()]


# ─── Library I/O ──────────────────────────────────────────────────────────────

def load_library() -> dict:
    if not Path(ANIMATION_FILE).exists():
        return {"animations": []}
    try:
        content = Path(ANIMATION_FILE).read_text().strip()
        return json.loads(content) if content else {"animations": []}
    except json.JSONDecodeError:
        return {"animations": []}


def save_library(lib: dict):
    with open(ANIMATION_FILE, "w") as f:
        json.dump(lib, f, indent=2, ensure_ascii=False)
    print(f"  Saved {len(lib['animations'])} animation(s) to {ANIMATION_FILE}")


def print_summary(lib: dict):
    print("\n── Animation Library ────────────────────────────────────")
    anims = lib.get("animations", [])
    if not anims:
        print("  (empty)")
    for cat in CATEGORIES:
        group = [a for a in anims if a.get("category") == cat]
        if not group:
            continue
        print(f"  [{cat}]")
        for a in group:
            parts      = a.get("parts", [])
            keyframes  = len(a.get("keyframes", []))
            step       = a.get("step_duration", "?")
            dur        = round(keyframes * step, 2) if isinstance(step, (int, float)) else "?"
            print(f"    {a['label']:<20} keyframes:{keyframes}  step:{step}s  dur:{dur}s  parts:{parts}")
            if a.get("description"):
                print(f"    {'':20} → {a['description']}")
    print("─────────────────────────────────────────────────────────\n")


# ─── Preview ──────────────────────────────────────────────────────────────────

def preview_keyframes(reachyC, keyframes: list, parts: list, step_duration: float):
    from reachy_sdk import trajectory as _traj

    if not keyframes:
        print("  No keyframes to preview.")
        return

    print(f"  ▶ Previewing {len(keyframes)} keyframes @ {step_duration}s/step...")

    # Go to first keyframe safely
    first = keyframes[0]
    moves = []
    if "right" in parts and "right" in first:
        jd = {j: v for j, v in zip(reachyC.armRight.getJointsInOrder(), first["right"])}
        reachyC.armRight.safeGoto(jd, duration=1.5)
    if "left" in parts and "left" in first:
        jd = {j: v for j, v in zip(reachyC.armLeft.getJointsInOrder(), first["left"])}
        reachyC.armLeft.safeGoto(jd, duration=1.5)
    if "head" in parts and "head" in first:
        disks = reachyC.head.getDisksInOrder()
        _traj.goto({d: a for d, a in zip(disks, first["head"])}, duration=1.5)

    # Play each keyframe
    for i, kf in enumerate(keyframes):
        t0 = time.time()

        def _right(kf=kf):
            if "right" in parts and "right" in kf:
                jd = {j: v for j, v in zip(reachyC.armRight.getJointsInOrder(), kf["right"])}
                reachyC.armRight.safeGoto(jd, step_duration)

        def _left(kf=kf):
            if "left" in parts and "left" in kf:
                jd = {j: v for j, v in zip(reachyC.armLeft.getJointsInOrder(), kf["left"])}
                reachyC.armLeft.safeGoto(jd, step_duration)

        def _head(kf=kf):
            if "head" in parts and "head" in kf:
                disks = reachyC.head.getDisksInOrder()
                _traj.goto({d: a for d, a in zip(disks, kf["head"])}, duration=step_duration)

        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(_right), pool.submit(_left), pool.submit(_head)]
            for f in futs:
                f.result()

        print(f"  [{i+1}/{len(keyframes)}]", end="\r")

    print(f"\n  ▶ Done.")


# ─── Annotation helpers ───────────────────────────────────────────────────────

def ask_parts() -> list:
    print("  Parts captured in each keyframe?")
    print("  r=right arm  l=left arm  h=head  (combine: rl / rh / lh / rlh)")
    raw   = get_line("  → ").lower().strip()
    parts = []
    if "r" in raw: parts.append("right")
    if "l" in raw: parts.append("left")
    if "h" in raw: parts.append("head")
    if not parts:
        print("  Nothing selected — defaulting to right+left+head")
        parts = ["right", "left", "head"]
    return parts


def ask_step_duration() -> float:
    raw = get_line("  Step duration in seconds (Enter = 0.5): ").strip()
    try:
        v = float(raw)
        return v if v > 0 else 0.5
    except ValueError:
        return 0.5


def ask_category() -> str:
    while True:
        raw = get_line("  Category (e=emotion / c=conversational): ").strip().lower()
        if raw in ("e", "emotion"):        return "emotion"
        if raw in ("c", "conversational"): return "conversational"
        print("  → type 'e' or 'c'")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    import libs.reachyController as reachy

    print("Connecting to Reachy...")
    reachyC = reachy.ReachyController.instanciate("10.59.1.20")
    reachyC.reachy.turn_off("reachy")

    stiff = {"right": False, "left": False, "head": False}
    right_joints = reachyC.armRight._joints
    left_joints  = reachyC.armLeft._joints
    head_joints  = reachyC.head._disks

    lib       = load_library()
    keyframes = []   # current session keyframes

    print(f"\nAnimation Recorder — {ANIMATION_FILE}")
    print("  R=right  L=left  H=head  SPACE=capture keyframe")
    print("  ENTER=finish+save  U=undo  P=preview  C=clear  D=summary  Q=quit\n")
    print_summary(lib)

    while True:
        key = get_key()

        # ── Stiffness toggles ──────────────────────────────────────────────────
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

        # ── Capture keyframe ───────────────────────────────────────────────────
        elif key == ' ':
            kf = {
                "right": capture_arm(reachyC.armRight, "r"),
                "left":  capture_arm(reachyC.armLeft,  "l"),
                "head":  capture_head(reachyC),
            }
            keyframes.append(kf)
            idx = len(keyframes)
            print(f"  ● Keyframe {idx} captured")
            print(f"    R: {kf['right']}")
            print(f"    L: {kf['left']}")
            print(f"    H: {kf['head']}")

        # ── Undo last keyframe ─────────────────────────────────────────────────
        elif key in ('u', 'U'):
            if keyframes:
                keyframes.pop()
                print(f"  ↩ Undo — {len(keyframes)} keyframe(s) remaining")
            else:
                print("  Nothing to undo.")

        # ── Preview ───────────────────────────────────────────────────────────
        elif key in ('p', 'P'):
            if not keyframes:
                print("  No keyframes yet.")
            else:
                parts         = ask_parts()
                step_duration = ask_step_duration()
                reachyC.reachy.turn_on("reachy")
                time.sleep(0.3)
                preview_keyframes(reachyC, keyframes, parts, step_duration)
                reachyC.reachy.turn_off("reachy")

        # ── Finish + save ──────────────────────────────────────────────────────
        elif key in ('\r', '\n'):
            if not keyframes:
                print("  No keyframes to save.")
                continue

            print(f"\n  Finishing animation with {len(keyframes)} keyframe(s).")
            parts         = ask_parts()
            step_duration = ask_step_duration()
            label         = get_line("  Label: ").strip()
            if not label:
                print("  No label — not saved.")
                continue
            desc     = get_line("  Description (Enter to skip): ").strip()
            category = ask_category()

            anim = {
                "label":         label,
                "category":      category,
                "description":   desc,
                "parts":         parts,
                "step_duration": step_duration,
                "timestamp":     time.time(),
                "keyframes":     [
                    {p: kf[p] for p in parts if p in kf}
                    for kf in keyframes
                ],
            }

            lib["animations"].append(anim)
            save_library(lib)
            print(f"  ✓ Saved [{label}] [{category}]  {len(keyframes)} keyframes  step:{step_duration}s")
            keyframes = []   # reset for next animation

        # ── Clear ─────────────────────────────────────────────────────────────
        elif key in ('c', 'C'):
            keyframes = []
            print("  ✗ Cleared — 0 keyframes.")

        # ── Summary ───────────────────────────────────────────────────────────
        elif key in ('d', 'D'):
            print_summary(lib)

        # ── Quit ──────────────────────────────────────────────────────────────
        elif key in ('q', 'Q', '\x03'):
            if keyframes:
                print(f"  Warning: {len(keyframes)} unsaved keyframes will be lost.")
            save_library(lib)
            print("\nSaved. Quitting.")
            reachyC.reachy.turn_off("reachy")
            break


main()