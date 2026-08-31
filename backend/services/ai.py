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
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
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
    # Use smaller max_tokens for faster streaming on simple queries
    sys_content = messages[0]["content"] if messages else ""
    is_simple = len(sys_content) < 1500 and len(messages) <= 2
    max_tok = 1024 if is_simple else 4096

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "max_tokens": max_tok,
    }
    resp = requests.post(
        GROQ_URL, headers=_headers(), json=payload, stream=True, timeout=(connect, read)
    )
    resp.raise_for_status()
    # Read RAW bytes and decode each complete SSE line as UTF-8. Using
    # `decode_unicode=True` would decode per-chunk, splitting multi-byte chars
    # (emojis, curly quotes) across chunk boundaries and producing U+FFFD
    # mojibake. Splitting on newlines first keeps each line's bytes intact.
    for raw in resp.iter_lines(decode_unicode=False):
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace")
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


def extract_marksheet(text: str) -> dict:
    """Parse a mark sheet / result text into a structured academic record via Groq.

    Returns {exam, board, year, marks:{subject:score}, total, percentage} or {}.
    """
    if not GROQ_API_KEY or not text or not text.strip():
        return {}
    prompt = (
        "You are an academic data extractor for Indian student mark sheets and result "
        "pages. Extract a JSON object with only these fields: "
        '{"exam":"10th|12th|Diploma|Graduation|Other",'
        '"board":"CBSE|ICSE|ISC|State Board|Other",'
        '"year":YYYY,"marks":{"Subject":score_number},'
        '"total":number,"percentage":number}. '
        "Include every subject and its numeric score found. Compute total as the sum of "
        "marks and percentage as (total / (number_of_subjects * 100)) * 100, rounded to 2 "
        "decimals. If a field is genuinely absent, use null. Output ONLY the JSON object, "
        "no markdown fences."
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text[:6000]},
    ]
    try:
        return _call_json("openai/gpt-oss-120b", messages, 0.1) or {}
    except Exception:
        return {}


def _call_json(model: str, messages: list[dict], temperature: float = 0.2) -> dict:
    """Call Groq in JSON mode and parse the returned object."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(GROQ_URL, headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


# Profile fields we can persist. (Public `users` columns + academic record.)
_PROFILE_FIELDS = [
    "name",
    "gender",
    "grade",
    "school",
    "board",
    "college",
    "state",
    "city",
    "target_exam",
    "stream",
    "career_goal",
    "language",
    "bio",
    "exam",
    "marks",
    "percentage",
    "year",
]


def extract_profile(text: str) -> dict:
    """Extract structured student-profile info from free-text chat input.

    Returns a dict of only the fields that were clearly present. Used to keep
    the user's profile in sync with what they casually mention in chat.
    """
    if not GROQ_API_KEY or not text or not text.strip():
        return {}
    prompt = (
        "You are a profile extractor for an Indian student study app. "
        "Read the user's message and extract any student-profile facts. "
        "Respond with ONE JSON object. For each field, output the value if "
        "clearly stated, else an empty string. Fields:\n"
        "- name: student's name\n"
        "- gender: 'Male' / 'Female' / 'Other'\n"
        "- grade: class or year of study (e.g. '12th', '2nd year B.Tech')\n"
        "- school: school name\n"
        "- board: education board (CBSE / ICSE / State / IB / etc.)\n"
        "- college: college name\n"
        "- state: Indian state of residence\n"
        "- city: city of residence\n"
        "- target_exam: exam being prepared for (JEE / NEET / CET / GATE / UPSC / CA / CAT / boards / etc.)\n"
        "- stream: field of study (Engineering / Medical / Commerce / Arts / Science / etc.)\n"
        "- career_goal: intended career\n"
        "- language: preferred language (English / Hindi / etc.)\n"
        "- bio: short self description\n"
        "- exam: an academic exam/marks entry name (e.g. '12th Boards', 'JEE Main') ONLY if marks are mentioned\n"
        "- marks: marks/score text for that exam (e.g. '450/500' or 'Maths 95, Physics 88')\n"
        "- percentage: overall percentage number if stated (as a string, e.g. '95')\n"
        "- year: year of that exam (e.g. 2024) if stated\n"
        "Set exam/marks/percentage/year together when the user states academic "
        "marks/score/percentage. Output JSON only, no prose."
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]
    last_err = None
    for mdl in ["groq/compound-mini", "groq/compound", "openai/gpt-oss-120b"]:
        try:
            obj = _call_json(mdl, messages)
            if isinstance(obj, dict):
                return {
                    k: str(obj.get(k, "")).strip()
                    for k in _PROFILE_FIELDS
                    if obj.get(k)
                }
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return {}


def generate_quiz(
    topic: str, count: int = 5, difficulty: str = "Mixed", language: str = "English"
) -> dict:
    """Generate a multiple-choice quiz as structured JSON.

    Returns {"questions": [{"question", "options":[4], "answer_index":int,
    "explanation":str}, ...]}.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")
    sys_prompt = (
        "You are an expert Indian academic tutor. Generate a multiple-choice quiz. "
        "Respond with ONE JSON object of the form "
        '{"questions":[ {"question": string, "options": [string, string, string, string], '
        '"answer_index": integer 0-3, "explanation": string} ]}. '
        f"Language: {language}. Difficulty: {difficulty}. Topic: {topic}. "
        f"Generate exactly {count} questions accurate to the Indian curriculum. "
        "Distractors must be plausible. Output JSON only, no prose."
    )
    messages = [{"role": "system", "content": sys_prompt}]
    last_err = None
    for mdl in [ANALYZE_MODEL, "groq/compound", "openai/gpt-oss-120b"]:
        try:
            obj = _call_json(mdl, messages, temperature=0.5)
            qs = obj.get("questions") or []
            clean = []
            for q in qs:
                opts = q.get("options") or []
                if not isinstance(opts, list):
                    opts = [str(opts)]
                opts = [str(o) for o in opts][:4]
                try:
                    ai_idx = int(q.get("answer_index"))
                except Exception:
                    ai_idx = 0
                if not (0 <= ai_idx < len(opts)):
                    ai_idx = 0
                clean.append(
                    {
                        "question": str(q.get("question", "")),
                        "options": opts,
                        "answer_index": ai_idx,
                        "explanation": str(q.get("explanation", "") or ""),
                    }
                )
            if clean:
                return {"questions": clean}
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise RuntimeError("Quiz generation failed")


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
