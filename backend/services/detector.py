SUSPICIOUS_TOKENS = ["fake", "sample_generated", "ai_made", "synthetic", "generated"]
SUPPORTED_EXT = ["pdf", "png", "jpg", "jpeg"]


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def detect_synthetic(filename: str, text: str | None = None) -> dict:
    """Heuristic synthetic-content detector. Deterministic and safe."""
    is_synthetic = False
    confidence = 0.0
    reasons: list[str] = []

    if any(tok in filename.lower() for tok in SUSPICIOUS_TOKENS):
        is_synthetic = True
        confidence = max(confidence, 0.7)
        reasons.append("filename contains suspicious token")

    ext = _ext(filename)
    if ext and ext not in SUPPORTED_EXT:
        is_synthetic = True
        confidence = max(confidence, 0.6)
        reasons.append(f"unsupported file type '.{ext}'")

    if text:
        stripped = text.strip()
        if len(stripped) > 0:
            words = stripped.split()
            if len(words) > 20:
                unique_ratio = len(set(words)) / len(words)
                if unique_ratio < 0.2:
                    is_synthetic = True
                    confidence = max(confidence, 0.8)
                    reasons.append("extremely repetitive text (low variance)")
            if len(set(stripped)) <= 3:
                is_synthetic = True
                confidence = max(confidence, 0.9)
                reasons.append("near-zero character variance")

    if not reasons:
        return {
            "is_synthetic": False,
            "confidence": 0.0,
            "reason": "passed basic checks",
        }

    reason = "; ".join(reasons)

    return {
        "is_synthetic": is_synthetic,
        "confidence": round(confidence, 2),
        "reason": reason,
    }
