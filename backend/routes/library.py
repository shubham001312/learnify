"""Trainer library + file uploads (Supabase Storage).

Three library types: RECORDED_LECTURE · PRESENTATION · STUDY_MATERIAL.
Videos may also be referenced by YouTube link instead of uploaded.

Enforced server-side (this storage-api build ignores bucket-level limits, so
the rules below are the real boundary):
    * 100 MB cap for video, 50 MB for documents/attachments
    * 5 MB cap for avatars and course covers (images only)
    * an allow-list of MIME types per bucket
    * files are stored under a per-uploader prefix so one trainer can never
      read or delete another's object by guessing a path
"""

import mimetypes
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, UploadFile, File, Form
from pydantic import BaseModel, Field

from backend.middleware.rbac import ALPHA, MASTER, SUPREME, _extract_user, require_role
from backend.services import db

router = APIRouter(prefix="/library", tags=["library"])

VIDEO_MB = 100
DOC_MB = 50
COVER_MB = 5
KB = 1024
VIDEO_LIMIT = VIDEO_MB * KB * KB
DOC_LIMIT = DOC_MB * KB * KB
COVER_LIMIT = COVER_MB * KB * KB

VIDEO_MIMES = {"video/mp4", "video/webm", "video/quicktime", "video/x-matroska",
               "video/x-msvideo"}
DOC_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.ms-powerpoint",
    "application/vnd.ms-excel",
    "image/png", "image/jpeg", "image/webp",
    "text/plain",
}
IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp"}
COVER_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif",
               "image/svg+xml"}

BUCKET_LIBRARY = "trainer-library"
BUCKET_ATTACH = "course-attachments"
BUCKET_AVATARS = "avatars"
BUCKET_COVERS = "course-covers"

# Every bucket this endpoint accepts (mirrors storage.buckets in schema.sql).
UPLOAD_BUCKETS = (BUCKET_LIBRARY, BUCKET_ATTACH, BUCKET_AVATARS, BUCKET_COVERS)
# Buckets with storage.buckets.public = true: their objects are served straight
# from /storage/v1/object/public/<bucket>/<path>, so the upload response can
# hand back a ready-to-render URL instead of forcing a signed-URL round trip.
PUBLIC_BUCKETS = (BUCKET_AVATARS, BUCKET_COVERS)

FILE_TYPES = ("RECORDED_LECTURE", "PRESENTATION", "STUDY_MATERIAL")

YOUTUBE_RE = __import__("re").compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,20})"
)


def _auth(authorization: Optional[str] = Header(None)):
    return _extract_user(authorization)


class LibraryIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    file_type: str = Field(pattern="^(RECORDED_LECTURE|PRESENTATION|STUDY_MATERIAL)$")
    subject_id: str = ""
    youtube_url: str = Field(default="", max_length=400)
    duration_seconds: int = Field(default=0, ge=0, le=86400)


class LibraryUpdate(LibraryIn):
    pass


# ─── Upload ────────────────────────────────────────────────────────────────
def _guess_mime(name: str, declared: str) -> str:
    mt = (declared or "").split(";")[0].strip().lower()
    if mt and mt != "application/octet-stream":
        return mt
    guessed, _ = mimetypes.guess_type(name or "")
    return (guessed or "application/octet-stream").lower()


def _check(name: str, declared: str, size: int, bucket: str) -> tuple[str, int, int]:
    """Validate and return (mime, limit, size). Raises db.Rejected on failure."""
    mime = _guess_mime(name, declared)
    if bucket == BUCKET_LIBRARY:
        allowed, limit = VIDEO_MIMES | DOC_MIMES, VIDEO_LIMIT
        doc_limit = DOC_LIMIT
    elif bucket == BUCKET_ATTACH:
        # Course slots hold lesson videos as well as handout attachments, so
        # this bucket keeps the video cap (100 MB) and the document cap (50 MB).
        allowed, limit = VIDEO_MIMES | DOC_MIMES, VIDEO_LIMIT
        doc_limit = DOC_LIMIT
    elif bucket == BUCKET_COVERS:
        # Course thumbnail (courses.cover_image_url): images only, 5 MB.
        allowed, limit = COVER_MIMES, COVER_LIMIT
        doc_limit = limit
    else:
        allowed, limit = IMAGE_MIMES, 5 * KB * KB
        doc_limit = limit

    if mime not in allowed:
        pretty = ", ".join(sorted(a.split("/")[-1] for a in allowed))
        raise db.Rejected(
            f"'{mime}' is not an accepted file type here. Allowed: {pretty}.")

    effective = limit if mime in VIDEO_MIMES else doc_limit
    if size > effective:
        mb = effective // (KB * KB)
        hint = (" Paste a YouTube link for larger videos."
                if bucket in (BUCKET_LIBRARY, BUCKET_ATTACH) else "")
        raise db.Rejected(
            f"File is {size / (KB * KB):.1f} MB; the limit is {mb} MB.{hint}")
    if size <= 0:
        raise db.Rejected("The file appears to be empty.")
    return mime, effective, size


