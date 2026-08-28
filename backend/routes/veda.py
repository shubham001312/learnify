import json
import datetime
import concurrent.futures as _cf
import urllib.parse
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from backend.services.ai import (
    stream_chat as ai_stream,
    extract_profile as ai_extract_profile,
    generate_quiz as ai_generate_quiz,
    _call_json,
)
from backend.services.rag import retrieve as rag_retrieve

from backend.database.client import db_available, get_client
from backend.database.seed import SEED_SCHOLARSHIPS
from backend.database.seed_careers import list_careers


router = APIRouter()

_HOME_CACHE = {}  # per-user-per-day cache for home suggestions; resets on restart/deploy


def _with_timeout(fn, timeout, default=None):
    """Run fn in a worker thread; return `default` if it exceeds `timeout`.

    Prevents a slow downstream call (DB, embeddings) from hanging the whole
    chat request before the first byte is ever sent to the client.
    """
    try:
        with _cf.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(fn).result(timeout=timeout)
    except Exception:
        return default


def _local_reply(text: str) -> str:
    """Rule-based fallback so Veda always returns something useful, even if the
    AI provider is down or slow. Returns plain friendly text (no markdown)."""
    t = (text or "").lower()
    if any(
        g in t
        for g in (
            "hi",
            "hello",
            "hey",
            "namaste",
            "नमस्ते",
            "how are you",
            "good morning",
            "good evening",
        )
    ):
        return (
            "Hey! I'm Veda, your study companion. Tell me what you're working on "
            "today — a subject, an exam, or a career question — and I'll help you out. ✨"
        )
    if "scholarship" in t or "छात्रवृत्ति" in t or "fellowship" in t:
        lines = _scholarship_context(text)[:6]
        return (
            "Here are some real scholarships you can explore:\n"
            + "\n".join(lines)
            + "\n\nOpen the Scholarships tab for the full list and apply links."
        )
    if "college" in t or "university" in t or "कॉलेज" in t or "campus" in t:
        return (
            "You can explore top Indian colleges (IITs, NITs, IISc and more) in the "
            "Colleges tab — filter by NIRF rank, stream and state, and compare them "
            "side by side. Tell me your stream or exam and I can suggest a few!"
        )
    if any(
        e in t
        for e in (
            "jee",
            "neet",
            "upsc",
            "ca ",
            "cat ",
            "gate",
            "boards",
            "exam",
            "परीक्षा",
        )
    ):
        return (
            "For exam prep, a simple plan works best: break the syllabus into weekly "
            "targets, revise with active recall, and solve previous years' papers. "
            "Tell me which exam and your timeline — I'll help you build a study plan."
        )
    if any(
        s in t
        for s in (
            "study",
            "tips",
            "motivat",
            "stress",
            "anxious",
            "sad",
            "tired",
            "पढ़ाई",
        )
    ):
        return (
            "You've got this! Small consistent steps beat cramming. Take a 5-minute "
            "break, hydrate, and tackle one topic at a time. I'm here if you want a "
            "quick study plan or just to talk. 💪"
        )
    return (
        "I'm Veda, your study companion. I can help with subjects, exam prep "
        "(JEE/NEET/boards), careers, colleges, scholarships and study planning. "
        "What would you like help with right now?"
    )


class ChatReq(BaseModel):
    user_id: str = "demo"
    messages: List[dict]
    mode: str = "chat"
    language: str = "English"
    chat_id: Optional[str] = None
    return_json: bool = False


class QuizReq(BaseModel):
    user_id: str = "demo"
    topic: str
    count: int = 5
    difficulty: str = "Mixed"
    language: str = "English"


