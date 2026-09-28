"""Dump the running API into a compact reference the frontend can be built against.

Writes docs/API.md: one entry per operation with its path, auth role, request
body fields and the shape of the success envelope.

    python scripts/dump_api.py [base_url]   # default http://127.0.0.1:8021
"""
import json
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8021").rstrip("/")

with urllib.request.urlopen(BASE + "/openapi.json", timeout=30) as r:
    spec = json.load(r)

schemas = spec.get("components", {}).get("schemas", {})


def resolve(ref: str) -> dict:
    return schemas.get(ref.rsplit("/", 1)[-1], {})


def body_fields(op: dict) -> list[str]:
    rb = op.get("requestBody") or {}
    content = rb.get("content") or {}
    for ct in ("application/json",):
        sch = (content.get(ct) or {}).get("schema") or {}
        if "$ref" in sch:
            sch = resolve(sch["$ref"])
        props = sch.get("properties") or {}
        req = set(sch.get("required") or [])
        out = []
        for name, p in props.items():
            t = p.get("type") or ("array" if "items" in p else "any")
            if t == "array":
                t += f"[{(p.get('items') or {}).get('type', 'obj')}]"
            mark = "" if name in req else "?"
            out.append(f"{name}{mark}:{t}")
        return out
    return []


def path_params(op: dict) -> list[str]:
    return [p.get("name") for p in (op.get("parameters") or [])
            if p.get("in") == "path"]


def query_params(op: dict) -> list[str]:
    return [f"{p.get('name')}{'?' if not p.get('required') else ''}"
            for p in (op.get("parameters") or []) if p.get("in") == "query"]


rows = []
for path, item in sorted(spec.get("paths", {}).items()):
    for method, op in item.items():
        if method not in ("get", "post", "put", "patch", "delete"):
            continue
        tags = op.get("tags") or ["?"]
        rows.append({
            "tag": tags[0],
            "method": method.upper(),
            "path": path,
            "summary": (op.get("summary") or "").strip(),
            "path_params": path_params(op),
            "query": query_params(op),
            "body": body_fields(op),
        })

by_tag: dict[str, list] = {}
for r in rows:
    by_tag.setdefault(r["tag"], []).append(r)

lines = ["# Learnify API", "",
         f"Base: `{BASE}` — success envelope "
         "`{success, data, error}`; auth routes return `{user, session}` directly.",
         f"{len(rows)} operations across {len(by_tag)} tags.", ""]

order = sorted(by_tag)
for tag in order:
    lines.append(f"## {tag}")
    lines.append("")
    for r in sorted(by_tag[tag], key=lambda x: (x["path"], x["method"])):
        head = f"### `{r['method']} {r['path']}`"
        lines.append(head)
        if r["summary"]:
            lines.append(f"- {r['summary']}")
        if r["path_params"]:
            lines.append(f"- path: `{'`, `'.join(r['path_params'])}`")
        if r["query"]:
            lines.append(f"- query: `{'`, `'.join(r['query'])}`")
        if r["body"]:
            lines.append(f"- body: `{'`, `'.join(r['body'])}`")
        lines.append("")

from pathlib import Path

Path("docs").mkdir(exist_ok=True)
out = Path("docs/API.md")
out.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {out} — {len(rows)} operations, {len(by_tag)} tags")
for tag in order:
    print(f"   {tag:18s} {len(by_tag[tag])}")
