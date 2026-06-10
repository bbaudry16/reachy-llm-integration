import sounddevice as sd
import numpy as np
from piper import PiperVoice
from piper.config import SynthesisConfig

class PiperTTS:

    SAMPLE_RATE = 22050

    def __init__(self, model: str, speaker: int = None, speed: float = 1.0):

        self.speaker = speaker
        self.speed = speed

        print(f"Loading piper voice'{model}'...")
        self.voice = PiperVoice.load(model)
        print("voice loaded.\n")

    def _synthesize(self, text: str) -> np.ndarray:
        from piper.config import SynthesisConfig
        config = SynthesisConfig(
            speaker_id=self.speaker,
            length_scale=self.speed,
        )
        
        chunks = []
        for audio_chunk in self.voice.synthesize(text, syn_config=config):
            chunks.append(np.frombuffer(audio_chunk.audio_int16_bytes, dtype=np.int16))

        if not chunks:
            return np.array([], dtype=np.int16)

        return np.concatenate(chunks)

    def textToSpeech(self, text: str) -> None:
        audio = self._synthesize(text)
        if audio.size == 0:
            return
        sd.play(audio, samplerate=self.voice.config.sample_rate)
        sd.wait()