import re
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException

try:
    from fastapi import File, Form, UploadFile

    _MULTIPART_OK = True
except Exception:
    _MULTIPART_OK = False

from backend.database.client import db_available, get_client
from backend.services.detector import detect_synthetic
from backend.services.rag import ingest as rag_ingest
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
]


def _extract_academic(text: str) -> dict:
    """Best-effort extraction of an exam marksheet into a structured record."""
    if not text:
        return {}
    lower = text.lower()
    rec: dict = {}

    # Exam label
    if re.search(r"\b10th\b|\bclass 10\b|\bsslc\b|\bmatric|\bsecondary\b", lower):
        rec["exam"] = "10th"
    elif re.search(r"\b12th\b|\bclass 12\b|\binter\b|\bsenior secondary\b", lower):
        rec["exam"] = "12th"
    elif re.search(r"\bdiploma\b", lower):
        rec["exam"] = "Diploma"

    # Board
    if "cbse" in lower:
        rec["board"] = "CBSE"
    elif "icse" in lower or "cisce" in lower:
        rec["board"] = "ICSE"
    elif "state" in lower:
        rec["board"] = "State Board"

    # Year
    y = re.search(r"(20\d{2})", text)
    if y:
        rec["year"] = int(y.group(1))

    # Subject -> marks. Heuristic: lines with a subject word and a 0-100 number.
    marks: dict = {}
    for line in text.splitlines():
        ll = line.lower()
        for subj in SUBJECT_WORDS:
            # subject appears as a standalone word, followed by a number <=100
            m = re.search(r"\b" + re.escape(subj) + r"\b[^\d\n]{0,20}?(\d{1,3})\b", ll)
            if m:
                val = int(m.group(1))
                if 0 <= val <= 100 and subj not in marks:
                    marks[subj.capitalize()] = val
    if marks:
        rec["marks"] = marks
        rec["total"] = sum(marks.values())
        rec["percentage"] = round(rec["total"] / (len(marks) * 100) * 100, 2)

    # Explicit percentage / total if present
    pct = re.search(r"percentage[^\d]{0,10}(\d{1,3}(?:\.\d{1,2})?)", lower)
    if pct:
        try:
            rec["percentage"] = float(pct.group(1))
        except Exception:
            pass
    return rec


if _MULTIPART_OK:

    @router.post("/upload")
    def upload(
        file: UploadFile = File(...),
        authorization: Optional[str] = None,
    ):
        try:
            uid = resolve_uid(authorization) or "demo"
            filename = file.filename or "document.bin"
            contents = file.file.read()
            try:
                text = contents.decode("utf-8", errors="ignore")
            except Exception:
                text = filename

            detection = detect_synthetic(filename, text)
            is_synthetic = detection.get("is_synthetic", False)
            if is_synthetic:
                return {
                    "document_id": None,
                    "is_synthetic": True,
                    "extracted": {},
                    "message": "Please re-upload a genuine document.",
                }

            rag_ingest(text or filename, uid, "document")

            acad = _extract_academic(text)
            doc_id = f"doc-{uuid.uuid4().hex[:12]}"

            client = get_client() if db_available() else None
            if client:
                try:
                    client.table("documents").insert(
                        {
                            "id": doc_id if _is_uuid(doc_id) else None,
                            "user_id": uid,
                            "filename": filename,
                            "is_synthetic": False,
                            "extracted": acad or {},
                        }
                    ).execute()
                except Exception:
                    pass
                if acad:
                    try:
                        client.table("academic_records").insert(
                            {
                                "user_id": uid,
                                "exam": acad.get("exam"),
                                "board": acad.get("board"),
                                "year": acad.get("year"),
                                "marks": acad.get("marks"),
                                "total": acad.get("total"),
                                "percentage": acad.get("percentage"),
                                "raw_text": text[:4000],
                            }
                        ).execute()
                    except Exception:
                        pass

            UPLOADS.append(
                {
                    "id": doc_id,
                    "filename": filename,
                    "is_synthetic": False,
                    "extracted": acad,
                }
            )
            return {
                "document_id": doc_id,
                "is_synthetic": False,
                "extracted": acad,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


def _is_uuid(v: str) -> bool:
    return bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-", v or ""))


@router.get("")
def list_documents(user_id: Optional[str] = None):
    if db_available():
        try:
            client = get_client()
            query = client.table("documents").select(
                "id, filename, is_synthetic, extracted, created_at"
            )
            if user_id:
                query = query.eq("user_id", user_id)
            result = query.execute()
            return {"documents": result.data or []}
        except Exception:
            pass
    return {"documents": UPLOADS}


@router.get("/academic")
def list_academic(authorization: Optional[str] = None):
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