def _safe_name(filename: str) -> str:
    """Strip directories and anything that could alter a storage path."""
    base = (filename or "file").replace("\\", "/").split("/")[-1]
    cleaned = "".join(ch for ch in base if ch.isalnum() or ch in "._- ()")
    cleaned = cleaned.strip(". ") or "file"
    return cleaned[:120]


@router.post("/upload")
async def upload(
    authorization: Optional[str] = Header(None),
    file: UploadFile = File(...),
    bucket: str = Form(default=BUCKET_LIBRARY),
    kind: str = Form(default=""),
):
    """Upload one object, then (optionally) register it as a library item.

    The response returns the storage path; the caller saves metadata with
    POST /library so a failed metadata write never orphans silently.
    Objects landing in a public bucket also come back with `public_url`.
    """
    user = _auth(authorization)
    if bucket not in UPLOAD_BUCKETS:
        raise db.Rejected("Unknown upload destination.")

    # Trainees may attach nothing; only trainers/supreme upload content.
    # Covers belong to the course wizard, which trainees never reach.
    if bucket in (BUCKET_LIBRARY, BUCKET_ATTACH, BUCKET_COVERS) \
            and user["role"] == ALPHA:
        raise db.Denied("Only trainers can upload content.")

    raw = await file.read()
    size = len(raw)
    name = _safe_name(file.filename or "file")
    mime, limit, size = _check(name, file.content_type or "", size, bucket)

    if bucket == BUCKET_LIBRARY and kind and kind not in FILE_TYPES:
        raise db.Rejected("Unknown library item type.")

    from backend.database.client import get_client
    client = get_client()
    if client is None:
        raise _unavailable("Storage is unavailable (Supabase not configured).")

    folder = user["uid"]
    path = f"{folder}/{uuid.uuid4().hex[:12]}_{name}"

    try:
        client.storage.from_(bucket).upload(path, raw, {
            "content-type": mime,
            "x-upsert": "false",
        })
    except Exception as e:
        msg = str(e)
        if "exceeded" in msg.lower() or "413" in msg:
            tail = (" Use a YouTube link for larger videos."
                    if bucket in (BUCKET_LIBRARY, BUCKET_ATTACH) else "")
            raise db.Rejected(
                f"File exceeds the {limit // (KB * KB)} MB limit.{tail}")
        raise _unavailable(f"Upload failed: {msg[:200]}")

    db.audit(user["uid"], "storage.upload", bucket, path,
             {"bytes": size, "mime": mime})
    body = {
        "storage_path": path, "bucket": bucket, "filename": name,
        "mime": mime, "size_bytes": size, "owner": folder,
    }
    # Public buckets (avatars, course covers) are directly renderable: hand the
    # caller a ready-to-use URL. Private buckets keep needing /files/sign.
    if bucket in PUBLIC_BUCKETS:
        body["public_url"] = client.storage.from_(bucket).get_public_url(path)
    return db.ok(body)


@router.delete("/files")
def delete_file(path: str = Query(max_length=600),
                bucket: str = Query(default=BUCKET_LIBRARY, max_length=40),
                user=Depends(_auth)):
    """Delete an object — but only if the caller owns its path prefix."""
    if not path:
        raise db.Rejected("No path given.")
    if path.startswith(f"{user['uid']}/") is False and user["role"] != SUPREME:
        raise db.Denied("You can only remove your own uploads.")
    if bucket not in UPLOAD_BUCKETS:
        raise db.Rejected("Unknown bucket.")

    from backend.database.client import get_client
    client = get_client()
    if client is None:
        raise _unavailable("Storage unavailable.")
    try:
        client.storage.from_(bucket).remove([path])
    except Exception:
        pass  # already gone counts as deleted
    db.audit(user["uid"], "storage.delete", bucket, path)
    return db.ok({"deleted": True})


