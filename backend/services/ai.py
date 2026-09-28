"""Groq-backed generation for Learnify.

Two consumers:
  * routes/ai.py       — draft MCQ questionnaires/assessments (queue → edit → publish)
  * backend/routes/reports.py — the personalisation layer on Veda reports

Design rules
  * The deterministic layer always works: if Groq is unreachable, mis-keyed, or
    slow, callers get a clear, actionable error and no half-built payload.
  * Never return unvalidated structure to a route — every response passes the
    strict JSON schema checks below, so a model cannot inject extra fields.
  * The API key never leaves the server.
"""

import json
import os
import re
from typing import Optional

import requests

DEFAULT_MODEL = os.environ.get("GROQ_MODEL") or "openai/gpt-oss-120b"

# Fallbacks are ordered; the first healthy model wins. Verified available on
# this project: openai/gpt-oss-120b, qwen/qwen3.8-27b, openai/gpt-oss-20b.
FALLBACK_MODELS = [
    DEFAULT_MODEL,
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
]

BASE = "https://api.groq.com/openai/v1"
TIMEOUT = 45

DIFFICULTIES = ("easy", "medium", "hard")


class AIUnavailable(RuntimeError):
    """Raised when Groq cannot be used — routes surface this as a 503."""


class AIInvalid(RuntimeError):
    """Raised when the model returned something that failed validation."""


def api_key() -> str:
    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not key:
        raise AIUnavailable(
            "GROQ_API_KEY is not configured. Add it to .env to enable AI "
            "drafting (manual authoring still works)."
        )
    return key


def _models() -> list[str]:
    """Unique, ordered candidate list — de-dupes the fallback chain."""
    seen, out = set(), []
    for m in FALLBACK_MODELS:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def available() -> dict:
    """Cheap capability probe for the UI (never leaks the key)."""
    key = os.environ.get("GROQ_API_KEY") or ""
    return {
        "configured": bool(key),
        "model": DEFAULT_MODEL,
        "features": {
            "question_generation": bool(key),
            "report_personalisation": bool(key),
        },
    }


# ─── Transport ─────────────────────────────────────────────────────────────
def _post(path: str, payload: dict, model: Optional[str] = None) -> dict:
    url = f"{BASE}/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"}
    body = dict(payload)
    if model:
        body["model"] = model
    try:
        r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise AIUnavailable(f"Could not reach Groq: {e}") from e
    if r.status_code == 401:
        raise AIUnavailable("Groq rejected the API key (401). Check GROQ_API_KEY.")
    if r.status_code == 404:
        raise AIUnavailable(f"Model '{model}' is not available on this project.")
    if r.status_code == 429:
        raise AIUnavailable("Groq rate limit reached — try again in a moment.")
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:200])
        except Exception:
            msg = r.text[:200]
        raise AIUnavailable(f"Groq error {r.status_code}: {msg}")
    try:
        return r.json()
    except Exception as e:
        raise AIUnavailable(f"Groq returned a non-JSON body: {e}") from e


def _content(resp: dict, model: str) -> str:
    """Extract assistant text from an OpenAI-compatible chat response."""
    choices = resp.get("choices") or []
    if not choices:
        raise AIInvalid("Groq returned no choices.")
    msg = choices[0].get("message") or {}
    text = msg.get("content")
    if not isinstance(text, str) or not text.strip():
        # Some reasoning models put the answer in `reasoning`.
        text = msg.get("reasoning") if isinstance(msg.get("reasoning"), str) else ""
    if not text or not text.strip():
        raise AIInvalid("Groq returned an empty message.")
    return text


def chat(messages: list[dict], *, temperature: float = 0.4,
         max_tokens: int = 4000, json_mode: bool = True) -> str:
    """Single-turn generation with model fallback. Returns assistant text.

    Groq's `response_format: json_object` rejects a prompt that does not
    contain the word "json". Rather than forcing that word into every prompt,
    we drop json_mode and retry — `extract_json` already tolerates prose and
    markdown fences around the payload.
    """
    errors = []
    for model in _models():
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = _post("chat/completions", payload, model)
            return _content(resp, model)
        except AIUnavailable as e:
            msg = str(e)
            if json_mode and "must contain the word 'json'" in msg:
                # Retry once without structured-output mode.
                try:
                    payload.pop("response_format", None)
                    resp = _post("chat/completions", payload, model)
                    return _content(resp, model)
                except AIUnavailable as e2:
                    errors.append(f"{model}: {e2}")
                    continue
            errors.append(f"{model}: {e}")
            continue
    raise AIUnavailable("No Groq model was reachable. " + " | ".join(errors))


