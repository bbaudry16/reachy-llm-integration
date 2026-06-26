import sounddevice as sd
import numpy as np
from piper import PiperVoice
from piper.config import SynthesisConfig


class TextToSpeech:
    """
    Synthesizes speech using a Piper voice model and plays it through the default audio device.

    @ivar speaker: Speaker ID used for multi-speaker models.
    @ivar speed: Length scale applied during synthesis (lower is faster).
    @type speed: float
    """

    def __init__(self, model: str, speaker: int = None, speed: float = 1.0):
        """
        @param model: Path to the Piper .onnx model file.
        @type model: str
        @param speaker: Speaker ID for multi-speaker models.
        @type speaker: int
        @param speed: Synthesis speed scale factor.
        @type speed: float
        """
        self.speaker = speaker
        self.speed = speed
        self.voice = PiperVoice.load(model)

    def _synthesize(self, text: str) -> np.ndarray:
        config = SynthesisConfig(speaker_id=self.speaker, length_scale=self.speed)
        chunks = []
        for audioChunk in self.voice.synthesize(text, syn_config=config):
            chunks.append(np.frombuffer(audioChunk.audio_int16_bytes, dtype=np.int16))
        if not chunks:
            return np.array([], dtype=np.int16)
        return np.concatenate(chunks)

    def textToSpeech(self, text: str) -> None:
        """
        Synthesize and play the given text.

        @param text: Text to speak.
        @type text: str
        """
        audio = self._synthesize(text)
        if audio.size == 0:
            return
        sd.play(audio, samplerate=self.voice.config.sample_rate)
        sd.wait()