@router.get("/files/sign")
def signed_url(path: str = Query(max_length=600),
               bucket: str = Query(default=BUCKET_LIBRARY, max_length=40),
               expires: int = Query(default=3600, ge=60, le=86400),
               user=Depends(_auth)):
    """Short-lived URL for a private object (videos and attachments)."""
    if not path:
        raise db.Rejected("No path given.")
    if bucket not in UPLOAD_BUCKETS:
        raise db.Rejected("Unknown bucket.")
    _assert_readable(path, bucket, user)

    from backend.database.client import get_client
    client = get_client()
    if client is None:
        raise _unavailable("Storage unavailable.")
    try:
        res = client.storage.from_(bucket).create_signed_url(path, expires)
        url = res.get("signedURL") if isinstance(res, dict) else getattr(
            res, "signed_url", None)
        if not url and isinstance(res, dict):
            url = res.get("signedURL") or res.get("signed_url")
        if not url:
            raise _unavailable("Could not sign that file.")
        return db.ok({"url": url, "expires_in": expires})
    except Exception as e:
        if isinstance(e, (db.Rejected, db.Denied)):
            raise
        raise _unavailable(f"Could not sign URL: {str(e)[:200]}")


def _assert_readable(path: str, bucket: str, user: dict):
    """Owners always read their own; everyone else needs a linked resource."""
    if path.startswith(f"{user['uid']}/"):
        return
    # Public buckets (avatars, course covers) are served without auth anyway,
    # so any signed-in caller may ask for a URL — no ownership needed.
    if bucket in PUBLIC_BUCKETS:
        return
    if user["role"] == SUPREME:
        return
    # A Master may read objects attached to content they can see, or any
    # library item (the library is a shared resource for trainers).
    if bucket in (BUCKET_LIBRARY, BUCKET_ATTACH) and user["role"] == MASTER:
        return
    # ALPHA: only files belonging to a course they are enrolled in.
    if bucket == BUCKET_ATTACH:
        att = db.first("slot_attachments",
                       "slot_id, storage_path", eq={"storage_path": path})
        if att:
            mod = db.first("course_modules", "course_id",
                           eq={"id": att["slot_id"]})
            course = db.first("courses", "status",
                              eq={"id": mod["course_id"]}) if mod else None
            if course and course.get("status") == "PUBLISHED":
                enr = db.first("enrollments", "id",
                               eq={"course_id": mod["course_id"],
                                   "trainee_id": user["uid"]})
                if enr:
                    return
        raise db.Denied("You are not enrolled in the course that owns this file.")
    if bucket == BUCKET_LIBRARY:
        raise db.Denied("This file is not available to you.")
    raise db.Denied("You cannot access this file.")


def _unavailable(msg: str):
    from fastapi import HTTPException
    return HTTPException(status_code=503, detail=msg)


# ─── Library CRUD ──────────────────────────────────────────────────────────
def _public(row: dict, user: dict) -> dict:
    subj = db.first("subjects", "id, code, name",
                    eq={"id": row.get("subject_id")}) if row.get("subject_id") else None
    trainer = db.first("users", "id, name, designation",
                       eq={"id": row.get("trainer_id")}) or {}
    return {
        **row,
        "subject_name": (subj or {}).get("name", ""),
        "trainer_name": trainer.get("name", ""),
        "trainer_designation": trainer.get("designation", ""),
        "can_edit": bool(user["role"] == SUPREME
                         or row.get("trainer_id") == user["uid"]),
        "has_youtube": bool(row.get("youtube_id")),
        "size_mb": round(float(row.get("size_bytes") or 0) / (1024 * 1024), 2),
    }


@router.get("")
def list_library(
    file_type: str = Query(default="", max_length=40),
    subject_id: str = Query(default="", max_length=60),
    mine: bool = False,
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=60, ge=1, le=200),
    user=Depends(_auth),
):
    eq: dict = {}
    if mine:
        eq["trainer_id"] = user["uid"]
    if file_type:
        eq["file_type"] = file_type
    if subject_id:
        eq["subject_id"] = subject_id

    rows, total = db.select("library_items", "*", eq=eq or None,
                            order=("created_at", True), limit=limit, count=True)
    if q:
        ql = q.lower()
        rows = [r for r in rows
                if ql in (r.get("title", "") or "").lower()
                or ql in (r.get("description", "") or "").lower()]
    return db.ok([_public(r, user) for r in rows],
                 meta={"total": total or len(rows)})


@router.get("/{item_id}")
def get_item(item_id: str, user=Depends(_auth)):
    row = db.first("library_items", "*", eq={"id": item_id})
    if not row:
        raise db.NotFound("Item not found")
    return db.ok(_public(row, user))