SYSTEM_BASE = (
    "You are Veda, a warm, friendly AI study companion for Indian students. "
    "Talk like a supportive older sibling / mentor — kind, encouraging, and concise. "
    "You CAN chat casually (greetings like hi/hello, small talk, motivation) — be "
    "friendly and natural, then gently help with studies. Keep it brief.\n"
    "SCOPE: education for Indian students — subjects, exam prep (JEE/NEET/boards/CA/UPSC "
    "etc.), careers, admissions, colleges, study planning, scholarships, and student life. "
    "If asked something clearly off-topic (code generation, politics, dating, etc.), "
    "respond politely and redirect toward studies rather than refusing coldly.\n"
    "LANGUAGE: Always reply in the SAME language the user writes in. If they write "
    "Hindi/Hinglish (WhatsApp-style), reply in Hindi/Hinglish. If they write English, "
    "reply in English. Match their tone and slang.\n"
    "PERSONALISATION: You have the user's real profile and academic records below. Use "
    "them for specific, personal answers. Address the user by name when known. When they "
    "ask about THEIR OWN marks, results, or records, answer strictly from the USER DATA — "
    "never invent numbers.\n"
    "SCHOLARSHIPS: if asked, answer strictly from the REAL SCHOLARSHIP DATABASE in context. "
    "Do not invent schemes; never mention KVPY (discontinued).\n"
    "PRECISION & PROFILE BUILDING: Be concrete and specific, not vague. When essential info "
    "for a good answer is missing (e.g. they ask 'best college for me' but their stream / "
    "state / marks are unknown), ask ONE short, specific question at a time to collect it "
    "(stream, class & marks, target exam, state, goal). Do NOT ask many questions at once. "
    "Once you have enough, give a precise, structured answer with real names/examples.\n"
    "FORMATTING: Use clean, readable markdown to structure answers — short ## headings when "
    "helpful, **bold** key terms, bullet lists (-) for options/steps, and numbered lists for "
    "sequences. Keep paragraphs short and friendly. Do not use horizontal rules.\n"
    "ATTRIBUTE ANSWERS: When a question asks about the traits, features, pros/cons, steps, "
    "options, or comparison of a person/college/exam/topic, NEVER reply in one dense paragraph. "
    "Break it into **bullet or numbered points** (one idea per line), keep each point short, and "
    "lead with a one-line summary. This is the preferred style for all explanatory answers."
)


def _is_scholarship_query(text: str) -> bool:
    t = (text or "").lower()
    return any(
        k in t
        for k in (
            "scholarship",
            "scholarships",
            "fellowship",
            "scholar",
            "financial aid",
            "financial support",
            "छात्रवृत्ति",
        )
    )


def _scholarship_context(query: str) -> List[str]:
    q = (query or "").lower()
    words = [w for w in q.split() if len(w) > 3]
    items = []
    for s in SEED_SCHOLARSHIPS:
        hay = " ".join(
            str(s.get(k, ""))
            for k in ("name", "category", "state", "eligibility", "amount")
        ).lower()
        if not words or any(w in hay for w in words):
            items.append(s)
    if not items:
        items = SEED_SCHOLARSHIPS
    items = items[:20]
    lines = []
    for s in items:
        lines.append(
            f"- {s.get('name')} | {s.get('category')} | {s.get('state', 'All India')} | "
            f"Amount: {s.get('amount')} | Eligibility: {s.get('eligibility')} | "
            f"Deadline: {s.get('deadline')} | Apply: {s.get('link')}"
        )
    return lines


