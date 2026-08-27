import os

import dotenv

dotenv.load_dotenv()

_client = None
_anon_client = None


def db_available() -> bool:
    return bool(os.environ.get("SUPABASE_URL")) and bool(
        os.environ.get("SUPABASE_SERVICE_KEY")
    )


def get_client():
    global _client
    if _client is None:
        from supabase import create_client

        _client = create_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
        )
    return _client


def get_anon_client():
    global _anon_client
    if _anon_client is None:
        from supabase import create_client

        _anon_client = create_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"]
        )
    return _anon_client
