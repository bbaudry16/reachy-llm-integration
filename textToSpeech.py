import sounddevice as sd
import numpy as np
from piper import PiperVoice
from piper.config import SynthesisConfig


class TextToSpeech:

    def __init__(self, model: str, speaker: int = None, speed: float = 1.0):
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
        audio = self._synthesize(text)
        if audio.size == 0:
            return
        sd.play(audio, samplerate=self.voice.config.sample_rate)
        sd.wait()