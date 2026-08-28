import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.services.ai import stream_chat as ai_stream
from backend.services.rag import retrieve as rag_retrieve

from backend.database.client import db_available, get_client
from backend.database.seed import SEED_SCHOLARSHIPS


router = APIRouter()


class ChatReq(BaseModel):
    user_id: str = "demo"
    messages: List[dict]
    mode: str = "chat"
    language: str = "English"
    chat_id: Optional[str] = None


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
    "FORMATTING: Write clean friendly plain-text. No markdown asterisks or bullet glyphs. "
    "Short paragraphs, simple line breaks only."
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
            f"Deadline: {s.get('deadline')} | Apply: {s.get('application_link')}"
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
            .select("name,grade,language,school,board,college,dob,premium")
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


@router.post("/chat")
def chat(req: ChatReq):
    user_messages = [m for m in req.messages if m.get("role") == "user"]
    last_msg = user_messages[-1].get("content", "") if user_messages else ""

    ctx = []
    scholarship_block = ""
    try:
        ctx = rag_retrieve(last_msg, req.user_id) or []
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

    user_block = _user_context(req.user_id) or ""

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

    chat_id = _ensure_chat(req.user_id, req.chat_id, last_msg or "New chat")

    def event_stream():
        collected = []
        try:
            for token in ai_stream(full_messages):
                collected.append(token)
                yield token
        except Exception:
            err = (
                "\n\nI'm really sorry — I'm having a small hiccup connecting right "
                "now. Please send that again in a moment. 🙏"
            )
            yield err
            collected.append(err)
        finally:
            _persist_turn(req.user_id, chat_id, last_msg, "".join(collected))

    return StreamingResponse(event_stream(), media_type="text/plain; charset=utf-8")


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
