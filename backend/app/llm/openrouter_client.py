import requests

from app.config import OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_URL

class LLMError(Exception):
    """Raised when open router fails or returns an unusable response"""

def chat(message: list[dict],
         model: str| None = None,
         temperature: float = 0.0,
         max_tokens: int = 1200,
         timeout: int = 60
        ) -> str:

        """Send a chat completion request and return the assistant's text.

            `messages` is the standard [{"role": "system"|"user"|"assistant", "content": ...}].
            temperature defaults to 0 — for grounded legal answers we want repeatability,
            not creativity.
        """ 
        if not OPENROUTER_API_KEY:
            raise LLMError("OPENROUTER_API_KEY is not set in backend/.env")

        payload = {
              "model": model or OPENROUTER_MODEL,
              # Must be "messages" (plural) — the API rejects "message".
              "messages": message,
              "temperature": temperature,
              "max_tokens": max_tokens
        }

        try:
              res = requests.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type":  "application/json",
                        # OpenRouter uses these for attribution; harmless but expected.
                        "HTTP-Referer": "http://localhost:5173",
                        "X-Title": "Palo Alto Rental GIS",
                    },
                    json=payload,
                    timeout=timeout
              )

        except requests.RequestException as err:
            raise LLMError(f"Could not reach OpenRouter: {err}") from err

        if res.status_code != 200:
            raise LLMError(f"OpenRouter returned {res.status_code}: {res.text[:300]}")

        data = res.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as err:
            raise LLMError(f"Unexpected response shape: {data}") from err
    