import threading
import time

import libs.reachyController as reachyLib
from textToSpeech import TextToSpeech
from speechToText import SpeechToText
from mistral import MistralClient
from faceDetector import FaceTracker
from actions import ActionContext, registerActions
from promptBuilder import buildSystemPrompt

MODEL_PATH = "./model/en_GB-semaine-medium.onnx"
SPEAKER_ID = 3
REACHY_IP = "localhost"
USE_VOICE = False

STOP_WORDS = ["stop", "Stop.", "Stop", "stop..", "Stop ?"]

FACE_SMOOTHING = 0.5
FACE_UPDATE_INTERVAL = 0.25
FACE_MOVE_DURATION = 0.22


def faceTrackingLoop(reachyC, tracker: FaceTracker, pauseFlag: threading.Event) -> None:
    current = [1.0, 0.0, 0.0]
    lookThread = None

    def sendLook(target, duration):
        reachyC.head.lookAt(target, duration=duration)

    while True:
        if pauseFlag.is_set():
            time.sleep(0.1)
            continue
        target = tracker.getLookAtTarget()
        if target is not None:
            current = [current[i] * FACE_SMOOTHING + target[i] * (1 - FACE_SMOOTHING) for i in range(3)]
            if lookThread is None or not lookThread.is_alive():
                lookThread = threading.Thread(target=sendLook, args=(current[:], FACE_MOVE_DURATION), daemon=True)
                lookThread.start()
        time.sleep(FACE_UPDATE_INTERVAL)


if __name__ == "__main__":
    reachyC = reachyLib.ReachyController.instanciate(REACHY_IP)
    tts = TextToSpeech(MODEL_PATH, SPEAKER_ID, 1)
    stt = SpeechToText(model="small", language="")

    tracker = None
    if USE_VOICE and REACHY_IP != "10.59.1.20":
        tracker = FaceTracker(reachyC, 10)
        tracker.start()

    ctx = ActionContext(piper=tts, tracker=tracker)
    registerActions(ctx, reachyLib.actionRegistry.ACTION_REGISTRY)

    systemPrompt = buildSystemPrompt()
    client = MistralClient(systemPrompt=systemPrompt)

    llmActive = threading.Event()

    if tracker is not None:
        faceThread = threading.Thread(target=faceTrackingLoop, args=(reachyC, tracker, llmActive), daemon=True)
        faceThread.start()

    reachyC.turnOn()
    running = True

    while False:
        if USE_VOICE:
            userInput = stt.listen(silenceThreshold=0.03, silenceDuration=1.5)
        else:
            userInput = input("you: ")

        reachyC.fans.tick()

        if not userInput:
            continue
        if userInput in STOP_WORDS:
            running = False
            continue

        result = client.ask(userInput)
        speech = result.get("speech", "")
        ryi = result.get("ryi", "")

        print(ryi)

        instructor = reachyLib.Instructor.loadFromString(ryi, reachyC)

        llmActive.set()
        if not instructor.data:
            tts.speak(speech)
        else:
            instructor.execute()
        llmActive.clear()

    reachyC.armLeft._debug_placeHandOnTable(3)
    reachyC.armRight._debug_placeHandOnTable(3)
    reachyC.turnOffSmooth()