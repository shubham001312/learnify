import json
import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_KEY")

# Chat models (best-first). These are the model IDs actually available on the
# configured Groq key (older llama/gemma/mixtral IDs were decommissioned).
# Ordered for quality + rate-limit resilience.
CHAT_MODELS = [
    "groq/compound",
    "groq/compound-mini",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
]

ANALYZE_MODEL = "openai/gpt-oss-120b"

VISION_MODELS = [
    "groq/compound",
    "openai/gpt-oss-120b",
]


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }


def _order(requested: str | None, pool: list[str]) -> list[str]:
    if requested and requested in pool:
        return [requested] + [m for m in pool if m != requested]
    return list(pool)


def chat(
    messages: list[dict],
    model: str = "groq/compound",
    temperature: float = 0.7,
) -> str:
    """Return an assistant reply from Groq, with model fallback."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    for mdl in _order(model, CHAT_MODELS):
        try:
            return _call(mdl, messages, temperature)
        except Exception:
            continue
    raise RuntimeError(
        "Veda is temporarily unavailable (AI provider busy). Please try again in a moment."
    )


def _call_stream(
    model: str, messages: list[dict], temperature: float, connect=6, read=20
):
    """Yield assistant tokens as they arrive from Groq (SSE)."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    resp = requests.post(
        GROQ_URL, headers=_headers(), json=payload, stream=True, timeout=(connect, read)
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
    model: str = "groq/compound",
    temperature: float = 0.7,
):
    """Stream an assistant reply from Groq, falling through models on failure.

    Yields text tokens. Raises RuntimeError only if every model fails.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    for mdl in _order(model, CHAT_MODELS):
        try:
            yielded = False
            for tok in _call_stream(mdl, messages, temperature, connect=6, read=20):
                yielded = True
                yield tok
            if yielded:
                return
            raise RuntimeError("Groq returned an empty response")
        except Exception:
            continue
    raise RuntimeError(
        "Veda is temporarily unavailable (AI provider busy). Please try again in a moment."
    )


def _call(model: str, messages: list[dict], temperature: float) -> str:
    payload = {"model": model, "messages": messages, "temperature": temperature}
    resp = requests.post(GROQ_URL, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise RuntimeError("Groq returned an empty response")
    return content


def analyze(text: str, model: str = ANALYZE_MODEL) -> dict:
    """Return structured analysis {summary, entities} from Groq."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

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

    resp = requests.post(GROQ_URL, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return {
        "summary": str(parsed.get("summary", (text or "")[:200])),
        "entities": parsed.get("entities", []),
    }


def embed(text: str) -> list[float] | None:
    """Return embedding vector or None (callers fall back to keyword retrieval).

    Groq does not provide an embeddings endpoint, so we always fall back.
    """
    return None


def vision_extract(b64: str, mime: str, prompt: str) -> str:
    """Return text extracted from an image using a vision-capable Groq model."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    for mdl in VISION_MODELS:
        try:
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
            resp = requests.post(GROQ_URL, headers=_headers(), json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if content and content.strip():
                return content
        except Exception:
            continue
    raise RuntimeError("Vision extraction failed on all models")
