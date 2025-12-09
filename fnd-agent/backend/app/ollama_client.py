from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


class OllamaClient:
    """
    Minimal HTTP client for a local Ollama instance.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
    ):
        self.model = model or os.getenv("FND_OLLAMA_MODEL", "llama3")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.temperature = temperature if temperature is not None else float(
            os.getenv("FND_OLLAMA_TEMPERATURE", "0.2")
        )

    def chat(self, messages: List[Dict[str, str]]) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": self.temperature,
            },
        }
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=float(os.getenv("FND_OLLAMA_TIMEOUT", "120")),
        )
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message") or {}
        content = message.get("content")
        if not content:
            raise RuntimeError("Ollama response did not include message content.")
        return content

