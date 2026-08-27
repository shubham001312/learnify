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
    import json
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.exception_handler(Exception)
    async def _h(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "traceback": traceback.format_exc()},
        )

    @app.get("/api/health")
    async def _health():
        return {"status": "error", "detail": repr(e)}
