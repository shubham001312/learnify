from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.ai import chat as ai_chat
from backend.services.rag import retrieve as rag_retrieve

from backend.services.memory import MemoryStore
from backend.database.seed import SEED_SCHOLARSHIPS


router = APIRouter()


class ChatReq(BaseModel):
    user_id: str = "demo"
    messages: List[dict]
    mode: str = "chat"
    language: str = "English"


SYSTEM_BASE = (
    "You are Veda, an AI study companion for Indian students. Be concise, "
    "warm, and academically rigorous.\n"
    "YOUR SCOPE IS STRICTLY EDUCATION: school/college subjects, exam preparation, "
    "career guidance, admissions, colleges, study planning, and scholarships for Indian "
    "students. You may help explain concepts and solve academic problems.\n"
    "You MUST REFUSE anything outside this scope: do NOT write or debug code, do NOT give "
    "relationship/ dating advice, do NOT discuss politics, news, or current affairs, do NOT "
    "do non-academic tasks. For such requests, politely reply that you only help with "
    "education and studies, and offer to help with a study-related topic instead.\n"
    "If the user asks about scholarships, financial aid, or 'what can I apply for', "
    "you MUST answer strictly from the REAL SCHOLARSHIP DATABASE given in the context. "
    "Do NOT invent schemes, do NOT use outside knowledge for scholarships, and NEVER "
    "mention KVPY (it is discontinued). If the database has nothing matching, say so "
    "honestly and suggest checking the Scholarships page and National Scholarship Portal."
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


@router.post("/chat")
def chat(req: ChatReq):
    user_messages = [m for m in req.messages if m.get("role") == "user"]
    last_msg = user_messages[-1].get("content", "") if user_messages else ""

    ctx = []
    memory = ""
    scholarship_block = ""
    try:
        ctx = rag_retrieve(last_msg, req.user_id) or []
    except Exception:
        ctx = []
    try:
        memory = MemoryStore().get_context(req.user_id) or ""
    except Exception:
        memory = ""

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

    context_block = ""
    if memory:
        context_block += f"\nUser memory:\n{memory}\n"
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
        + context_block
    )

    full_messages = [{"role": "system", "content": system_prompt}]
    full_messages.extend(req.messages)

    try:
        reply = ai_chat(full_messages)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Veda request failed: {e}")

    try:
        MemoryStore().add_conversation(req.user_id, req.messages)
    except Exception:
        pass

    return {
        "reply": reply,
        "sources": ctx[:2],
        "memory_updated": True,
    }
