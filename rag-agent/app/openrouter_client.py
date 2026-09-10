import httpx

from app.config import settings


class OpenRouterClient:
    def __init__(self):
        self._client = httpx.Client(
            base_url=settings.openrouter_base_url,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            timeout=120.0,
        )

    def chat_completion(self, model: str, messages: list[dict], json_mode: bool = False) -> str:
        payload: dict = {"model": model, "messages": messages}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def close(self):
        self._client.close()


client = OpenRouterClient()
