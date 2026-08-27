import hashlib
import hmac
import json
import os
import uuid
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")


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

    print(f"[learnify] webhook receipt: {json.dumps(payload)[:200]}")
    return {"status": "ok"}
