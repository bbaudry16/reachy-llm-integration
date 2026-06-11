import os
import time
import requests
import json

class MistralClient:

    API_URL = "https://api.mistral.ai/v1/chat/completions"
    MODEL   = "mistral-small-2503"

    def __init__(self, systemPrompt: str, APIKey: str = None, maxTokens: int = 512, temperature: float = 0.7, historySize: int = 10, rateLimit: float = 1.1):

        self.APIKey = APIKey or os.environ.get("MISTRAL_API_KEY")
        self.systemPrompt = systemPrompt
        self.maxTokens = maxTokens
        self.temperature = temperature
        self.historySize = historySize
        self.rateLimit = rateLimit

        self.history : list  = []
        self._lastRequestTime : float = 0.0

    def _waitRateLimit(self) -> None:
        elapsed = time.time() - self._lastRequestTime
        if elapsed < self.rateLimit:
            time.sleep(self.rateLimit - elapsed)

    def _buildMessages(self, user_message: str) -> list:
        messages = [{"role": "system", "content": self.systemPrompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _updateHistory(self, user_message: str, reply: str) -> None:
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": reply})
        if len(self.history) > self.historySize:
            self.history = self.history[-self.historySize:]

    def ask(self, user_message: str) -> dict:
        self._waitRateLimit()

        headers = {"Authorization": f"Bearer {self.APIKey}", "Content-Type": "application/json"}
        payload = {
            "model":       self.MODEL,
            "messages":    self._buildMessages(user_message),
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }

        self._lastRequestTime = time.time()
        response = requests.post(self.API_URL, headers=headers, json=payload, timeout=30)
        if not response.ok:
            print(response.json())
            response.raise_for_status()

        raw = response.json()["choices"][0]["message"]["content"]

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {"speech": raw, "ryi": "reachy:\n- wait:\n    duration: 0.1"}

        self._updateHistory(user_message, result.get("speech", ""))
        return result

    def clearHistory(self) -> None:
        self.history = []