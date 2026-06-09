import subprocess
import sounddevice as sd
import numpy as np

class PiperTTS:

    def __init__(self, piper_bin: str, model: str, speaker: int = None, speed: float = 1.0):
        self.piper_bin = piper_bin
        self.model     = model
        self.speaker   = speaker
        self.speed     = speed

    def _synthesize(self, text: str, speed: float = None, speaker: int = None) -> bytes:
        """
        call piper binary and get an audio file
        """
        cmd = [
            self.piper_bin,
            "--model",
            self.model,
            "--output_raw",
            "--length_scale",
            str(speed or self.speed),
        ]

        if (speaker or self.speaker) is not None:
            cmd += ["--speaker", str(speaker or self.speaker)]

        result = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            capture_output=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Piper error : {result.stderr.decode()}")

        return result.stdout
    
    def _playPCM(self, pcmBytes):
        audio = np.frombuffer(pcmBytes, dtype=np.int16)
        sd.play(audio, samplerate=22050)
        sd.wait()
    
    def textToSpeech(self, text : str):
        self._playPCM(self._synthesize(text))
        