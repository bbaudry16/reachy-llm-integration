import re

_SPEECH_TIMING: list[tuple[int, float]] = [
    (5,  1.0),
    (8,  1.5),
    (11, 2.0),
]
_SPEECH_BUFFER = 0.2
_MIN_MOTION_DURATION = 0.4
_MAX_MOTION_DURATION = 2.0

_SLOW_POSES_MIN = 1.0
_SLOW_POSE_LABELS = {"suprised", "shocked"}

_MOTION_ACTIONS = {
    "move_joints",
    "move_head",
    "look_at_human",
    "set_antenna",
}


def _speech_duration(text: str) -> float:
    words = len(text.split())
    for limit, duration in _SPEECH_TIMING:
        if words <= limit:
            return duration
    return _SPEECH_TIMING[-1][1]


def _contains_slow_pose(block_text: str) -> bool:
    low = block_text.lower()
    return any(label in low for label in _SLOW_POSE_LABELS)


class YamlTimingFixer:
    """
    Corrects motion durations in LLM-generated YAML so they outlast speech.

    For each parallel block, durations are bumped to at least
    speech_duration + buffer. Slow poses (suprised, shocked) enforce
    an additional minimum duration.
    """

    def __init__(
        self,
        buffer: float = _SPEECH_BUFFER,
        min_duration: float = _MIN_MOTION_DURATION,
        max_duration: float = _MAX_MOTION_DURATION,
        slow_pose_min: float = _SLOW_POSES_MIN,
        verbose: bool = False,
    ):
        """
        @param buffer: Extra seconds added on top of speech duration.
        @type buffer: float
        @param min_duration: Absolute minimum motion duration in seconds.
        @type min_duration: float
        @param max_duration: Absolute maximum motion duration in seconds.
        @type max_duration: float
        @param slow_pose_min: Minimum duration enforced for slow poses.
        @type slow_pose_min: float
        @param verbose: Print corrections to stdout when True.
        @type verbose: bool
        """
        self.buffer       = buffer
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.slow_min     = slow_pose_min
        self.verbose      = verbose

        self._dur_re = re.compile(r'(duration:\s*)(\d+(?:\.\d+)?)')

    def fix(self, ryi: str) -> str:
        """
        Apply timing corrections to the full YAML string.

        @param ryi: Raw YAML string from the LLM.
        @type ryi: str
        @return: Corrected YAML string.
        @rtype: str
        """
        if not ryi or "parallel:" not in ryi:
            return ryi

        blocks = self._split_parallel_blocks(ryi)
        if not blocks:
            return ryi

        result_parts: list[str] = []
        for block in blocks:
            result_parts.append(self._fix_block(block))

        fixed = "".join(result_parts)

        if self.verbose and fixed != ryi:
            print("[YamlTimingFixer] Timing corrections applied.")

        return fixed

    def _split_parallel_blocks(self, ryi: str) -> list[str]:
        positions = [m.start() for m in re.finditer(r'- parallel:', ryi)]
        if not positions:
            return [ryi]

        segments: list[str] = []
        for i, pos in enumerate(positions):
            if i == 0 and pos > 0:
                segments.append(ryi[:pos])
            end = positions[i + 1] if i + 1 < len(positions) else len(ryi)
            segments.append(ryi[pos:end])

        return segments

    def _fix_block(self, block: str) -> str:
        if "parallel:" not in block:
            return block

        speech_match = re.search(
            r'speak_a_text:\s*\n\s+text:\s*["\']?(.*?)["\']?\s*$',
            block, re.MULTILINE
        )
        if not speech_match:
            if _contains_slow_pose(block):
                return self._bump_durations(block, self.slow_min)
            return block

        speech_text  = speech_match.group(1).strip().strip('"\'')
        required_dur = _speech_duration(speech_text) + self.buffer

        if _contains_slow_pose(block):
            required_dur = max(required_dur, self.slow_min)

        return self._bump_durations(block, required_dur)

    def _bump_durations(self, block: str, min_dur: float) -> str:
        def replacer(m: re.Match) -> str:
            prefix  = m.group(1)
            current = float(m.group(2))
            fixed = min(self.max_duration, max(min_dur, current))
            if fixed != current and self.verbose:
                print(f"  [timing] duration {current:.2f}s -> {fixed:.2f}s")
            return f"{prefix}{fixed:.2f}"

        pattern = re.compile(r'(?<!step_)(duration:\s*)(\d+(?:\.\d+)?)')
        return pattern.sub(replacer, block)


if __name__ == "__main__":
    sample = """reachy:
- parallel:
    - speak_a_text:
        text: "Oh, that is absolutely wonderful, I love it!"
    - look_at_human:
        duration: 0.5
        timeout: 1.5
        fallback: [1, 0, 0]
    - move_joints:
        arm: right
        joints: [-40.86, -1.12, 2.15, -80.84, 3.47, 7.16, -1.03, 16.35]
        duration: 0.5
    - move_joints:
        arm: left
        joints: [-41.38, 3.32, 2.59, -80.22, 2.51, -0.22, -0.73, -18.7]
        duration: 0.5
    - set_antenna:
        antenna: left
        angle: 25
        duration: 0.4
- parallel:
    - speak_a_text:
        text: "Wait!"
    - move_joints:
        arm: right
        joints: [-78.39, -3.58, -1.71, -66.07, 2.95, 4.53, -1.03, 16.35]
        duration: 0.6
"""

    fixer = YamlTimingFixer(verbose=True)
    fixed = fixer.fix(sample)
    print(fixed)