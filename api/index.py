import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

app = None
try:
    from backend.main import app  # noqa: E402
except Exception as e:  # surface import errors instead of silent 500
    import logging

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    logging.getLogger("learnify").exception("backend.main failed to import")
    app = FastAPI()

    @app.exception_handler(Exception)
    async def _h(request: Request, exc: Exception):
        # Do not leak internals — log server-side, return a generic message.
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": "import failed"},
        )

    @app.get("/api/health")
    async def _health():
        return {"status": "error", "detail": repr(e)}
