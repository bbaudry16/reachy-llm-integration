from textToSpeech import PiperTTS
from mistral import MistralClient

PIPIER_BIN_LOCALISATION : str = "./piper/piper"
MODEL_LOCALISATION : str = "./model/en_GB-semaine-medium.onnx"
SPEAKER_ID : int = 3

SYSTEM_PROMPT = """Tu es Reachy, un robot humanoïde bienveillant et curieux.
Tu réponds de façon concise et naturelle, comme si tu parlais à voix haute."""

if __name__ == "__main__":
    piper = PiperTTS(PIPIER_BIN_LOCALISATION, MODEL_LOCALISATION, SPEAKER_ID, 1)
    client = MistralClient(systemPrompt=SYSTEM_PROMPT, APIKey="bqOf6A5e1Sm08TqO4gd9M3DKWZhG5rNF")

    while True:
        user_input = input("Toi : ").strip()
        if not user_input or user_input.lower() in ("quit", "q"):
            break

        reply = client.ask(user_input)
        print(f"\nRéachy : {reply}\n")
        piper.textToSpeech(reply)