import os

from backend.database.client import db_available, get_client

GRAPHIFY_ENABLED = os.environ.get("GRAPHIFY_ENABLED", "").lower() in (
    "1",
    "true",
    "yes",
)


class MemoryStore:
    """Multi-layer user memory (user data, college, career, conversations)."""

    def __init__(self) -> None:
        self.store: dict[str, list[dict]] = {}

    def _layer(self, user_id: str, layer: int) -> list[dict]:
        self.store.setdefault(user_id, [])
        return [d for d in self.store[user_id] if d.get("layer") == layer]

    def add_user_data(self, user_id: str, data: dict) -> None:
        data = dict(data)
        data["layer"] = 1
        self.store.setdefault(user_id, []).append(data)

    def add_conversation(self, user_id: str, role: str, content: str) -> None:
        entry = {"layer": 4, "role": role, "content": content}
        self.store.setdefault(user_id, []).append(entry)
        if db_available():
            try:
                get_client().table("conversations").insert(
                    {"user_id": user_id, "role": role, "content": content}
                ).execute()
            except Exception:
                pass

    def add_college_context(self, user_id: str, text: str) -> None:
        self.store.setdefault(user_id, []).append({"layer": 2, "text": text})

    def add_career_criteria(self, user_id: str, text: str) -> None:
        self.store.setdefault(user_id, []).append({"layer": 3, "text": text})

    def get_context(self, user_id: str) -> str:
        """Assemble a readable multi-layer context string for Veda."""
        parts: list[str] = []
        local = self.store.get(user_id, [])

        l1 = [d for d in local if d.get("layer") == 1]
        if l1:
            parts.append("Layer 1 - User Data:")
            for d in l1:
                parts.append(f"  {d}")

        l2 = [d for d in local if d.get("layer") == 2]
        if l2:
            parts.append("Layer 2 - College Context:")
            for d in l2:
                parts.append(f"  {d.get('text', '')}")

        l3 = [d for d in local if d.get("layer") == 3]
        if l3:
            parts.append("Layer 3 - Career Criteria:")
            for d in l3:
                parts.append(f"  {d.get('text', '')}")

        l4 = [d for d in local if d.get("layer") == 4]
        if l4:
            parts.append("Layer 4 - Recent Conversation:")
            for d in l4[-6:]:
                parts.append(f"  {d.get('role')}: {d.get('content', '')}")

        if db_available():
            try:
                rows = (
                    get_client()
                    .table("memory")
                    .select("*")
                    .eq("user_id", user_id)
                    .limit(20)
                    .execute()
                )
                for r in rows.data or []:
                    parts.append(f"DB Memory: {r}")
            except Exception:
                pass

        return "\n".join(parts) if parts else "No memory yet."

    def sync_graphify(self) -> None:
        # TODO: run graphify CLI to build knowledge graph
        pass
