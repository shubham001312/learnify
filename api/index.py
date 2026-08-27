import os
import sys
import traceback

# Make the project root importable so `backend.main` resolves.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from backend.main import app as _app

    app = _app
except Exception:  # surface import failures as JSON instead of a blank 500
    _tb = traceback.format_exc()

    async def app(scope, receive, send):
        from starlette.responses import JSONResponse

        resp = JSONResponse(
            {"error": "import_failed", "traceback": _tb}, status_code=500
        )
        await resp(scope, receive, send)
