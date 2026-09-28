"""Exercise the auth rate limiter against a live server.

    python scripts/test_ratelimit.py [base_url]

Each section uses its own throwaway source address, so the script can run
after e2e_test.py without inheriting the loopback bucket e2e just spent.
The limiter is in-process, so a restart also resets every window.
"""
import json
import random
import sys
import time

import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8021").rstrip("/")
LOGIN_LIMIT = 15          # RATE_LIMIT_LOGIN default; see middleware/ratelimit.py
WINDOW = 60               # seconds
FAIL = []


def fresh_ip():
    """An address nothing else in this run (or the last e2e) has spent."""
    return f"203.0.{random.randint(0, 255)}.{random.randint(1, 254)}"


def check(label, ok, extra=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' :: ' + extra) if extra else ''}")
    if not ok:
        FAIL.append(label)


def login(email, ip, password="definitely-wrong"):
    return requests.post(BASE + "/api/auth/login",
                         json={"email": email, "password": password},
                         headers={"X-Forwarded-For": ip}, timeout=10)


def wait_health(timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if requests.get(BASE + "/health", timeout=3).ok:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


assert wait_health(), "server never came up on " + BASE

print("=== 1. unmetered traffic is untouched ===")
r = requests.get(BASE + "/health", timeout=10)
check("GET /health -> 200", r.status_code == 200, str(r.status_code))
r = requests.get(BASE + "/api/v1/subjects", timeout=10)
check("GET /api/v1/subjects passes through unmetered",
      r.status_code in (200, 401), f"{r.status_code} (401 = auth-gated, not 429)")
r = requests.get(BASE + "/api/auth/me", timeout=10)
check("GET /api/auth/me (no token) -> 401 not 429",
      r.status_code == 401, str(r.status_code))

print("=== 2. login budget is enforced on a fresh address ===")
ip_budget = fresh_ip()
statuses = []
for i in range(LOGIN_LIMIT + 10):
    statuses.append(login(f"rate.probe.{i}@example.com", ip_budget).status_code)

first_429 = statuses.index(429) if 429 in statuses else -1
allowed = [s for s in statuses if s != 429]
blocked = [s for s in statuses if s == 429]
print(f"    statuses seen: {sorted(set(statuses))}  allowed={len(allowed)} 429={len(blocked)}")
check("pre-limit responses are real auth failures (401)",
      all(s == 401 for s in statuses[:LOGIN_LIMIT]), str(statuses[:LOGIN_LIMIT]))
check("first 429 at exactly the configured limit",
      first_429 == LOGIN_LIMIT, f"index {first_429}, expected {LOGIN_LIMIT}")
check("everything past the cap is 429",
      all(s == 429 for s in statuses[LOGIN_LIMIT:]), str(statuses[LOGIN_LIMIT:]))
check("no request slipped past the cap", len(blocked) == 10, f"{len(blocked)}/10")

print("=== 3. 429 contract ===")
r = login("rate.probe@example.com", ip_budget)
if r.status_code == 429:
    body = r.json()
    check("status 429", True)
    check("envelope success:false", body.get("success") is False, str(body.get("success")))
    check("data null", body.get("data") is None)
    check("error present", bool(body.get("error")), str(body.get("error"))[:80])
    check("detail mirrors error", body.get("detail") == body.get("error"))
    check("Retry-After header is seconds",
          (r.headers.get("Retry-After") or "").isdigit(),
          str(r.headers.get("Retry-After")))
else:
    check("status 429", False, str(r.status_code))

print("=== 4. a client-controlled X-Forwarded-For prefix cannot rotate past it ===")
# Through a proxy the real address is appended last; rotating only the
# client-written part in front of it must leave the key unchanged.
ip_rot = fresh_ip()
rotated = 0
for i in range(LOGIN_LIMIT + 10):
    r = requests.post(BASE + "/api/auth/login",
                      json={"email": "rot@example.com", "password": "x"},
                      headers={"X-Forwarded-For": f"203.255.{i % 250}.9, {ip_rot}"},
                      timeout=10)
    if r.status_code == 429:
        rotated += 1
check("rotating the spoofed prefix still hits the cap", rotated == 10,
      f"{rotated}/25 blocked")

print("=== 5. distinct addresses get their own budget ===")
got = 0
for _ in range(5):
    r = login("fresh@example.com", fresh_ip())
    if r.status_code != 429:
        got += 1
check("a new address is not inheriting someone else's cap", got == 5, f"{got}/5 allowed")

print("=== 6. other endpoints never metered ===")
for path in ("/api/v1/notifications/my", "/api/v1/feed", "/api/v1/library"):
    r = requests.get(BASE + path, timeout=10)
    check(f"GET {path} -> not 429", r.status_code != 429, str(r.status_code))

print("=== 7. validation errors use our envelope, not FastAPI's default ===")
r = requests.post(BASE + "/api/auth/login",
                  json={"email": "not-an-email", "password": "x"},
                  headers={"X-Forwarded-For": fresh_ip()}, timeout=10)
if r.status_code == 422:
    b = r.json()
    check("422 body is our envelope",
          b.get("success") is False and isinstance(b.get("error"), str),
          json.dumps(b)[:200])
    check("error names the offending field", "email" in (b.get("error") or ""),
          str(b.get("error"))[:120])
    check("detail mirrors error", b.get("detail") == b.get("error"))
    check("not a list (would render as [object Object])",
          not isinstance(b.get("detail"), list))
else:
    check("malformed email -> 422", False, str(r.status_code))

print("=== 8. Groq-spending endpoints are metered per bearer token ===")
# A fake token is rejected by auth long before Groq is reached, so this
# measures the meter itself: the key is the token, not the address.
AI_LIMIT = 10
ai_st = []
for i in range(AI_LIMIT + 5):
    r = requests.post(BASE + "/api/v1/ai/generate-questions", json={},
                      headers={"Authorization": "Bearer " + "z" * 40,
                               "Content-Type": "application/json"}, timeout=10)
    ai_st.append(r.status_code)
first_ai = ai_st.index(429) if 429 in ai_st else -1
print(f"    statuses seen: {sorted(set(ai_st))}")
check("AI generation is metered at all", first_ai >= 0, str(ai_st))
check("meter opens at the configured limit",
      first_ai == AI_LIMIT, f"index {first_ai}, expected {AI_LIMIT}")
check("pre-limit responses are not 429",
      all(s != 429 for s in ai_st[:AI_LIMIT]), str(ai_st[:AI_LIMIT]))
check("everything past the cap is 429",
      all(s == 429 for s in ai_st[AI_LIMIT:]), str(ai_st[AI_LIMIT:]))

r = requests.post(BASE + "/api/v1/ai/generate-questions", json={},
                  headers={"Authorization": "Bearer " + "y" * 40,
                           "Content-Type": "application/json"}, timeout=10)
check("a different account starts with a fresh budget", r.status_code != 429,
      str(r.status_code))

r = requests.post(BASE + "/api/v1/ai/personalise-report", json={},
                  headers={"Authorization": "Bearer " + "z" * 40,
                           "Content-Type": "application/json"}, timeout=10)
check("report personalisation shares that account's AI budget",
      r.status_code == 429, str(r.status_code))

print()
if FAIL:
    print(f"RESULT: {len(FAIL)} FAILED -> {FAIL}")
    sys.exit(1)
print("RESULT: ALL RATE LIMIT CHECKS PASSED")
