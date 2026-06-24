import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel


class SpeechToText:

    def __init__(self, model: str = "small", language: str = "en", sampleRate: int = 16000, device: str = "cpu", computeType: str = "int8"):
        self.language = language
        self.sampleRate = sampleRate
        self._model = WhisperModel(model, device=device, compute_type=computeType)

    def _record(self, silenceThreshold: float = 0.07, silenceDuration: float = 3.0, maxDuration: float = 30.0) -> np.ndarray:
        chunkSize = int(self.sampleRate * 0.1)
        maxChunks = int(maxDuration / 0.1)
        silentChunks = int(silenceDuration / 0.1)
        frames = []
        silentCount = 0
        recording = False
        print("[STT] listening...", flush=True)
        with sd.InputStream(samplerate=self.sampleRate, channels=1, dtype="float32", blocksize=chunkSize) as stream:
            for _ in range(maxChunks):
                chunk, _ = stream.read(chunkSize)
                rms = np.sqrt(np.mean(chunk ** 2))
                if rms > silenceThreshold:
                    if not recording:
                        print("[STT] recording...", flush=True)
                        recording = True
                    frames.append(chunk)
                    silentCount = 0
                elif recording:
                    frames.append(chunk)
                    if rms < silenceThreshold:
                        silentCount += 1
                    if silentCount >= silentChunks:
                        print(f"[STT] silence detected ({silentCount} chunks) — stopping", flush=True)
                        break
        return np.concatenate(frames, axis=0).flatten() if frames else np.array([])

    def listen(self, silenceThreshold: float = 0.01, silenceDuration: float = 1.5) -> str:
        audio = self._record(silenceThreshold, silenceDuration)
        if audio.size == 0:
            print("[STT] no audio captured", flush=True)
            return ""
        print(f"[STT] transcribing {len(audio) / self.sampleRate:.1f}s of audio...", flush=True)
        segments, _ = self._model.transcribe(audio, language=None, beam_size=5, vad_filter=True, task="transcribe", initial_prompt="Transcribe exactly what is said without translating.")
        text = " ".join(s.text.strip() for s in segments).strip()
        print(f"[STT] heard: {text!r}", flush=True)
        return text