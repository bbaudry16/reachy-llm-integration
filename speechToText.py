import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel


class SpeechToText:

    def __init__(self, model: str = "small", language: str = "en", sample_rate: int = 16000, device: str = "cpu", compute_type: str = "int8"):

        self.language = language
        self.sample_rate = sample_rate

        print(f"Loding Whisper '{model}'...")
        self._model = WhisperModel(model, device=device, compute_type=compute_type)
        print("Model loaded\n")

    def _record(self, silence_threshold: float = 0.07, silence_duration: float = 3.0, max_duration: float = 30.0) -> np.ndarray:
        
        chunk_size = int(self.sample_rate * 0.1)
        max_chunks = int(max_duration / 0.1)
        silent_chunks = int(silence_duration / 0.1)

        frames = []
        silent_count = 0
        recording = False

        print("Waiting for speech...", end="", flush=True)

        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32", blocksize=chunk_size) as stream:

            for _ in range(max_chunks):
                chunk, _ = stream.read(chunk_size)
                rms       = np.sqrt(np.mean(chunk ** 2))
                print(f"\rRMS: {rms:.4f}  silent_count: {silent_count}/{silent_chunks}    ", end="", flush=True)

                if rms > silence_threshold:
                    if not recording:
                        print("\Listening...      ", end="", flush=True)
                        recording = True
                    frames.append(chunk)
                    silent_count = 0

                elif recording:
                    frames.append(chunk)
                    if rms < silence_threshold:
                        silent_count += 1
                    if silent_count >= silent_chunks:
                        break
                
        return np.concatenate(frames, axis=0).flatten() if frames else np.array([])


    def listen(self, silence_threshold: float = 0.01, silence_duration: float = 1.5) -> str:
        
        audio = self._record(silence_threshold, silence_duration)

        if audio.size == 0:
            return ""

        segments, _ = self._model.transcribe(
            audio,
            language=None,
            beam_size=5,
            vad_filter=True,
            task="transcribe",
            initial_prompt="Transcribe exactly what is said without translating.",
        )

        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()