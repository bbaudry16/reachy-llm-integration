import re
import time


_POSE_TO_MOOD: dict[str, str] = {
    # Arms
    "shocked":    "shocked",
    "suprised":   "surprised",
    "excited":    "excited",
    "wonderful":  "wonder",
    "confused":   "curious",
    "happy":      "happy",
    "thinking":   "thoughtful",
    "sad":        "sad",
    "defeated":   "defeated",
    # Head
    "depressed":  "defeated",
    "curious":    "curious",
    "shy":        "shy",
    "angry":      "angry",
    "pissed":     "angry",
    # Antennas
    "panicking":  "panicking",
    "crazy":      "playful",
}

_MOOD_DECAY_TURNS: int = 4

_INTENSITY_THRESHOLD: float = 0.25

_MOOD_DESCRIPTIONS: dict[str, str] = {
    "shocked":    "You are still reeling from shock — wide-eyed, almost speechless.",
    "surprised":  "You are still buzzing with surprise — things are not quite settled.",
    "excited":    "You are riding a wave of excitement — energetic, almost bouncy.",
    "wonder":     "You are in a state of wonder — slow, reverent, deeply impressed.",
    "curious":    "You are genuinely curious — leaning in, wanting to know more.",
    "happy":      "You feel warm and joyful — light, open, genuinely pleased.",
    "thoughtful": "You are in a reflective mood — measured, a little inward.",
    "sad":        "There is a quiet sadness in you — not dramatic, just present.",
    "defeated":   "You feel low and heavy — not broken, but certainly not cheerful.",
    "shy":        "You feel a little bashful — slightly withdrawn, softer than usual.",
    "angry":      "There is irritation simmering — you are not in the mood for nonsense.",
    "panicking":  "You are still on edge — nerves not quite settled, a little twitchy.",
    "playful":    "You are in a goofy, playful mood — lighthearted and a bit silly.",
    "neutral":    ""
}


class MoodTracker:
    """Tracks Reachy's emotional state across conversation turns."""

    def __init__(self, decay_turns: int = _MOOD_DECAY_TURNS):
        self.decay_turns   = decay_turns
        self.mood          = "neutral"
        self.intensity     = 0.0
        self._turns_since  = 0
        self._history: list[tuple[str, float]] = []

    def update_from_response(self, result: dict) -> None:
        """
        Parse a Mistral result dict (keys: speech, ryi) and update mood.
        Call this immediately after client.ask().
        """
        ryi    = result.get("ryi", "")
        speech = result.get("speech", "")

        detected = self._detect_mood(ryi, speech)

        if detected and detected != "neutral":
            self.mood         = detected
            self.intensity    = 1.0
            self._turns_since = 0
        else:
            self._decay()

        self._history.append((self.mood, self.intensity))
        if len(self._history) > 20:
            self._history = self._history[-20:]

    def build_context_message(self) -> dict | None:

        effective_intensity = self.intensity * self._decay_factor()

        if effective_intensity < _INTENSITY_THRESHOLD or self.mood == "neutral":
            return None

        desc = _MOOD_DESCRIPTIONS.get(self.mood, "")
        if not desc:
            return None

        percent = int(effective_intensity * 100)
        lines = [
            "═══ YOUR CURRENT EMOTIONAL STATE ═══",
            f"Mood     : {self.mood}  (intensity {percent}%)",
            f"Context  : {desc}",
            "",
            "This mood colours your NEXT response. You do not need to mention it",
            "explicitly — let it show through your pose choices and speech tone.",
            "If the new topic naturally shifts your mood, allow the transition.",
            "═════════════════════════════════════",
        ]
        return {"role": "system", "content": "\n".join(lines)}

    def force_mood(self, mood: str, intensity: float = 1.0) -> None:
        self.mood         = mood
        self.intensity    = max(0.0, min(1.0, intensity))
        self._turns_since = 0

    def reset(self) -> None:
        self.mood         = "neutral"
        self.intensity    = 0.0
        self._turns_since = 0

    def __repr__(self) -> str:
        return (f"MoodTracker(mood={self.mood!r}, "
                f"intensity={self.intensity:.2f}, "
                f"turns_since={self._turns_since})")


    def _detect_mood(self, ryi: str, speech: str) -> str:

        for label, mood in _POSE_TO_MOOD.items():
            pattern = rf'(?<![a-z_]){re.escape(label)}(?![a-z_])'
            if re.search(pattern, ryi, re.IGNORECASE):
                return mood

        if "vibrate_antenna" in ryi:
            return "excited"

        low = speech.lower()
        if any(w in low for w in ("wonderful", "amazing", "incredible", "wow")):
            return "wonder"
        if any(w in low for w in ("oh!", "oh no", "wait!", "what?!")):
            return "surprised"
        if any(w in low for w in ("sorry", "sad", "unfortunately", "ah...")):
            return "sad"
        if any(w in low for w in ("ha!", "haha", "funny", "silly")):
            return "playful"

        return "neutral"

    def _decay(self) -> None:
        self._turns_since += 1
        self.intensity = max(0.0, self.intensity * self._decay_factor())
        if self.intensity < _INTENSITY_THRESHOLD:
            self.mood      = "neutral"
            self.intensity = 0.0

    def _decay_factor(self) -> float:
        """Exponential decay: intensity halves every decay_turns turns."""
        return 0.5 ** (self._turns_since / max(1, self.decay_turns))