def _user_context(user_id: str) -> str:
    """Build a personalisation block from the user's real stored data."""
    if not user_id or user_id == "demo" or not db_available():
        return ""
    try:
        client = get_client()
        res = (
            client.table("users")
            .select(
                "name,grade,language,school,board,college,dob,premium,"
                "gender,state,city,target_exam,stream,career_goal,bio"
            )
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        u = (res.data or [{}])[0] if res.data else {}
        if not u:
            return ""

        parts = ["USER PROFILE (use this to personalise):"]
        if u.get("name"):
            parts.append(f"- Name: {u['name']}")
        if u.get("grade"):
            parts.append(f"- Grade / class: {u['grade']}")
        if u.get("school"):
            parts.append(f"- School: {u['school']}")
        if u.get("board"):
            parts.append(f"- Board: {u['board']}")
        if u.get("college"):
            parts.append(f"- College: {u['college']}")
        if u.get("stream"):
            parts.append(f"- Stream / field: {u['stream']}")
        if u.get("target_exam"):
            parts.append(f"- Target exam: {u['target_exam']}")
        if u.get("state"):
            parts.append(f"- State: {u['state']}")
        if u.get("city"):
            parts.append(f"- City: {u['city']}")
        if u.get("gender"):
            parts.append(f"- Gender: {u['gender']}")
        if u.get("career_goal"):
            parts.append(f"- Career goal: {u['career_goal']}")
        if u.get("bio"):
            parts.append(f"- Bio: {u['bio']}")
        if u.get("dob"):
            parts.append(f"- Date of birth: {u['dob']}")

        acad = (
            client.table("academic_records")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        for rec in acad.data or []:
            label = rec.get("exam") or "Exam"
            line = f"- {label} record"
            if rec.get("board"):
                line += f" (board: {rec['board']})"
            if rec.get("year"):
                line += f" year: {rec['year']}"
            if rec.get("marks"):
                line += f": marks = {json.dumps(rec['marks'], ensure_ascii=False)}"
            if rec.get("percentage") is not None:
                line += f", percentage = {rec['percentage']}"
            if rec.get("total") is not None:
                line += f", total = {rec['total']}"
            parts.append(line)

        mem = (
            client.table("memory")
            .select("kind,content")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        for m in mem.data or []:
            if m.get("content"):
                parts.append(f"- Memory: {m['content']}")

        return "\n".join(parts)
    except Exception:
        return ""


def _ensure_chat(user_id: str, chat_id: Optional[str], title: str):
    """Return a valid chat_id (create one if needed)."""
    if not db_available():
        return None
    try:
        client = get_client()
        if chat_id:
            existing = (
                client.table("chats").select("id").eq("id", chat_id).limit(1).execute()
            )
            if existing.data:
                return chat_id
        res = (
            client.table("chats")
            .insert({"user_id": user_id, "title": title[:80]})
            .execute()
        )
        if res.data:
            return res.data[0]["id"]
    except Exception:
        pass
    return None


def _persist_turn(user_id, chat_id, user_msg, assistant_msg):
    if not db_available() or not chat_id:
        return
    try:
        client = get_client()
        rows = [
            {
                "user_id": user_id,
                "chat_id": chat_id,
                "role": "user",
                "content": user_msg,
            },
            {
                "user_id": user_id,
                "chat_id": chat_id,
                "role": "assistant",
                "content": assistant_msg,
            },
        ]
        client.table("conversations").insert(rows).execute()
        client.table("chats").update({"updated_at": "now()"}).eq(
            "id", chat_id
        ).execute()
    except Exception:
        pass


def _extract_and_save_profile(user_id: str, text: str) -> dict:
    """Two-way profile sync: pull structured facts the user mentioned in chat and
    persist them to their profile (users) and academic records, so future answers
    are precise. Returns a compact delta dict for UI feedback (empty if nothing)."""
    if not user_id or user_id in ("demo", "auth-user") or not db_available():
        return {}
    try:
        data = ai_extract_profile(text)
    except Exception:
        return {}
    if not data:
        return {}

    client = get_client()
    # 1) Plain profile fields -> users table.
    PROFILE_COLS = [
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
    ]
    update = {}
    for f in PROFILE_COLS:
        v = (data.get(f) or "").strip()
        if v:
            update[f] = v
    if update:
        try:
            client.table("users").update(update).eq("id", user_id).execute()
        except Exception:
            update = {}

    # 2) Academic marks -> academic_records (dedupe by exam so re-stating doesn't spam).
    academic = []
    exam = (data.get("exam") or "").strip()
    marks = (data.get("marks") or "").strip()
    pct = (data.get("percentage") or "").strip()
    year = (data.get("year") or "").strip()
    if exam and (marks or pct):
        try:
            existing = (
                client.table("academic_records")
                .select("id")
                .eq("user_id", user_id)
                .eq("exam", exam)
                .execute()
            )
            for row in existing.data or []:
                client.table("academic_records").delete().eq("id", row["id"]).execute()
            pct_val = float(pct) if pct.replace(".", "", 1).isdigit() else None
            rec = {
                "user_id": user_id,
                "exam": exam,
                "board": (data.get("board") or "").strip(),
                "marks": marks,
                "total": None,
                "percentage": pct_val,
                "year": int(year) if year.isdigit() else None,
                "raw_text": text[:500],
            }
            client.table("academic_records").insert(rec).execute()
            academic.append({"exam": exam, "value": pct or marks})
        except Exception:
            pass

    deltas = {}
    if update:
        deltas["profile"] = update
    if academic:
        deltas["academic"] = academic
    return deltas


@router.post("/chat")
def chat(req: ChatReq):
    user_messages = [m for m in req.messages if m.get("role") == "user"]
    last_msg = user_messages[-1].get("content", "") if user_messages else ""

    # Non-streaming JSON mode (used by structured tools like Resume Polish that
    # need a guaranteed parseable object back instead of a text stream).
    if req.return_json:
        full = [
            {
                "role": "system",
                "content": "You are a precise assistant. Respond with valid JSON only, no markdown fences.",
            }
        ] + req.messages
        try:
            parsed = (
                _with_timeout(lambda: _call_json("openai/gpt-oss-120b", full, 0.2), 25)
                or {}
            )
        except Exception:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        return JSONResponse({"reply": json.dumps(parsed)})

    # Two-way profile sync: pull any facts the user just stated into their profile
    # so Veda's answer (and all future ones) can be precise.
    profile_deltas = {}
    try:
        profile_deltas = (
            _with_timeout(lambda: _extract_and_save_profile(req.user_id, last_msg), 4)
            or {}
        )
    except Exception:
        profile_deltas = {}

    ctx = []
    scholarship_block = ""
    try:
        ctx = _with_timeout(lambda: rag_retrieve(last_msg, req.user_id), 3) or []
    except Exception:
        ctx = []

    if _is_scholarship_query(last_msg):
        try:
            sch_lines = _scholarship_context(last_msg)
            if sch_lines:
                scholarship_block = (
                    "\nREAL SCHOLARSHIP DATABASE (use ONLY these, do not invent others; "
                    "KVPY is discontinued, never mention it):\n"
                    + "\n".join(sch_lines)
                    + "\n"
                )
        except Exception:
            scholarship_block = ""

    try:
        user_block = _with_timeout(lambda: _user_context(req.user_id), 3) or ""
    except Exception:
        user_block = ""

    context_block = ""
    if user_block:
        context_block += user_block + "\n"
    if scholarship_block:
        context_block += scholarship_block
    if ctx:
        context_block += "Other relevant context:\n" + "\n".join(
            f"- {c}" for c in ctx[:3]
        )

    system_prompt = (
        SYSTEM_BASE
        + f"\nMode: {req.mode}"
        + f"\nRespond in {req.language}."
        + (f"\n\n{context_block}" if context_block else "")
    )

    full_messages = [{"role": "system", "content": system_prompt}]
    full_messages.extend(req.messages)

    try:
        chat_id = _with_timeout(
            lambda: _ensure_chat(req.user_id, req.chat_id, last_msg or "New chat"), 3
        ) or (req.chat_id or "default")
    except Exception:
        chat_id = req.chat_id or "default"

    def event_stream():
        collected = []
        try:
            yield " "  # flush headers immediately so the client receives bytes at once
            try:
                for token in ai_stream(full_messages):
                    collected.append(token)
                    yield token
            except Exception:
                # AI provider failed/slow: fall back to a helpful local reply so the
                # user always gets an answer instead of a dead end.
                fb = _local_reply(last_msg)
                collected.append(fb)
                yield fb
        except Exception:
            err = (
                "\n\nI'm really sorry — I'm having a small hiccup connecting right "
                "now. Please send that again in a moment. 🙏"
            )
            yield err
            collected.append(err)
        finally:
            _persist_turn(req.user_id, chat_id, last_msg, "".join(collected))

    resp = StreamingResponse(event_stream(), media_type="text/plain; charset=utf-8")
    if profile_deltas:
        resp.headers["X-Profile-Updated"] = urllib.parse.quote(
            json.dumps(profile_deltas)
        )
    return resp


# ───────────────────────── personalized home slots ─────────────────────────
class HomeSuggReq(BaseModel):
    user_id: str = "demo"
    language: str = "English"


@router.post("/home-suggestions")
def home_suggestions(req: HomeSuggReq):
    """AI-generated, personalized suggestion 'slots' for the home screen,
    derived from the user's real profile, marks and goals."""
    cache_key = (req.user_id or "demo") + "|" + datetime.date.today().isoformat()
    if cache_key in _HOME_CACHE:
        return {"slots": _HOME_CACHE[cache_key]}
    try:
        user_block = _with_timeout(lambda: _user_context(req.user_id), 3) or ""
    except Exception:
        user_block = ""

    career_titles = ", ".join(f"{c['title']}" for c in list_careers())

    system = (
        "You are Veda, an AI study companion for Indian students. The user has a home "
        "screen with a 'For You' section. Generate 4 short, personalized, actionable "
        "suggestion cards (slots) they would find genuinely useful right now. "
        "Base them on the USER PROFILE below when available (exam, stream, marks, goal, "
        "state). If the profile is empty, give broadly useful student actions. "
        "Each slot must be concrete and specific (name a real exam, career, subject or tool).\n"
        'Return STRICT JSON only: {"slots":[ {"icon":emoji,"title":<4 words>,'
        '"text":<one short sentence>,"cta_label":<2-3 words>,"cta_go":'
        '"college"|"career"|"veda"|"scholarships"|"planner"|"quiz",'
        '"cta_arg":<optional career id / exam / empty string>} ]}.\n'
        "Available careers include: " + career_titles + "."
    )
    messages = [{"role": "system", "content": system}]
    if user_block:
        messages.append({"role": "user", "content": "USER PROFILE:\n" + user_block})
    else:
        messages.append(
            {
                "role": "user",
                "content": "No profile data yet — suggest useful starter actions.",
            }
        )

    try:
        parsed = (
            _with_timeout(lambda: _call_json("openai/gpt-oss-120b", messages, 0.35), 25)
            or {}
        )
    except Exception:
        parsed = {}
    slots = parsed.get("slots") if isinstance(parsed, dict) else None
    if not isinstance(slots, list) or not slots:
        slots = _default_slots()
    # Sanitize / cap.
    clean = []
    allowed_go = {"college", "career", "veda", "scholarships", "planner", "quiz"}
    for s in slots[:4]:
        if not isinstance(s, dict):
            continue
        clean.append(
            {
                "icon": (s.get("icon") or "✨")[:4],
                "title": str(s.get("title", "Tip"))[:40],
                "text": str(s.get("text", ""))[:140],
                "cta_label": str(s.get("cta_label", "Explore"))[:30],
                "cta_go": s.get("cta_go") if s.get("cta_go") in allowed_go else "veda",
                "cta_arg": str(s.get("cta_arg") or "")[:40],
            }
        )
    if not clean:
        clean = _default_slots()
    else:
        _HOME_CACHE[cache_key] = clean
    return {"slots": clean}


def _default_slots():
    return [
        {
            "icon": "🎯",
            "title": "Explore Careers",
            "text": "Discover 25+ career paths and find what fits you best.",
            "cta_label": "Career Paths",
            "cta_go": "career",
            "cta_arg": "",
        },
        {
            "icon": "🏫",
            "title": "Find Colleges",
            "text": "Search 700+ colleges across India with smart filters.",
            "cta_label": "Search",
            "cta_go": "college",
            "cta_arg": "",
        },
        {
            "icon": "💡",
            "title": "Ask Veda",
            "text": "Stuck on a topic or decision? Chat with your AI mentor.",
            "cta_label": "Talk",
            "cta_go": "veda",
            "cta_arg": "",
        },
        {
            "icon": "🎓",
            "title": "Scholarships",
            "text": "See schemes you may be eligible for and never miss a deadline.",
            "cta_label": "Browse",
            "cta_go": "scholarships",
            "cta_arg": "",
        },
    ]


# ───────────────────────── career guidance (short Q&A) ─────────────────────────
class GuidanceReq(BaseModel):
    user_id: str = "demo"
    answers: dict = {}
    language: str = "English"


@router.post("/career-guidance")
def career_guidance(req: GuidanceReq):
    """Take a student's profile + a few short survey answers and return a
    personalized career-path recommendation (drawn from our careers dataset)."""
    try:
        user_block = _with_timeout(lambda: _user_context(req.user_id), 1.5) or ""
    except Exception:
        user_block = ""

    careers = list_careers()
    catalog = "\n".join(f"- {c['id']}: {c['title']} ({c['category']})" for c in careers)
    answers_txt = json.dumps(req.answers or {}, ensure_ascii=False)

    system = (
        "You are Veda, a career counsellor for Indian students. Using the student's "
        "profile and their answers to a short interest survey, recommend the single "
        "best-fit career PATH from the provided CATALOG (you must pick one of those ids). "
        "Also list 1-3 alternative paths they should consider. Be specific and kind.\n"
        "Return STRICT JSON only:\n"
        '{"career_id":"<id from catalog>","title":"<career title>",'
        '"category":"<category>","match":<0-100 integer>,'
        '"reasoning":"<2-3 short sentences>",'
        '"next_steps":[<3 short steps>],'
        '"also_consider":[<up to 3 career ids from catalog>]}\n'
        "CATALOG:\n" + catalog
    )
    messages = [{"role": "system", "content": system}]
    ctx = ""
    if user_block:
        ctx += "USER PROFILE:\n" + user_block + "\n"
    ctx += "SURVEY ANSWERS:\n" + answers_txt
    messages.append({"role": "user", "content": ctx})

    try:
        parsed = (
            _with_timeout(lambda: _call_json("openai/gpt-oss-120b", messages, 0.3), 25)
            or {}
        )
    except Exception:
        parsed = {}

    # Validate career_id against our catalog.
    valid_ids = {c["id"] for c in careers}
    cid = parsed.get("career_id") if isinstance(parsed, dict) else None
    if cid not in valid_ids:
        # Try to match by title, else fall back to also_consider / first.
        title = (parsed.get("title") or "").lower()
        matched = next((c["id"] for c in careers if c["title"].lower() == title), None)
        if not matched and isinstance(parsed.get("also_consider"), list):
            matched = next((x for x in parsed["also_consider"] if x in valid_ids), None)
        cid = matched or (list(valid_ids)[0] if valid_ids else None)

    result = {
        "career_id": cid,
        "title": parsed.get("title") if isinstance(parsed, dict) else None,
        "category": parsed.get("category") if isinstance(parsed, dict) else None,
        "match": parsed.get("match") if isinstance(parsed, dict) else None,
        "reasoning": parsed.get("reasoning") if isinstance(parsed, dict) else None,
        "next_steps": parsed.get("next_steps") if isinstance(parsed, dict) else None,
        "also_consider": parsed.get("also_consider")
        if isinstance(parsed, dict)
        else None,
    }
    return {"guidance": result}


@router.post("/quiz")
def quiz(req: QuizReq):
    """Generate an MCQ quiz on a topic (structured JSON for the frontend)."""
    topic = (req.topic or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")
    count = max(1, min(20, int(req.count or 5)))
    try:
        data = ai_generate_quiz(topic, count, req.difficulty, req.language)
        return data
    except Exception as e:
        raise HTTPException(status_code=502, detail="Quiz generation failed: " + str(e))


# ───────────────────────── chat history ─────────────────────────
class ChatCreate(BaseModel):
    user_id: str
    title: Optional[str] = None


@router.get("/chats")
def list_chats(user_id: str):
    if not db_available():
        return {"chats": []}
    try:
        client = get_client()
        res = (
            client.table("chats")
            .select("id,title,created_at,updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(50)
            .execute()
        )
        return {"chats": res.data or []}
    except Exception:
        return {"chats": []}


@router.post("/chats")
def create_chat(req: ChatCreate):
    if not db_available():
        raise HTTPException(status_code=503, detail="Chat storage unavailable")
    try:
        client = get_client()
        res = (
            client.table("chats")
            .insert({"user_id": req.user_id, "title": (req.title or "New chat")[:80]})
            .execute()
        )
        if res.data:
            return {"id": res.data[0]["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=500, detail="Could not create chat")


@router.get("/chats/{chat_id}")
def get_chat(chat_id: str):
    if not db_available():
        return {"id": chat_id, "messages": []}
    try:
        client = get_client()
        res = (
            client.table("conversations")
            .select("role,content,created_at")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
            .execute()
        )
        msgs = [
            {"role": m["role"], "content": m["content"]}
            for m in (res.data or [])
            if m.get("content")
        ]
        title_res = (
            client.table("chats").select("title").eq("id", chat_id).limit(1).execute()
        )
        title = (title_res.data or [{}])[0].get("title") if title_res.data else None
        return {"id": chat_id, "title": title, "messages": msgs}
    except Exception:
        return {"id": chat_id, "messages": []}


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str):
    if db_available():
        try:
            client = get_client()
            client.table("conversations").delete().eq("chat_id", chat_id).execute()
            client.table("chats").delete().eq("id", chat_id).execute()
        except Exception:
            pass
    return {"ok": True}
