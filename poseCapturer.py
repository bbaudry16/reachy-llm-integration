"""
Pose Capture Tool
Controls:
  1      → toggle stiff/compliant  RIGHT arm
  2      → toggle stiff/compliant  LEFT arm
  3      → toggle stiff/compliant  HEAD
  SPACE  → capture current pose (arms + head look_at)
  S      → save all captures to poses.json
  Q      → quit
"""

import json
import sys
import tty
import termios


def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def set_stiff(joints, stiff: bool):
    for j in joints.values():
        j.compliant = not stiff


def capture(reachyC):
    # Arms — cartesian + orientation
    rpos = reachyC.armRight.getHandPosition()
    lpos = reachyC.armLeft.getHandPosition()

    def get_ori(arm):
        joints = list(arm._reachyArm.joints.values())
        wr = next((j.present_position for j in joints if "wrist_roll"  in j.name), 0.0)
        fy = next((j.present_position for j in joints if "forearm_yaw" in j.name), 0.0)
        return round(wr, 1), round(fy, 1)

    rwr, rfy = get_ori(reachyC.armRight)
    lwr, lfy = get_ori(reachyC.armLeft)

    # Head — forward kinematic gives look_at [x, y, z]
    look = reachyC.head.forwardKinematic(distance=1.0)

    return {
        "right": {
            "position":    [round(v, 3) for v in rpos],
            "orientation": [round(rwr, 1), 0, round(rfy, 1)],
        },
        "left": {
            "position":    [round(v, 3) for v in lpos],
            "orientation": [round(-lwr, 1), 0, round(-lfy, 1)],
        },
        "look_at": [round(v, 3) for v in look],
    }


def print_capture(idx, data):
    r  = data["right"]["position"]
    ro = data["right"]["orientation"]
    l  = data["left"]["position"]
    lo = data["left"]["orientation"]
    g  = data["look_at"]
    print(f"[{idx}] captured")
    print(f"      R: [{r[0]:.3f}, {r[1]:.3f}, {r[2]:.3f}]  ori:{ro}")
    print(f"      L: [{l[0]:.3f}, {l[1]:.3f}, {l[2]:.3f}]  ori:{lo}")
    print(f"      look_at: [{g[0]:.3f}, {g[1]:.3f}, {g[2]:.3f}]")


def main():
    import libs.reachyController as reachy
    print("Connecting to Reachy...")
    reachyC = reachy.ReachyController.instanciate("10.59.1.20")

    # Start compliant (motors off)
    reachyC.reachy.turn_off("reachy")

    stiff = {"right": False, "left": False, "head": False}

    right_joints = reachyC.armRight._reachyArm.joints
    left_joints  = reachyC.armLeft._reachyArm.joints
    head_joints  = reachyC.head._disks

    captures = []

    print("\nPose Capture — all parts start COMPLIANT (free to move)")
    print("  1     → toggle RIGHT arm  stiff/compliant")
    print("  2     → toggle LEFT arm   stiff/compliant")
    print("  3     → toggle HEAD       stiff/compliant")
    print("  SPACE → capture pose")
    print("  S     → save to poses.json")
    print("  Q     → quit\n")

    while True:
        key = get_key()

        if key == '1':
            stiff["right"] = not stiff["right"]
            set_stiff(right_joints, stiff["right"])
            state = "STIFF" if stiff["right"] else "compliant"
            print(f"  RIGHT arm → {state}")

        elif key == '2':
            stiff["left"] = not stiff["left"]
            set_stiff(left_joints, stiff["left"])
            state = "STIFF" if stiff["left"] else "compliant"
            print(f"  LEFT arm  → {state}")

        elif key == '3':
            stiff["head"] = not stiff["head"]
            set_stiff(head_joints, stiff["head"])
            state = "STIFF" if stiff["head"] else "compliant"
            print(f"  HEAD      → {state}")

        elif key == ' ':
            data = capture(reachyC)
            captures.append(data)
            print_capture(len(captures), data)

        elif key in ('s', 'S'):
            path = "poses.json"
            with open(path, "w") as f:
                json.dump(captures, f, indent=2)
            print(f"\n  Saved {len(captures)} pose(s) to {path}")

        elif key in ('q', 'Q', '\x03'):
            print("\nQuitting — turning off Reachy.")
            reachyC.reachy.turn_off("reachy")
            break


main()