"""Minimal LLM client for any OpenAI-compatible chat API (OpenAI, Groq, OpenRouter, Gemini's
OpenAI-compatible endpoint, a local Ollama server, ...). Uses only the standard library.

Configure with environment variables or a `.env` file in the project root:
    LLM_API_KEY   (or OPENAI_API_KEY)   required - without it the bot falls back to rules
    LLM_BASE_URL  default https://api.openai.com/v1
    LLM_MODEL     default gpt-4o-mini
"""
import json
import os
import pathlib
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]


class LLMError(Exception):
    pass


def load_dotenv(path: pathlib.Path = ROOT / ".env"):
    """Tiny .env reader (KEY=value lines); real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class LLMClient:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini", timeout: int = 40):
        self.api_key, self.base_url, self.model, self.timeout = api_key, base_url.rstrip("/"), model, timeout

    @classmethod
    def from_env(cls):
        """Returns a client, or None when no API key is configured."""
        load_dotenv()
        key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not key:
            return None
        return cls(key, os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"), os.environ.get("LLM_MODEL", "gpt-4o-mini"))

    def __call__(self, messages: list[dict], temperature: float = 0.2) -> str:
        body = json.dumps({"model": self.model, "messages": messages, "temperature": temperature}).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            raise LLMError(f"LLM HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}") from e
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as e:
            raise LLMError(f"LLM call failed: {e}") from e
