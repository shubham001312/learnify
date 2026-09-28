import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.middleware.ratelimit import gate as _rate_limit_gate

load_dotenv()

app = FastAPI(title="Learnify")

# ─── CORS ───────────────────────────────────────────────────────────────────
# Credentials are only ever sent to our own origins. Unknown origins get no
# CORS headers, so a hostile page cannot call the API with the user's cookies.
_env_origins = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,https://learnify.hosteler.shop",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_env_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def no_cache_static(request, call_next):
    resp = await call_next(request)
    p = request.url.path
    if (
        p == "/"
        or p.startswith("/src")
        or p.startswith("/assets")
        or p.endswith(".js")
        or p.endswith(".css")
    ):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.middleware("http")
async def rate_limit(request, call_next):
    # Registered after no_cache_static so it is the outermost layer and a
    # flood is refused before any handler work happens. Meters login,
    # register and change-password only — see middleware/ratelimit.py.
    blocked = _rate_limit_gate(request)
    if blocked is not None:
        return blocked
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok", "app": "learnify"}


# ─── Error contract ────────────────────────────────────────────────────────
# Success  → {"success": true,  "data": ..., "error": null}
# Failure  → {"success": false, "data": null, "error": "...", "detail": "..."}
# `detail` mirrors `error` so clients written against FastAPI's default shape
# keep working, while `error` matches the success envelope's field.
#
# The domain exceptions in backend/services/db.py document the status each one
# should produce. Registering them here means routes can simply
# `raise db.NotFound(...)` instead of hand-rolling HTTP plumbing — and, before
# these handlers existed, every 404/403/400 in the API surfaced as a 500.
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.services import db as _db  # noqa: E402


def _error(message: str, status: int) -> JSONResponse:
    message = str(message or "").strip() or "Request failed"
    return JSONResponse(
        {"success": False, "data": None, "error": message, "detail": message},
        status_code=status,
    )


@app.exception_handler(_db.NotFound)
async def _h_not_found(request: Request, exc: _db.NotFound):
    return _error(str(exc) or "Not found", 404)


@app.exception_handler(_db.Denied)
async def _h_denied(request: Request, exc: _db.Denied):
    return _error(str(exc) or "You do not have access to this resource.", 403)


@app.exception_handler(_db.Rejected)
async def _h_rejected(request: Request, exc: _db.Rejected):
    return _error(getattr(exc, "detail", None) or str(exc) or "Invalid request",
                  400)


@app.exception_handler(_db.Unavailable)
async def _h_unavailable(request: Request, exc: _db.Unavailable):
    # The database link dropped mid-request. 400 would tell the client its
    # request was malformed and stop it retrying; 503 says "ours, try again".
    return _error(str(exc) or "The service is temporarily unavailable. Please try again.",
                  503)


@app.exception_handler(StarletteHTTPException)
async def _h_http(request: Request, exc: StarletteHTTPException):
    # Auth/RBAC raise HTTPException; keep the code, normalise the body.
    return _error(str(exc.detail or "Request failed"), exc.status_code)


@app.exception_handler(RequestValidationError)
async def _h_validation(request: Request, exc: RequestValidationError):
    # FastAPI's default 422 body is {"detail": [{"loc":…, "msg":…}]}, which
    # the frontend reads as `data.detail` and stringifies to "[object
    # Object]". Collapse it to one readable line in our own envelope.
    errs = exc.errors() or []
    first = errs[0] if errs else {}
    field = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    message = (f"{field}: {first.get('msg', '')}" if field
               else str(first.get("msg") or "Invalid request"))
    if len(errs) > 1:
        message += f" (and {len(errs) - 1} more problem{'' if len(errs) == 2 else 's'})"
    return _error(message, 422)


@app.exception_handler(Exception)
async def _global_exception(request: Request, exc: Exception):
    # Never leak internals (tracebacks, SQL, paths) to the client.
    import logging
    import traceback as _tb

    logging.getLogger("learnify").exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    print(_tb.format_exc())
    return _error("Internal server error", 500)


# ─── Routers ────────────────────────────────────────────────────────────────
# Only Learnify modules are mounted. Learnify-era routers (colleges,
# careers, scholarships, veda, premium, documents, search, scanned, sgpa,
# internships, mentor, milestones, evaluations, portfolio, career_intelligence,
# opportunities, skills, student_profile, analytics, learning) are removed.
def _mount():
    from fastapi import APIRouter

    from backend.routes import auth, notifications

    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(notifications.router, prefix="/api/v1")

    # Feature routers are registered as they land in each phase; a missing
    # module must never take the whole server down.
    optional = [
        ("profiles", "/api/v1"),
        ("subjects", "/api/v1"),
        ("competency", "/api/v1"),
        ("courses", "/api/v1"),
        ("questionnaires", "/api/v1"),
        ("assessments", "/api/v1"),
        ("ai", "/api/v1"),
        ("library", "/api/v1"),
        ("feedback", "/api/v1"),
        ("feed", "/api/v1"),
        ("reports", "/api/v1"),
        ("admin", "/api/v1"),
        ("participation", "/api/v1"),
    ]
    for name, prefix in optional:
        try:
            mod = __import__(f"backend.routes.{name}", fromlist=["router"])
            router = getattr(mod, "router", None)
            if isinstance(router, APIRouter):
                app.include_router(router, prefix=prefix)
        except ImportError:
            continue
        except Exception as e:  # noqa: BLE001
            import traceback as _tb

            print(f"[learnify] router '{name}' failed: {e}\n{_tb.format_exc()}")


try:
    _mount()
except Exception as e:  # noqa: BLE001
    import traceback as _tb

    print(f"[learnify] router setup skipped: {e}\n{_tb.format_exc()}")


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

if os.path.isdir(PUBLIC_DIR):
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
    app.mount(
        "/src", StaticFiles(directory=os.path.join(PUBLIC_DIR, "src")), name="src"
    )
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(PUBLIC_DIR, "assets")),
        name="assets",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
