import os
import time
import requests

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
MODEL = "mistral-small-2503"
API_URL = "https://api.mistral.ai/v1/chat/completions"

SYSTEM_PROMPT = """Tu es Reachy, un robot humanoïde bienveillantn curieux, très émotionnel. Tu réponds de façon concise et naturelle, comme si tu parlais à voix haute."""


def ask_mistral(user_message: str, history: list = None) -> str:

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 256,
        "temperature": 0.7,
    }

    response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]


def chat_loop():
    history = []
    last_request_time = 0.0
    
    while True:
        user_input = input("Toi : ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break

        elapsed = time.time() - last_request_time
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)

        try:
            last_request_time = time.time()
            reply = ask_mistral(user_input, history)
            print(f"\nRéachy : {reply}\n")

            history.append({"role": "user",      "content": user_input})
            history.append({"role": "assistant",  "content": reply})

            if len(history) > 20:
                history = history[-20:]

        except requests.HTTPError as e:
            print(f"[Erreur HTTP] {e.response.status_code} : {e.response.text}")
        except Exception as e:
            print(f"[Erreur] {e}")