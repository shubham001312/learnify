import base64
import gzip
import io
import json
import mimetypes
import re
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

try:
    from fastapi import File, Form, UploadFile

    _MULTIPART_OK = True
except Exception:
    _MULTIPART_OK = False

from backend.database.client import db_available, get_client
from backend.services.detector import detect_synthetic
from backend.services.rag import ingest as rag_ingest
from backend.services.ai import vision_extract, extract_marksheet
from backend.routes.auth import resolve_uid

router = APIRouter()

UPLOADS: list[dict] = []

SUBJECT_WORDS = [
    "english",
    "hindi",
    "mathematics",
    "maths",
    "math",
    "science",
    "physics",
    "chemistry",
    "biology",
    "social",
    "sst",
    "sanskrit",
    "history",
    "geography",
    "economics",
    "accountancy",
    "accounts",
    "business",
    "computer",
    "informatics",
    "political",
    "telugu",
    "tamil",
    "kannada",
    "malayalam",
    "marathi",
    "bengali",
    "punjabi",
    "gujarati",
    "urdu",
    "arabic",
    "french",
    "physical",
    "environmental",
    "information",
    "technology",
    "it",
    "ip",
    "statistics",
    "commerce",
]


def _detect_file_type(filename: str, mime: Optional[str]) -> str:
    fn = (filename or "").lower()
    if mime:
        if mime.startswith("image/"):
            return "image"
        if mime == "application/pdf":
            return "pdf"
    if fn.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")):
        return "image"
    if fn.endswith(".pdf"):
        return "pdf"
    if fn.endswith((".txt", ".md")):
        return "text"
    return "other"


def _extract_pdf_text(contents: bytes) -> str:
    # Try several PDF text extractors; return best effort.
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(contents))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        pass
    try:
        from PyPDF2 import PdfReader as P2

        reader = P2(io.BytesIO(contents))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        pass
    try:
        from pdfminer.high_level import extract_text

        return extract_text(io.BytesIO(contents))
    except Exception:
        pass
    return ""


def _extract_academic(text: str) -> dict:
    """Best-effort extraction of an exam marksheet into a structured record."""
    if not text:
        return {}
    lower = text.lower()
    rec: dict = {}

    if re.search(r"\b10th\b|\bclass 10\b|\bsslc\b|\bmatric|\bsecondary\b", lower):
        rec["exam"] = "10th"
    elif re.search(r"\b12th\b|\bclass 12\b|\binter\b|\bsenior secondary\b", lower):
        rec["exam"] = "12th"
    elif re.search(r"\bdiploma\b", lower):
        rec["exam"] = "Diploma"
    elif re.search(r"\bbachelor|\bdegree|\bgraduation|\bb\.tech|\bbe\b|\bbsc\b", lower):
        rec["exam"] = "Graduation"

    if "cbse" in lower:
        rec["board"] = "CBSE"
    elif "icse" in lower or "cisce" in lower:
        rec["board"] = "ICSE"
    elif "state" in lower:
        rec["board"] = "State Board"
    elif "isc" in lower:
        rec["board"] = "ISC"

    y = re.search(r"(20\d{2})", text)
    if y:
        rec["year"] = int(y.group(1))

    marks: dict = {}
    for line in text.splitlines():
        ll = line.lower()
        for subj in SUBJECT_WORDS:
            m = re.search(r"\b" + re.escape(subj) + r"\b[^\d\n]{0,20}?(\d{1,3})\b", ll)
            if m:
                val = int(m.group(1))
                if 0 <= val <= 100 and subj not in marks:
                    marks[subj.capitalize()] = val
    if marks:
        rec["marks"] = marks
        rec["total"] = sum(marks.values())
        rec["percentage"] = round(rec["total"] / (len(marks) * 100) * 100, 2)

    pct = re.search(r"percentage[^\d]{0,10}(\d{1,3}(?:\.\d{1,2})?)", lower)
    if pct:
        try:
            rec["percentage"] = float(pct.group(1))
        except Exception:
            pass
    return rec


def _merge_vision(acad: dict, vision_text: str) -> dict:
    try:
        # Strip code fences if the model wrapped JSON.
        raw = vision_text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            for k in ("exam", "board", "year", "marks", "total", "percentage"):
                if parsed.get(k) not in (None, "", {}):
                    acad[k] = parsed[k]
    except Exception:
        pass
    return acad


def _compress_file(contents: bytes, ftype: str, filename: str):
    """Return (file_data_b64, file_type_tag) for owner preview. None if too big/unavailable."""
    try:
        if ftype == "image":
            from PIL import Image

            img = Image.open(io.BytesIO(contents))
            img.thumbnail((1000, 1000))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80, optimize=True)
            return base64.b64encode(buf.getvalue()).decode("ascii"), "image"
        if ftype == "pdf":
            gz = gzip.compress(contents, 6)
            if len(gz) <= 700_000:
                return base64.b64encode(gz).decode("ascii"), "pdf"
    except Exception:
        pass
    return None, ftype