@router.post("")
def create_item(payload: LibraryIn, user=Depends(require_role(MASTER, SUPREME))):
    """Register metadata for an already-uploaded file, or a YouTube item."""
    yt = ""
    if payload.youtube_url.strip():
        m = YOUTUBE_RE.search(payload.youtube_url.strip())
        if not m:
            raise db.Rejected("That does not look like a YouTube link.")
        yt = m.group(1)
        if payload.file_type not in ("RECORDED_LECTURE",):
            raise db.Rejected("YouTube links are only for recorded lectures.")

    row = db.insert("library_items", {
        "trainer_id": user["uid"],
        "subject_id": payload.subject_id or None,
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "file_type": payload.file_type,
        "storage_path": "", "bucket": BUCKET_LIBRARY,
        "youtube_id": yt or None,
        "duration_seconds": payload.duration_seconds,
        "mime": "", "size_bytes": 0,
    })
    db.audit(user["uid"], "library.create", "library_item", row.get("id"))
    return db.ok(row)


@router.post("/{item_id}/attach-file")
def attach_file(item_id: str, payload: dict, user=Depends(require_role(MASTER, SUPREME))):
    """Bind an uploaded object to an existing library item."""
    row = db.first("library_items", "*, trainer_id", eq={"id": item_id})
    if not row:
        raise db.NotFound("Item not found")
    if user["role"] != SUPREME and row.get("trainer_id") != user["uid"]:
        raise db.Denied("That item belongs to another trainer.")
    path = str((payload or {}).get("storage_path") or "")
    if not path:
        raise db.Rejected("storage_path is required.")
    if not path.startswith(f"{user['uid']}/") and user["role"] != SUPREME:
        raise db.Denied("That file was not uploaded by you.")

    rows = db.update("library_items", {
        "storage_path": path,
        "mime": str((payload or {}).get("mime") or row.get("mime") or ""),
        "size_bytes": int((payload or {}).get("size_bytes") or 0),
        "youtube_id": None,
    }, id=item_id)
    return db.ok(rows[0] if rows else None)


@router.put("/{item_id}")
def update_item(item_id: str, payload: LibraryUpdate,
                user=Depends(require_role(MASTER, SUPREME))):
    row = db.first("library_items", "*, trainer_id", eq={"id": item_id})
    if not row:
        raise db.NotFound("Item not found")
    if user["role"] != SUPREME and row.get("trainer_id") != user["uid"]:
        raise db.Denied("That item belongs to another trainer.")
    rows = db.update("library_items", {
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "file_type": payload.file_type,
        "subject_id": payload.subject_id or None,
        "duration_seconds": payload.duration_seconds,
    }, id=item_id)
    return db.ok(rows[0] if rows else None)


@router.delete("/{item_id}")
def delete_item(item_id: str, user=Depends(require_role(MASTER, SUPREME))):
    row = db.first("library_items", "*, trainer_id", eq={"id": item_id})
    if not row:
        raise db.NotFound("Item not found")
    if user["role"] != SUPREME and row.get("trainer_id") != user["uid"]:
        raise db.Denied("That item belongs to another trainer.")
    path = row.get("storage_path") or ""
    if path:
        from backend.database.client import get_client
        client = get_client()
        if client is not None:
            try:
                client.storage.from_(row.get("bucket") or BUCKET_LIBRARY).remove([path])
            except Exception:
                pass
    db.delete("library_items", id=item_id)
    db.audit(user["uid"], "library.delete", "library_item", item_id)
    return db.ok({"deleted": True})


@router.get("/{item_id}/stats")
def item_stats(item_id: str, user=Depends(_auth)):
    """Content-level feedback aggregate (average stars + count)."""
    db.first("library_items", "id", eq={"id": item_id}) \
        or (_raise_404())
    rows, _ = db.select("content_feedback", "rating, comment, created_at, trainee_id",
                        eq={"content_type": "LIBRARY", "content_id": item_id},
                        order=("created_at", True), limit=200)
    return db.ok(_rating_summary(rows, user))


def _raise_404():
    raise db.NotFound("Item not found")


def _rating_summary(rows: list[dict], user: dict) -> dict:
    mine = next((r for r in rows if r.get("trainee_id") == user["uid"]), None)
    ratings = [r["rating"] for r in rows if r.get("rating")]
    return {
        "average": round(sum(ratings) / len(ratings), 2) if ratings else 0,
        "count": len(ratings),
        "my_rating": (mine or {}).get("rating"),
        "my_comment": (mine or {}).get("comment", ""),
        "recent": [{"rating": r.get("rating"), "comment": r.get("comment", ""),
                    "created_at": r.get("created_at")} for r in rows[:10]],
    }
