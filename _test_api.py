import json, urllib.request

B = "https://learnify.hosteler.shop"
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def get(p):
    req = urllib.request.Request(B + p, headers=HDR)
    return json.load(urllib.request.urlopen(req, timeout=30))


def post(p, body):
    req = urllib.request.Request(
        B + p,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **HDR},
        method="POST",
    )
    return json.load(urllib.request.urlopen(req, timeout=30))


try:
    d = get("/api/careers")
    print("careers count:", len(d["careers"]))
    print("categories:", d["categories"])
    print("sample:", d["careers"][0])
except Exception as e:
    print("careers ERR", e)

try:
    d = get("/api/careers/mbbs")
    c = d["career"]
    print("mbbs title:", c["title"], "| keys:", list(c.keys()))
    print("related:", [r["id"] for r in c["related_careers"]])
except Exception as e:
    print("mbbs ERR", e)

try:
    d = post("/api/veda/home-suggestions", {"user_id": "demo"})
    print("home slots:", len(d["slots"]))
    for s in d["slots"]:
        print("  -", s["title"], "->", s["cta_go"], s.get("cta_arg", ""))
except Exception as e:
    print("home-sugg ERR", e)

try:
    d = post(
        "/api/veda/career-guidance",
        {
            "user_id": "demo",
            "answers": {
                "field": "Tech & Coding",
                "priority": "High income",
                "route": "Engineering / Medical (B.Tech, MBBS)",
            },
        },
    )
    g = d["guidance"]
    print(
        "guidance career_id:",
        g["career_id"],
        "| title:",
        g["title"],
        "| match:",
        g.get("match"),
    )
except Exception as e:
    print("guidance ERR", e)
