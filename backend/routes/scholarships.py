"""Smart Scholarship Match — AI-powered eligibility scoring."""

from __future__ import annotations

import re
from fastapi import APIRouter
from pydantic import BaseModel
from backend.database.seed import SEED_SCHOLARSHIPS

router = APIRouter(prefix="/scholarships", tags=["scholarships"])


class MatchReq(BaseModel):
    state: str = ""
    category: str = ""
    income: int = 0
    education: str = ""
    disability: str = "no"
    gender: str = ""


def _score(s: dict, req: MatchReq) -> int:
    """Return 0-100 eligibility score for a scholarship."""
    score = 0
    elig = (s.get("eligibility") or "").lower()
    desc = (s.get("description") or "").lower()
    text = elig + " " + desc
    state = (s.get("state") or "").lower()

    # State match (25 pts)
    if req.state:
        req_state = req.state.lower()
        if state == "central" or state == req_state or req_state in text:
            score += 25
        elif (
            "all india" in text
            or "national" in text
            or "all" in (s.get("colleges") or [])
        ):
            score += 15
    else:
        score += 10  # no state preference = partial

    # Category match (25 pts)
    if req.category:
        cat = req.category.lower()
        if cat in text or (
            cat == "general"
            and "general" not in text
            and "sc " not in text
            and "obc" not in text
            and "st " not in text
        ):
            score += 25
        elif cat == "ews" and ("ews" in text or "economically weaker" in text):
            score += 25
        elif cat == "minority" and (
            "minority" in text
            or "muslim" in text
            or "christian" in text
            or "sikh" in text
        ):
            score += 25
        else:
            # Category-specific scholarships that don't match
            if any(
                x in text
                for x in [
                    "sc ",
                    "sc/",
                    "scheduled caste",
                    "obc",
                    "other backward",
                    "st ",
                    "st/",
                    "scheduled tribe",
                ]
            ):
                score += 0  # wrong category
            else:
                score += 15  # open to all
    else:
        score += 15

    # Income match (25 pts)
    if req.income > 0:
        # Extract income limits from eligibility text
        income_match = re.search(
            r"income.*?below.*?₹?\s*([\d.]+)\s*(lakh|lakhs|l)", elig
        )
        if income_match:
            limit_str = income_match.group(1).replace(",", "")
            limit = float(limit_str) * 100000  # convert lakh to rupees
            if req.income <= limit:
                score += 25
            elif req.income <= limit * 1.2:
                score += 15  # close to limit
            else:
                score += 5
        else:
            # No income limit mentioned = open
            score += 20
    else:
        score += 15

    # Education match (15 pts)
    if req.education:
        edu = req.education.lower()
        if "class 10" in edu and (
            "matric" in text or "class 10" in text or "10th" in text
        ):
            score += 15
        elif "class 12" in edu and (
            "12" in text or "higher secondary" in text or "plus two" in text
        ):
            score += 15
        elif "ug" in edu or "bachelor" in edu:
            if (
                "undergraduate" in text
                or "bachelor" in text
                or "ug " in text
                or "1st yr" in text
                or "professional" in text
            ):
                score += 15
            elif "post matric" in text or "post-matric" in text:
                score += 12
        elif "pg" in edu or "master" in edu:
            if (
                "postgraduate" in text
                or "master" in text
                or "pg " in text
                or "research" in text
            ):
                score += 15
        elif "phd" in edu or "doctoral" in text:
            score += 10
        elif "diploma" in edu:
            if "diploma" in text or "polytechnic" in text:
                score += 15
            elif "professional" in text:
                score += 10
        else:
            score += 10
    else:
        score += 10

    # Disability bonus (10 pts)
    if req.disability == "yes":
        if (
            "disability" in text
            or "pwd" in text
            or "p.d" in text
            or "differently abled" in text
            or "special needs" in text
        ):
            score += 10
        else:
            score += 3  # most are open to PwD

    return min(score, 100)


@router.post("/match")
def match_scholarships(req: MatchReq):
    scored = []
    for s in SEED_SCHOLARSHIPS:
        sc = _score(s, req)
        if sc >= 20:  # only show somewhat-matching
            scored.append(
                {
                    "id": s.get("id"),
                    "name": s.get("name", ""),
                    "amount": s.get("amount", ""),
                    "eligibility": s.get("eligibility", ""),
                    "deadline": s.get("deadline", ""),
                    "category": s.get("category", ""),
                    "state": s.get("state", ""),
                    "link": s.get("link", ""),
                    "provider": s.get("provider", ""),
                    "score": sc,
                }
            )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"matches": scored, "total": len(scored)}
