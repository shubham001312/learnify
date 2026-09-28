"""Smoke-test the Groq integration used for question drafting and Veda reports."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from backend.services import ai  # noqa: E402

print("configured:", ai.available())

# 1. raw chat
try:
    txt = ai.chat([{"role": "user", "content": 'Reply with exactly: {"ok": true}'}],
                  max_tokens=50, json_mode=True)
    print("chat raw:", txt[:80].replace("\n", " "))
    print("extract_json:", ai.extract_json(txt))
except Exception as e:
    print("chat FAILED:", type(e).__name__, str(e)[:300])

# 2. question generation
try:
    qs = ai.generate_questions(
        subject="Computer Networks",
        topics=["OSI Model", "TCP/IP", "Routing"],
        count=3, difficulty="medium", kind="ASSESSMENT",
    )
    print(f"\ngenerated {len(qs)} questions")
    for q in qs:
        print(f"  [{q['difficulty']}/{q['topic']}] {q['text'][:90]}")
        print(f"      correct({q['correct_index']}): {q['options'][q['correct_index']][:70]}")
except Exception as e:
    print("generate FAILED:", type(e).__name__, str(e)[:400])

# 3. report personalisation
try:
    ins = ai.personalise_report(
        trainee_name="Asha", subject="Computer Networks", percentage=58.0,
        passed=False,
        weak_topics=[{"topic": "Routing", "pct": 40.0},
                     {"topic": "OSI Model", "pct": 55.0}],
        strong_topics=[{"topic": "TCP/IP", "pct": 90.0}],
        difficulty={"easy": {"pct": 80.0}, "hard": {"pct": 35.0}},
        benchmarks=[{"topic": "Routing", "standard": "Should grasp OSPF/BGP basics"}],
        attempt_kind="ASSESSMENT",
    )
    print("\nreport keys:", list(ins.keys()))
    for k, v in ins.items():
        print(f"  {k}: {str(v)[:110]}")
except Exception as e:
    print("report FAILED:", type(e).__name__, str(e)[:400])
