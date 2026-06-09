from RealtimeSTT import AudioToTextRecorder

class RealtimeSTTClient:

    def __init__(self, model: str = "small", language: str = "fr",
                 on_text: callable = None):
        """
        model    : "tiny", "base", "small", "medium" (plus grand = plus précis mais plus lent)
        language : "fr", "en", etc. (None = détection automatique)
        on_text  : callback appelé dès qu'une phrase est reconnue
        """
        self.on_text = on_text or (lambda text: print(f"[STT] {text}"))

        self._recorder = AudioToTextRecorder(
            model=model,
            language=language,
            spinner=False,
        )

    def listen(self) -> str:
        return self._recorder.text()

    def listenLoop(self) -> None:
        while True:
            text = self._recorder.text()
            if text:
                self.on_text(text)

    def shutdown(self) -> None:
        self._recorder.shutdown()