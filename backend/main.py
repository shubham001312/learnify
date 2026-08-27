import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI(title="Learnify")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/health")
def health():
    return {"status": "ok", "app": "learnify"}


from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as _FastAPIHTTPException


@app.exception_handler(Exception)
async def _global_exception(request: Request, exc: Exception):
    if isinstance(exc, _FastAPIHTTPException):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    import traceback as _tb

    return JSONResponse(
        {
            "error": str(exc),
            "type": type(exc).__name__,
            "traceback": _tb.format_exc(),
        },
        status_code=500,
    )


@app.get("/")
def root():
    index_path = os.path.join(PUBLIC_DIR, "index.html")
    if os.path.isfile(index_path):
        from fastapi.responses import FileResponse

        return FileResponse(index_path)
    return {"status": "ok", "app": "learnify"}


try:
    from backend.routes import auth, veda, colleges, documents, premium, search, scanned

    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(veda.router, prefix="/api/veda")
    app.include_router(colleges.router, prefix="/api")
    app.include_router(documents.router, prefix="/api/documents")
    app.include_router(premium.router, prefix="/api/premium")
    app.include_router(search.router, prefix="/api")
    app.include_router(scanned.router, prefix="/api")
except Exception as e:
    import traceback as _tb

    print(f"[learnify] router import skipped: {e}\n{_tb.format_exc()}")


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
