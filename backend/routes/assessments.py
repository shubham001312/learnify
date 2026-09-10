"""
Assessment engine routes.

GET    /api/v1/assessments                     — list available assessments
GET    /api/v1/assessments/{assessment_id}     — get assessment details (questions)
POST   /api/v1/assessments/{assessment_id}/start   — start an attempt
POST   /api/v1/assessments/{assessment_id}/submit   — submit answers, get results
GET    /api/v1/assessments/attempts/me         — list own attempts
GET    /api/v1/assessments/attempts/{attempt_id} — get attempt details
"""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.database.client import db_available, get_client
from backend.routes.auth import _current_app_user
from backend.services.cache import invalidate_pattern

router = APIRouter()


class SubmitAnswer(BaseModel):
    question_id: str
    selected_option_id: Optional[str] = None
    answer_text: Optional[str] = None


class SubmitAttemptReq(BaseModel):
    attempt_id: str
    answers: list[SubmitAnswer]


def _require_user(authorization: Optional[str]):
    cu = _current_app_user(authorization)
    if not cu:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return cu


# ───────────────────────── LIST ASSESSMENTS ─────────────────────────


@router.get("/assessments")
def list_assessments(authorization: Optional[str] = Header(None)):
    """List all active assessments."""
    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    try:
        res = (
            client.table("assessments")
            .select(
                "id, title, description, category, duration_minutes, max_score, passing_score"
            )
            .eq("is_active", True)
            .order("title")
            .execute()
        )
        return {"assessments": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load assessments: {e}")


# ───────────────────────── GET ASSESSMENT ─────────────────────────


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, authorization: Optional[str] = Header(None)):
    """Get assessment details with questions and options."""
    _require_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    try:
        # Get assessment
        a_res = (
            client.table("assessments")
            .select("*")
            .eq("id", assessment_id)
            .limit(1)
            .execute()
        )
        if not a_res.data:
            raise HTTPException(status_code=404, detail="Assessment not found")
        assessment = a_res.data[0]

        # Get questions
        q_res = (
            client.table("assessment_questions")
            .select("id, question_text, question_type, difficulty, weight")
            .eq("assessment_id", assessment_id)
            .order("created_at")
            .execute()
        )
        questions = q_res.data or []

        # Get options for each question
        for q in questions:
            o_res = (
                client.table("assessment_options")
                .select("id, option_text, sort_order")
                .eq("question_id", q["id"])
                .order("sort_order")
                .execute()
            )
            q["options"] = o_res.data or []

        assessment["questions"] = questions
        return {"assessment": assessment}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load assessment: {e}")


# ───────────────────────── START ATTEMPT ─────────────────────────


