import hashlib
import hmac
import json
import os
import uuid
import asyncio
import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.database.client import db_available, get_client
from backend.routes.auth import resolve_uid

router = APIRouter()

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

PLAN_DAYS = {"trial": 7, "pro_monthly": 30, "pro_yearly": 365}


def _grant_premium(user_id: str, plan: str = "pro_monthly"):
    if not db_available() or not user_id or user_id == "demo":
        return False
    try:
        client = get_client()
        days = PLAN_DAYS.get(plan, 30)
        until = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).isoformat()
        client.table("users").update({"premium": True, "premium_until": until}).eq(
            "id", user_id
        ).execute()
        return True
    except Exception as e:
        print(f"[learnify] premium grant failed: {e}")
        return False


class CheckoutReq(BaseModel):
    user_id: str = "demo"
    plan: str = "pro_monthly"


@router.post("/checkout")
def checkout(req: CheckoutReq):
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Payments unavailable: Razorpay is not configured. "
            "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env.",
        )

    amount = 500 if req.plan == "trial" else 3700

    import razorpay

    client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    order = client.order.create(
        {
            "amount": amount,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {"user_id": req.user_id, "plan": req.plan},
        }
    )
    return {
        "order_id": order.get("id"),
        "amount": amount,
        "currency": "INR",
        "key": RAZORPAY_KEY_ID,
    }


class ActivateReq(BaseModel):
    plan: str = "pro_monthly"


@router.post("/activate")
def activate(req: ActivateReq, authorization: Optional[str] = None):
    """Grant premium to the logged-in user (called after a successful payment)."""
    uid = resolve_uid(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    ok = _grant_premium(uid, req.plan)
    if not ok:
        raise HTTPException(status_code=500, detail="Could not activate membership")
    return {"ok": True, "premium": True}


@router.get("/status")
def status(authorization: Optional[str] = None):
    uid = resolve_uid(authorization)
    if not uid or not db_available():
        return {"premium": False, "premium_until": ""}
    try:
        client = get_client()
        res = (
            client.table("users")
            .select("premium,premium_until")
            .eq("id", uid)
            .limit(1)
            .execute()
        )
        row = (res.data or [{}])[0]
        premium = bool(row.get("premium"))
        until = row.get("premium_until") or ""
        if premium and until:
            try:
                premium = (
                    datetime.datetime.fromisoformat(str(until)[:19])
                    > datetime.datetime.utcnow()
                )
            except Exception:
                pass
        return {"premium": premium, "premium_until": until}
    except Exception:
        return {"premium": False, "premium_until": ""}


@router.post("/webhook")
def webhook(request: Request):
    body_bytes = b""
    try:
        loop = asyncio.new_event_loop()
        body_bytes = loop.run_until_complete(request.body())
        loop.close()
    except Exception:
        body_bytes = b""

    try:
        payload = json.loads(body_bytes or b"{}")
    except Exception:
        payload = {}

    signature = request.headers.get("X-Razorpay-Signature", "")
    if RAZORPAY_KEY_SECRET and signature:
        try:
            expected = hmac.new(
                RAZORPAY_KEY_SECRET.encode("utf-8"),
                body_bytes,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                print("[learnify] Razorpay signature mismatch")
        except Exception:
            pass

    # Grant premium on a successful payment using the notes we attached at checkout.
    try:
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        notes = entity.get("notes", {}) or {}
        user_id = notes.get("user_id") or payload.get("user_id")
        plan = notes.get("plan") or payload.get("plan") or "pro_monthly"
        event = payload.get("event", "")
        if user_id and (
            "captured" in event or "authorized" in event or event == "payment.captured"
        ):
            _grant_premium(user_id, plan)
    except Exception as e:
        print(f"[learnify] webhook grant error: {e}")

    print(f"[learnify] webhook receipt: {json.dumps(payload)[:200]}")
    return {"status": "ok"}
