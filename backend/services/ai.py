import json
import os

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

OPENROUTER_API_KEY_1 = os.environ.get("OPENROUTER_API_KEY_1") or os.environ.get(
    "OPENROUTER_KEY"
)
OPENROUTER_API_KEY_2 = os.environ.get("OPENROUTER_API_KEY_2") or os.environ.get(
    "OPENROUTER_KEY"
)

# Free models, best-first. OpenRouter free tiers are intermittently available,
# so we fall through to the next one on failure.
FALLBACK_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "google/gemma-4-31b-it:free",
    "z-ai/glm-5.2:free",
    "minimax/minimax-m3:free",
]


def chat(
    messages: list[dict],
    model: str = "openai/gpt-4o-mini",
    temperature: float = 0.7,
) -> str:
    """Return an assistant reply from OpenRouter, with free-model fallback."""
    if not OPENROUTER_API_KEY_1:
        raise RuntimeError("OPENROUTER_API_KEY_1 is not configured")

    order = [model] + [m for m in FALLBACK_MODELS if m != model]
    last_err = None
    for mdl in order:
        try:
            return _call(mdl, messages, temperature)
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(
        "Veda is temporarily unavailable (AI provider busy). Please try again in a moment."
    )


def _call_stream(model: str, messages: list[dict], temperature: float):
    """Yield assistant tokens as they arrive from OpenRouter (SSE)."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY_1}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://learnify.app",
        "X-Title": "Learnify",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    resp = requests.post(
        OPENROUTER_URL, headers=headers, json=payload, stream=True, timeout=(8, 25)
    )
    resp.raise_for_status()
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
            content = obj["choices"][0]["delta"].get("content")
            if content:
                yield content
        except Exception:
            continue


def stream_chat(
    messages: list[dict],
    model: str = "openai/gpt-4o-mini",
    temperature: float = 0.7,
):
    """Stream an assistant reply, falling through free models on failure.

    Yields text tokens. Raises RuntimeError only if every model fails.
    """
    if not OPENROUTER_API_KEY_1:
        raise RuntimeError("OPENROUTER_API_KEY_1 is not configured")

    order = [model] + [m for m in FALLBACK_MODELS if m != model]
    for mdl in order[:2]:
        try:
            yielded = False
            for tok in _call_stream(mdl, messages, temperature):
                yielded = True
                yield tok
            if not yielded:
                raise RuntimeError("OpenRouter returned an empty response")
            return
        except Exception:
            continue
    raise RuntimeError(
        "Veda is temporarily unavailable (AI provider busy). Please try again in a moment."
    )


def _call(model: str, messages: list[dict], temperature: float) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY_1}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://learnify.app",
        "X-Title": "Learnify",
    }
    payload = {"model": model, "messages": messages, "temperature": temperature}

    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=25)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise RuntimeError("OpenRouter returned an empty response")
    return content


def analyze(text: str, model: str = "nvidia/nemotron-3.5-lightning:free") -> dict:
    """Return structured analysis {summary, entities} from OpenRouter."""
    if not OPENROUTER_API_KEY_2:
        raise RuntimeError("OPENROUTER_API_KEY_2 is not configured")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY_2}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://learnify.app",
        "X-Title": "Learnify",
    }
    prompt = (
        "Analyze the following text. Respond ONLY with JSON containing "
        '"summary" (string <=200 chars) and "entities" (list of short strings). '
        f"Text:\n{text}"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = __import__("json").loads(content)
    return {
        "summary": str(parsed.get("summary", (text or "")[:200])),
        "entities": parsed.get("entities", []),
    }


def embed(text: str) -> list[float] | None:
    """Return embedding vector or None (callers fall back to keyword retrieval)."""
    if not OPENROUTER_API_KEY_2:
        return None
    # OpenRouter has no universal embedding endpoint; keep simple, return None.
    return None


VISION_MODELS = [
    "openai/gpt-4o-mini",
    "google/gemini-2.0-flash-001",
    "anthropic/claude-3.5-sonnet",
]


def vision_extract(b64: str, mime: str, prompt: str) -> str:
    """Return text extracted from an image using a vision-capable model via OpenRouter."""
    key = OPENROUTER_API_KEY_1 or OPENROUTER_API_KEY_2
    if not key:
        raise RuntimeError("OPENROUTER key is not configured")
    for mdl in VISION_MODELS:
        try:
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://learnify.app",
                "X-Title": "Learnify",
            }
            payload = {
                "model": mdl,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "temperature": 0.2,
            }
            resp = requests.post(
                OPENROUTER_URL, headers=headers, json=payload, timeout=45
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if content and content.strip():
                return content
        except Exception:
            continue
    raise RuntimeError("Vision extraction failed on all models")