if _MULTIPART_OK:

    @router.post("/upload")
    def upload(
        file: UploadFile = File(...),
        authorization: Optional[str] = Header(None, alias="Authorization"),
    ):
        try:
            uid = resolve_uid(authorization) or "demo"
            filename = file.filename or "document.bin"
            contents = file.file.read()
            mime = file.content_type or mimetypes.guess_type(filename)[0]
            ftype = _detect_file_type(filename, mime)

            # synthetic detection only for text-like files
            text = ""
            if ftype in ("pdf", "text"):
                if ftype == "pdf":
                    text = _extract_pdf_text(contents)
                else:
                    text = contents.decode("utf-8", errors="ignore")
                detection = detect_synthetic(filename, text)
                if detection.get("is_synthetic", False):
                    return {
                        "document_id": None,
                        "is_synthetic": True,
                        "extracted": {},
                        "message": "Please re-upload a genuine document.",
                    }

            acad: dict = {}
            if ftype == "image":
                b64 = base64.b64encode(contents).decode("ascii")
                prompt = (
                    "Read this academic marksheet / result image. Reply with ONLY a JSON "
                    "object (no markdown) of this exact shape: "
                    '{"exam":"10th|12th|Diploma|Graduation|Other",'
                    '"board":"CBSE|ICSE|State Board|ISC|Other",'
                    '"year":YYYY,"marks":{"Subject":score_number},'
                    '"total":number,"percentage":number}. '
                    "If no marks are visible, return "
                    '{"exam":null,"board":null,"marks":{}}. Only output JSON.'
                )
                try:
                    vision_text = vision_extract(b64, mime or "image/jpeg", prompt)
                    acad = _merge_vision({}, vision_text)
                except Exception:
                    acad = {}
            elif ftype == "pdf":
                acad = extract_marksheet(text) or _extract_academic(text)
            elif ftype == "text":
                acad = extract_marksheet(text) or _extract_academic(text)

            rag_ingest((text or filename), uid, "document")

            doc_id = f"doc-{uuid.uuid4().hex[:12]}"
            file_data, stored_type = _compress_file(contents, ftype, filename)

            client = get_client() if db_available() else None
            db_note = None
            if client:
                try:
                    result = (
                        client.table("documents")
                        .insert(
                            {
                                "user_id": uid,
                                "filename": filename,
                                "file_type": stored_type,
                                "file_data": file_data,
                                "is_synthetic": False,
                                "extracted": acad or {},
                            }
                        )
                        .execute()
                    )
                    if getattr(result, "error", None):
                        db_note = "documents: " + str(result.error)[:400]
                except Exception as e:
                    db_note = "documents: " + str(e)[:400]
                if acad:
                    try:
                        result = (
                            client.table("academic_records")
                            .insert(
                                {
                                    "user_id": uid,
                                    "doc_id": doc_id,
                                    "exam": acad.get("exam"),
                                    "board": acad.get("board"),
                                    "year": acad.get("year"),
                                    "marks": acad.get("marks"),
                                    "total": acad.get("total"),
                                    "percentage": acad.get("percentage"),
                                    "raw_text": (text or "")[:4000],
                                    "verified": True,
                                }
                            )
                            .execute()
                        )
                        if getattr(result, "error", None):
                            db_note = (
                                (db_note + "; " if db_note else "")
                                + "academic: "
                                + str(result.error)[:400]
                            )
                    except Exception as e:
                        db_note = (
                            (db_note + "; " if db_note else "")
                            + "academic: "
                            + str(e)[:400]
                        )

            UPLOADS.append(
                {
                    "id": doc_id,
                    "filename": filename,
                    "file_type": stored_type,
                    "is_synthetic": False,
                    "extracted": acad,
                }
            )
            return {
                "document_id": doc_id,
                "is_synthetic": False,
                "extracted": acad,
                "db_note": db_note,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


def _is_uuid(v: str) -> bool:
    return bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-", v or ""))


class AcadUpdate(BaseModel):
    exam: Optional[str] = None
    board: Optional[str] = None
    year: Optional[int] = None
    marks: Optional[dict] = None
    total: Optional[float] = None
    percentage: Optional[float] = None


@router.patch("/academic/{record_id}")
def update_academic(
    record_id: str,
    req: AcadUpdate,
    authorization: Optional[str] = None,
):
    uid = resolve_uid(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not db_available():
        raise HTTPException(status_code=503, detail="Storage unavailable")
    client = get_client()
    existing = (
        client.table("academic_records")
        .select("user_id")
        .eq("id", record_id)
        .limit(1)
        .execute()
    )
    if not existing.data or existing.data[0]["user_id"] != uid:
        raise HTTPException(status_code=403, detail="Not allowed")
    update = {k: v for k, v in req.dict(exclude_unset=True).items() if v is not None}
    if not update:
        return {"ok": True}
    res = client.table("academic_records").update(update).eq("id", record_id).execute()
    return {"ok": True, "record": (res.data or [{}])[0]}


@router.get("")
def list_documents(authorization: Optional[str] = Header(None, alias="Authorization")):
    uid = resolve_uid(authorization)
    if not uid or not db_available():
        return {"documents": []}
    try:
        client = get_client()
        result = (
            client.table("documents")
            .select(
                "id, filename, file_type, file_data, is_synthetic, extracted, created_at"
            )
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .execute()
        )
        return {"documents": result.data or []}
    except Exception:
        return {"documents": []}


@router.get("/academic")
def list_academic(authorization: Optional[str] = Header(None, alias="Authorization")):
    uid = resolve_uid(authorization)
    if not uid or not db_available():
        return {"records": []}
    try:
        client = get_client()
        res = (
            client.table("academic_records")
            .select("*")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .execute()
        )
        return {"records": res.data or []}
    except Exception:
        return {"records": []}