# ─── Parsing helpers ───────────────────────────────────────────────────────
def extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response tolerantly.

    Handles markdown fences, leading prose and trailing commentary — all of
    which reasoning models produce despite instructions.
    """
    if not text:
        raise AIInvalid("Empty model response.")
    s = text.strip()

    # ```json ... ```
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.S | re.I)
    if fence:
        s = fence.group(1).strip()

    # Outermost { ... }
    start = s.find("{")
    if start == -1:
        raise AIInvalid("No JSON object found in the response.")
    depth, end = 0, -1
    in_str, esc = False, False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise AIInvalid("Truncated JSON object in the response.")

    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError as e:
        raise AIInvalid(f"Model returned malformed JSON: {e}") from e


def _clean_text(v, limit: int) -> str:
    s = re.sub(r"\s+", " ", str(v or "")).strip()
    return s[:limit]


# ─── Question generation ───────────────────────────────────────────────────
def generate_questions(*, subject: str, topics: list[str], count: int = 8,
                       difficulty: str = "medium", kind: str = "QUESTIONNAIRE",
                       language: str = "English",
                       extra_context: str = "") -> list[dict]:
    """Produce validated draft MCQs. Returns a list of:

        {text, options:[str], correct_index:int, explanation:str,
         difficulty:str, topic:str}
    """
    count = max(1, min(int(count or 8), 40))
    if difficulty not in DIFFICULTIES:
        difficulty = "medium"
    topic_line = ", ".join(topics[:20]) if topics else "the whole subject"
    exam_word = "a formal exam" if kind == "ASSESSMENT" else "practice"

    sys = (
        "You are an expert exam author for an Indian training and capacity-"
        "building platform. You write fair, unambiguous multiple-choice "
        "questions. Respond ONLY with a JSON object, no prose, no markdown."
    )
    user = (
        f"Create exactly {count} multiple-choice questions for a {exam_word}.\n"
        f"Subject: {subject}\n"
        f"Allowed topics (tag each question with EXACTLY one of these): {topic_line}\n"
        f"Difficulty: {difficulty}\n"
        f"Language: {language}\n"
        f"{('Context: ' + extra_context[:600]) if extra_context else ''}\n\n"
        "Rules:\n"
        "- Each question has exactly 4 options, one correct.\n"
        "- Make distractors plausible but clearly wrong; avoid 'all of the above'.\n"
        "- Avoid trick questions, negations and 'except' phrasings.\n"
        "- `explanation` is 1-2 sentences saying WHY the answer is right.\n"
        "- `topic` must be copied verbatim from the allowed topics list.\n\n"
        "Return exactly this JSON shape:\n"
        '{"questions":[{"text":"...","options":["a","b","c","d"],'
        '"correct_index":0,"explanation":"...","difficulty":"' + difficulty +
        '","topic":"..."}]}'
    )

    raw = chat([
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ], temperature=0.5, max_tokens=6000, json_mode=True)

    data = extract_json(raw)
    items = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(items, list):
        # Some models nest differently — search one level deep.
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict) \
                        and ("options" in v[0] or "text" in v[0]):
                    items = v
                    break
    if not isinstance(items, list) or not items:
        raise AIInvalid("The model did not return a question list.")

    allowed = {_clean_text(t, 120).lower() for t in topics} if topics else set()
    out, seen = [], set()
    for it in items[:count]:
        if not isinstance(it, dict):
            continue
        q = _validate_question(it, allowed, difficulty, seen)
        if q:
            out.append(q)
            seen.add(q["text"].lower())
    if not out:
        raise AIInvalid("Every generated question failed validation.")
    return out


def _validate_question(it: dict, allowed_topics: set, default_diff: str,
                       seen: set) -> Optional[dict]:
    text = _clean_text(it.get("text"), 2000)
    if len(text) < 10 or text.lower() in seen:
        return None

    opts_raw = it.get("options")
    if not isinstance(opts_raw, list):
        return None
    options = [_clean_text(o, 400) for o in opts_raw[:6]]
    options = [o for o in options if o]
    if len(options) < 2:
        return None
    # de-dupe while preserving order
    deduped, used = [], set()
    for o in options:
        k = o.lower()
        if k not in used:
            used.add(k)
            deduped.append(o)
    options = deduped
    if len(options) < 2:
        return None

    try:
        ci = int(it.get("correct_index", 0))
    except (TypeError, ValueError):
        ci = 0
    if ci < 0 or ci >= len(options):
        ci = 0

    diff = str(it.get("difficulty") or default_diff).lower().strip()
    if diff not in DIFFICULTIES:
        diff = default_diff

    topic = _clean_text(it.get("topic"), 120)
    if allowed_topics and topic.lower() not in allowed_topics:
        # Map to the closest allowed topic rather than dropping the question.
        topic = _closest(topic, allowed_topics) or ""

    return {
        "text": text,
        "options": options,
        "correct_index": ci,
        "explanation": _clean_text(it.get("explanation"), 1000),
        "difficulty": diff,
        "topic": topic,
    }


def _closest(name: str, allowed: set) -> Optional[str]:
    if not name:
        return None
    n = name.lower()
    for a in allowed:
        if n in a or a in n:
            return a
    # token overlap
    ntok = set(re.findall(r"[a-z]+", n))
    best, best_score = None, 0.0
    for a in allowed:
        atok = set(re.findall(r"[a-z]+", a))
        if not atok:
            continue
        score = len(ntok & atok) / len(ntok | atok)
        if score > best_score:
            best, best_score = a, score
    return best if best_score >= 0.4 else None


# ─── Veda report personalisation ───────────────────────────────────────────
REPORT_SECTIONS = (
    "weak_points", "improve", "industry", "learn_next", "suggestions",
)


def personalise_report(*, trainee_name: str, subject: str, percentage: float,
                       passed: bool, weak_topics: list[dict],
                       strong_topics: list[dict], difficulty: dict,
                       benchmarks: list[dict], attempt_kind: str) -> dict:
    """Turn the deterministic numbers into a written Veda report.

    Purely additive: the caller already has scores, ranks and benchmark data.
    If Groq fails the caller keeps the deterministic report untouched.
    """
    weak_line = ", ".join(
        f"{t.get('topic','')} ({t.get('pct',0)}%)" for t in weak_topics[:6]
    ) or "none recorded"
    strong_line = ", ".join(
        f"{t.get('topic','')} ({t.get('pct',0)}%)" for t in strong_topics[:6]
    ) or "none recorded"
    diff_line = ", ".join(
        f"{k}: {v.get('pct',0)}%" for k, v in (difficulty or {}).items()
    ) or "n/a"
    bench_line = "; ".join(
        f"{b.get('topic','')}: {b.get('standard','')}" for b in benchmarks[:6]
    ) or "not published for this subject"

    sys = (
        "You are Veda, the performance-report voice of Learnify, a "
        "digital capacity-building portal for Indian learners. Write in "
        "plain, encouraging, professional English. Be specific and "
        "actionable — never generic. Never invent scores or facts not given. "
        "Respond ONLY with a JSON object."
    )
    user = (
        f"Learner: {trainee_name}\n"
        f"Subject: {subject}\n"
        f"Type: {attempt_kind}\n"
        f"Score: {percentage:.1f}% ({'PASS' if passed else 'NOT YET'})\n"
        f"Weakest topics: {weak_line}\n"
        f"Strongest topics: {strong_line}\n"
        f"Difficulty split: {diff_line}\n"
        f"Industry benchmarks: {bench_line}\n\n"
        "Return exactly this JSON shape with SHORT paragraph values "
        "(2-4 sentences each):\n"
        '{"weak_points":"...", "improve":"...", "industry":"...", '
        '"learn_next":"...", "suggestions":["...", "...", "..."]}\n\n'
        "Meanings:\n"
        "weak_points — what tripped them up, in their language\n"
        "improve     — the 1-2 highest-leverage things to fix first\n"
        "industry    — how this compares to the published industry standard\n"
        "learn_next  — the specific topics/concepts to study next\n"
        "suggestions — 3 concrete study actions (strings in a list)"
    )

    raw = chat([
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ], temperature=0.6, max_tokens=2000, json_mode=True)

    data = extract_json(raw)
    if not isinstance(data, dict):
        raise AIInvalid("Report response was not a JSON object.")

    out = {}
    for key in REPORT_SECTIONS:
        val = data.get(key)
        if key == "suggestions":
            if isinstance(val, list):
                out[key] = [_clean_text(v, 300) for v in val[:6]
                            if str(v).strip()]
            elif isinstance(val, str) and val.strip():
                out[key] = [_clean_text(val, 600)]
            else:
                out[key] = []
        else:
            out[key] = _clean_text(val, 1200)
    return out
