import secrets
import string

# Ambiguous characters removed (0/O, 1/I, etc.) for readability.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _rand(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def generate_uid(is_taken, length: int = 7):
    """Return a random, unique, non-repeating id of exactly `length` chars.

    `is_taken(uid) -> bool` lets the caller guarantee global uniqueness
    against the existing store (Supabase table or local file).
    """
    length = max(7, int(length))
    while True:
        uid = _rand(length)
        if not is_taken(uid):
            return uid
