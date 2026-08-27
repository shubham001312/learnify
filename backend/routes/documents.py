import os
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

router = APIRouter()

UPLOADS: list[dict] = []


def _read_text(filename: str, contents: bytes) -> str:
    try:
        return contents.decode("utf-8", errors="ignore")
    except Exception:
        return filename


def _extract_fields(text: str) -> dict:
    fields: dict = {}
    if not text:
        return fields
    sgpa = re.search(r"SGPA\s*[:=]?\s*([0-9]{1,2}(\.\d{1,2})?)", text, re.I)
    if sgpa:
        fields["sgpa"] = sgpa.group(1)
    cgpa = re.search(r"CGPA\s*[:=]?\s*([0-9]{1,2}(\.\d{1,2})?)", text, re.I)
    if cgpa:
        fields["cgpa"] = cgpa.group(1)
    stream = re.search(r"Stream\s*[:=]?\s*([A-Za-z ]+)", text, re.I)
    if stream:
        fields["stream"] = stream.group(1).strip()
    marks = re.search(r"Marks\s*[:=]?\s*([0-9]{1,3})", text, re.I)
    if marks:
        fields["marks"] = marks.group(1)
    return fields


if _MULTIPART_OK:

    @router.post("/upload")
    def upload(
        file: UploadFile = File(...),
        user_id: str = Form("demo"),
    ):
        try:
            filename = file.filename or "document.bin"
            contents = file.file.read()
            text = _read_text(filename, contents)

            detection = detect_synthetic(filename, text)
            is_synthetic = detection.get("is_synthetic", False)

            if is_synthetic:
                return {
                    "document_id": None,
                    "is_synthetic": True,
                    "extracted": {},
                    "message": "Please re-upload a genuine document.",
                }

            rag_ingest(text or filename, user_id, "document")
            extracted = _extract_fields(text)

            UPLOADS.append(
                {
                    "id": f"doc-{uuid.uuid4().hex[:12]}",
                    "filename": filename,
                    "is_synthetic": False,
                    "extracted": extracted,
                }
            )

            return {
                "document_id": UPLOADS[-1]["id"],
                "is_synthetic": False,
                "extracted": extracted,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


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
