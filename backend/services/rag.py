import re

from backend.database.client import db_available, get_client

CHUNKS: list[dict] = []


def _split(text: str, size: int = 500) -> list[str]:
    text = text or ""
    if not text.strip():
        return []
    chunks = [text[i : i + size].strip() for i in range(0, len(text), size)]
    return [c for c in chunks if c]


def ingest(text: str, user_id: str, namespace: str = "general") -> None:
    """Chunk text and store in Supabase or in-memory fallback."""
    pieces = _split(text)
    if not pieces:
        return

    if db_available():
        try:
            client = get_client()
            rows = [
                {"content": p, "user_id": user_id, "namespace": namespace}
                for p in pieces
            ]
            client.table("doc_chunks").insert(rows).execute()
            return
        except Exception:
            pass

    for p in pieces:
        CHUNKS.append(
            {"content": p, "user_id": user_id, "namespace": namespace}
        )


def retrieve(
    query: str, user_id: str | None = None, k: int = 5
) -> list[str]:
    """Retrieve top-k relevant chunk contents."""
    query_terms = set(re.findall(r"\w+", (query or "").lower()))

    if db_available():
        try:
            client = get_client()
            q = client.table("doc_chunks").select("content, user_id")
            if user_id:
                q = q.eq("user_id", user_id)
            result = q.order("created_at").limit(k * 5).execute()
            rows = result.data or []
            scored = []
            for row in rows:
                content = row.get("content", "")
                score = sum(1 for t in query_terms if t in content.lower())
                if score > 0:
                    scored.append((score, content))
            scored.sort(key=lambda x: x[0], reverse=True)
            top = [c for _, c in scored[:k]]
            if top:
                return top
        except Exception:
            pass

    scored = []
    for chunk in CHUNKS:
        if user_id and chunk.get("user_id") != user_id:
            continue
        content = chunk.get("content", "")
        score = sum(1 for t in query_terms if t in content.lower())
        scored.append((score, content))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]