@router.post("/assessments/{assessment_id}/start")
def start_attempt(assessment_id: str, authorization: Optional[str] = Header(None)):
    """Start a new assessment attempt."""
    cu = _require_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()

    # Check cooldown
    try:
        last_attempt = (
            client.table("assessment_attempts")
            .select("completed_at")
            .eq("user_id", cu["uid"])
            .eq("assessment_id", assessment_id)
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .limit(1)
            .execute()
        )
        if last_attempt.data and last_attempt.data[0].get("completed_at"):
            from datetime import datetime, timedelta

            completed = datetime.fromisoformat(
                last_attempt.data[0]["completed_at"].replace("Z", "+00:00")
            )
            assessment = (
                client.table("assessments")
                .select("cooldown_hours")
                .eq("id", assessment_id)
                .limit(1)
                .execute()
            )
            cooldown = (assessment.data or [{}])[0].get("cooldown_hours", 24)
            if datetime.utcnow() < completed + timedelta(hours=cooldown):
                raise HTTPException(
                    status_code=429,
                    detail=f"Cooldown active. Try again after {cooldown} hours from your last attempt.",
                )
    except HTTPException:
        raise
    except Exception:
        pass

    # Get max score
    try:
        a_res = (
            client.table("assessments")
            .select("max_score, duration_minutes")
            .eq("id", assessment_id)
            .limit(1)
            .execute()
        )
        if not a_res.data:
            raise HTTPException(status_code=404, detail="Assessment not found")
        max_score = a_res.data[0].get("max_score", 100)
    except HTTPException:
        raise
    except Exception:
        max_score = 100

    # Create attempt
    try:
        res = (
            client.table("assessment_attempts")
            .insert(
                {
                    "user_id": cu["uid"],
                    "assessment_id": assessment_id,
                    "max_score": max_score,
                    "status": "in_progress",
                }
            )
            .execute()
        )
        return {"attempt": res.data[0], "message": "Attempt started"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to start attempt: {e}")


# ───────────────────────── SUBMIT ATTEMPT ─────────────────────────


@router.post("/assessments/{assessment_id}/submit")
def submit_attempt(
    assessment_id: str,
    req: SubmitAttemptReq,
    authorization: Optional[str] = Header(None),
):
    """Submit answers for an assessment attempt and get results."""
    cu = _require_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()

    # Verify attempt belongs to user and is in_progress
    try:
        a_res = (
            client.table("assessment_attempts")
            .select("*")
            .eq("id", req.attempt_id)
            .eq("user_id", cu["uid"])
            .limit(1)
            .execute()
        )
        if not a_res.data:
            raise HTTPException(status_code=404, detail="Attempt not found")
        attempt = a_res.data[0]
        if attempt["status"] != "in_progress":
            raise HTTPException(status_code=400, detail="Attempt already completed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Attempt lookup failed: {e}")

    # Score each answer
    total_score = 0
    max_score = attempt.get("max_score", 100)
    skill_scores = {}  # skill_name -> {"correct": n, "total": n}

    for answer in req.answers:
        try:
            # Get question details
            q_res = (
                client.table("assessment_questions")
                .select("id, weight, explanation")
                .eq("id", answer.question_id)
                .limit(1)
                .execute()
            )
            if not q_res.data:
                continue
            question = q_res.data[0]

            # Check correctness
            is_correct = False
            if answer.selected_option_id:
                o_res = (
                    client.table("assessment_options")
                    .select("is_correct")
                    .eq("id", answer.selected_option_id)
                    .limit(1)
                    .execute()
                )
                is_correct = bool(o_res.data and o_res.data[0].get("is_correct"))

            # Calculate score for this question
            q_score = question.get("weight", 1.0) * (100 if is_correct else 0)
            total_score += q_score

            # Track skill scores
            qs_res = (
                client.table("question_skills")
                .select("skill_id, weight, skills(name)")
                .eq("question_id", answer.question_id)
                .execute()
            )
            for qs in qs_res.data or []:
                skill_name = (qs.get("skills") or {}).get("name", "Unknown")
                if skill_name not in skill_scores:
                    skill_scores[skill_name] = {"correct": 0, "total": 0}
                skill_scores[skill_name]["total"] += 1
                if is_correct:
                    skill_scores[skill_name]["correct"] += 1

            # Save response
            client.table("assessment_responses").insert(
                {
                    "attempt_id": req.attempt_id,
                    "question_id": answer.question_id,
                    "selected_option_id": answer.selected_option_id,
                    "is_correct": is_correct,
                    "score": q_score,
                }
            ).execute()

        except Exception:
            continue

    # Calculate percentage and update attempt
    percentage = (total_score / max_score * 100) if max_score > 0 else 0
    passing_score = (
        attempt.get("passing_score", 60) if "passing_score" in attempt else 60
    )

    try:
        # Get passing score from assessment
        a_info = (
            client.table("assessments")
            .select("passing_score")
            .eq("id", assessment_id)
            .limit(1)
            .execute()
        )
        passing_score = (a_info.data or [{}])[0].get("passing_score", 60)
    except Exception:
        pass

    passed = percentage >= passing_score

    try:
        client.table("assessment_attempts").update(
            {
                "score": total_score,
                "percentage": round(percentage, 1),
                "status": "completed",
                "completed_at": "now()",
            }
        ).eq("id", req.attempt_id).execute()
    except Exception:
        pass

    # Update user skill levels based on assessment results
    for skill_name, scores in skill_scores.items():
        skill_level = (
            (scores["correct"] / scores["total"] * 100) if scores["total"] > 0 else 0
        )
        # Find skill_id
        try:
            s_res = (
                client.table("skills")
                .select("id")
                .eq("name", skill_name)
                .limit(1)
                .execute()
            )
            if s_res.data:
                skill_id = s_res.data[0]["id"]
                # Update or insert user skill
                existing = (
                    client.table("user_skills")
                    .select("id, level")
                    .eq("user_id", cu["uid"])
                    .eq("skill_id", skill_id)
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    old_level = existing.data[0].get("level", 0)
                    new_level = max(old_level, skill_level)
                    client.table("user_skills").update(
                        {
                            "level": new_level,
                            "source": "ASSESSMENT",
                            "last_assessed_at": "now()",
                        }
                    ).eq("id", existing.data[0]["id"]).execute()
                else:
                    client.table("user_skills").insert(
                        {
                            "user_id": cu["uid"],
                            "skill_id": skill_id,
                            "level": skill_level,
                            "source": "ASSESSMENT",
                            "last_assessed_at": "now()",
                        }
                    ).execute()
        except Exception:
            continue

    # Invalidate caches
    invalidate_pattern(f"learnify:user:{cu['uid']}")

    return {
        "attempt_id": req.attempt_id,
        "score": total_score,
        "max_score": max_score,
        "percentage": round(percentage, 1),
        "passed": passed,
        "passing_score": passing_score,
        "skill_breakdown": {
            name: {
                "correct": s["correct"],
                "total": s["total"],
                "level": round(s["correct"] / s["total"] * 100)
                if s["total"] > 0
                else 0,
            }
            for name, s in skill_scores.items()
        },
    }


# ───────────────────────── MY ATTEMPTS ─────────────────────────


@router.get("/assessments/attempts/me")
def my_attempts(authorization: Optional[str] = Header(None)):
    """List the authenticated user's assessment attempts."""
    cu = _require_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    try:
        res = (
            client.table("assessment_attempts")
            .select(
                "id, assessment_id, score, max_score, percentage, status, started_at, completed_at, assessments(title, category)"
            )
            .eq("user_id", cu["uid"])
            .order("started_at", desc=True)
            .execute()
        )
        return {"attempts": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load attempts: {e}")


@router.get("/assessments/attempts/{attempt_id}")
def get_attempt(attempt_id: str, authorization: Optional[str] = Header(None)):
    """Get details of a specific attempt with responses."""
    cu = _require_user(authorization)

    if not db_available():
        raise HTTPException(status_code=503, detail="Database unavailable")

    client = get_client()
    try:
        a_res = (
            client.table("assessment_attempts")
            .select("*, assessments(title, category, max_score, passing_score)")
            .eq("id", attempt_id)
            .eq("user_id", cu["uid"])
            .limit(1)
            .execute()
        )
        if not a_res.data:
            raise HTTPException(status_code=404, detail="Attempt not found")

        attempt = a_res.data[0]

        # Get responses
        r_res = (
            client.table("assessment_responses")
            .select(
                "*, question:assessment_questions(id, question_text, explanation), selected_option:assessment_options(option_text)"
            )
            .eq("attempt_id", attempt_id)
            .execute()
        )
        attempt["responses"] = r_res.data or []

        return {"attempt": attempt}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load attempt: {e}")
