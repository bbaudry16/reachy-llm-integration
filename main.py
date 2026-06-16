from textToSpeech import PiperTTS
from mistral import MistralClient
from speechToText import SpeechToText
import libs.reachyController as reachy

import threading
import time
from faceDetector import FaceTracker

MODEL_LOCALISATION : str = "./model/en_GB-semaine-medium.onnx"
SPEAKER_ID : int = 3


def face_tracking_loop(reachyC, tracker, active_flag: threading.Event):
    SMOOTHING       = 0.5
    UPDATE_INTERVAL = 0.25
    MOVE_DURATION   = 0.22

    current = [1.0, 0.0, 0.0]
    look_thread = None

    def send_look(target, duration):
        reachyC.head.lookAt(target, duration=duration)

    while True:
        if active_flag.is_set():
            time.sleep(0.1)
            continue

        target = tracker.get_look_at_target()
        if target is not None:
            current = [
                current[i] * SMOOTHING + target[i] * (1 - SMOOTHING)
                for i in range(3)
            ]

            if look_thread is None or not look_thread.is_alive():
                look_thread = threading.Thread(
                    target=send_look,
                    args=(current[:], MOVE_DURATION),
                    daemon=True
                )
                look_thread.start()

        time.sleep(UPDATE_INTERVAL)


@reachy.actionRegistry.register_action("speak_a_text")
def speakAText(executor, params):
    if not reachy.Validator(params, "speak_a_text").require("text").validate():
        return

    text = params["text"]
    reachy.consoleManager.MKprint("saying line : " + str(text), "action", reachy.consoleManager.Color.BRIGHT_MAGENTA)
    piper.textToSpeech(text)


@reachy.actionRegistry.register_action("look_at_human")
def look_at_human(executor, params):
    if not reachy.Validator(params, "look_at_human").require("duration").require("timeout").require("fallback").validate():
        return

    duration = params.get("duration")
    timeout  = params.get("timeout")
    fallback = params.get("fallback")

    target  = None
    elapsed = 0.0
    step    = 0.05

    while elapsed < timeout:
        target = tracker.get_look_at_target()
        if target is not None:
            break
        time.sleep(step)
        elapsed += step

    reachy.consoleManager.MKprint("looking at human : " + str(target), "action", reachy.consoleManager.Color.BRIGHT_MAGENTA)
    if target is None:
        target = fallback

    executor.reachy.head.lookAt(target, duration=duration)


if __name__ == "__main__":

    reachyC = reachy.ReachyController.instanciate("10.59.1.20")
    piper   = PiperTTS(MODEL_LOCALISATION, SPEAKER_ID, 1)

    from prompt.test.best import SYSTEM_PROMPT
    client  = MistralClient(systemPrompt=SYSTEM_PROMPT)
    stt     = SpeechToText(model="small", language="")

    tracker = FaceTracker(reachyC, 10)
    tracker.start()

    llm_active = threading.Event()

    face_thread = threading.Thread(target=face_tracking_loop, args=(reachyC, tracker, llm_active), daemon=True)
    face_thread.start()

    reachyC.turnOn()

    on : bool = True
    stop : list = ["stop", "Stop.", "Stop", "stop..", "Stop ?"]
    while on:
        user_input = stt.listen(silence_threshold=0.03, silence_duration=1.5)

        reachyC.fans.tick()
        reachyC.fans.printState()

        if not user_input:
            continue
        if user_input in stop:
            on = False
            continue

        print(f"You : {user_input}")

        result = client.ask(user_input)
        speech = result.get("speech", "")
        ryi    = result.get("ryi", "")

        print(f"Reachy : {speech}")
        print(f"RYI :\n{ryi}\n")

        instructor = reachy.Instructor.loadFromString(ryi, reachyC)
        print(instructor.data)

        llm_active.set()
        if not instructor.data:
            piper.textToSpeech(speech)
        else:
            instructor.execute()
        llm_active.clear()

    reachyC.armLeft._debug_placeHandOnTable(3)
    reachyC.armRight._debug_placeHandOnTable(3)
    reachyC.turnOffSmooth()