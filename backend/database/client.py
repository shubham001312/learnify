import os

import dotenv

dotenv.load_dotenv()

_client = None
_anon_client = None


def db_available() -> bool:
    return bool(os.environ.get("SUPABASE_URL")) and bool(
        os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    )


def _make(url: str, key: str):
    from supabase import create_client

    # Apply a network timeout so a slow/unreachable Supabase fails fast instead
    # of hanging the request (and the serverless function) indefinitely.
    try:
        from supabase import ClientOptions

        opts = ClientOptions(postgrest_client_timeout=10, storage_client_timeout=10)
        return create_client(url, key, options=opts)
    except Exception:
        return create_client(url, key)


def get_client():
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get(
            "SUPABASE_ANON_KEY"
        )
        if not url or not key:
            return None
        _client = _make(url, key)
    return _client


def get_anon_client():
    global _anon_client
    if _anon_client is None:
        _anon_client = _make(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"]
        )
    return _anon_client
