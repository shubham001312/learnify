"""Static consistency check for the Learnify frontend.

Catches the failures that would otherwise only show up as a blank screen:

  1. every route in app.js resolves to a real module file
  2. every static import resolves to a real file AND every imported name is
     actually exported by its target
  3. every iconSvg('name') reference exists in the icon registry
  4. no module still imports a file we deleted
  5. the served shell is the rebuilt one (when a base URL is given)
  6. every API path the frontend calls appears in docs/API.md

    python scripts/check_frontend.py [base_url]
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public" / "src"

problems: list[str] = []
notes: list[str] = []


def bad(msg: str) -> None:
    problems.append(msg)


def _seg_list(path: str, kind: str) -> list[str]:
    """Split a URL into segments, marking variable ones as tokens.

    `kind='fe'` turns a `${...}` template segment into `*` (may expand to more
    than one segment — `base` can itself be `/v1/courses`); `kind='api'` turns
    a `{param}` path parameter into `?` (exactly one segment). Matching both
    directions is what lets a frontend path assembled from variables still be
    checked against the contract's literal segments.
    """
    segs = [s for s in path.split("/") if s]
    if kind == "fe":
        return ["*" if "${" in s else s for s in segs]
    return ["?" if (s.startswith("{") and s.endswith("}")) else s for s in segs]


def _seg_match(fe: list[str], api: list[str]) -> bool:
    """`*` in `fe` swallows one or more segments; `?` in `api` matches one."""
    n, m = len(fe), len(api)
    seen: set[tuple[int, int]] = set()

    def go(i: int, j: int) -> bool:
        if (i, j) in seen:
            return False
        if i == n:
            return j == m
        if fe[i] == "*":
            if go(i + 1, j):            # zero segments
                return True
            for k in range(j + 1, m + 1):
                if go(i + 1, k):        # one or more segments
                    return True
            return False
        if j >= m:
            return False
        if api[j] != "?" and api[j] != fe[i]:
            seen.add((i, j))
            return False
        return go(i + 1, j + 1)

    return go(0, 0)


# ── 1. routes -> modules ────────────────────────────────────────────────────
app_js = (SRC / "app.js").read_text(encoding="utf-8")

route_files = set(re.findall(r"file:\s*'([^']+)'", app_js))
route_files = {f for f in route_files if not f.startswith("$")}
route_files.discard("")

# `$role` resolves to the signed-in user's dashboard module.
if "'$role'" in app_js:
    route_files.update({"alpha", "master", "supreme"})

if not route_files:
    bad("app.js: no `file: '...'` route entries found")

for f in sorted(route_files):
    if not (SRC / f"{f}.js").exists():
        bad(f"route module missing: public/src/{f}.js")

notes.append(f"{len(route_files)} route modules declared")

# ── 1b. route handlers are exported ─────────────────────────────────────────
# The router does `const m = await import(file); await m[fn](root, ctx)`, so a
# missing export is a silent blank screen rather than an error. Route entries
# put `file:` and `fn:` in declaration order, and every entry carries both.
route_files_decl = re.findall(r"file:\s*'([^']+)'", app_js)
route_fns = re.findall(r"fn:\s*'([^']+)'", app_js)

checked_pairs = set()
if len(route_files_decl) == len(route_fns):
    pairs = list(zip(route_files_decl, route_fns))
else:
    bad(f"app.js: {len(route_files_decl)} file: vs {len(route_fns)} fn: entries "
        "- the route table cannot be checked mechanically")
    pairs = []
pairs += [("alpha", "render"), ("master", "render"), ("supreme", "render")]

for f, fn in pairs:
    if f.startswith("$"):
        continue
    key = (f, fn)
    if key in checked_pairs:
        continue
    checked_pairs.add(key)
    path = SRC / f"{f}.js"
    if not path.exists():
        continue  # reported by the existence check above
    body = path.read_text(encoding="utf-8")
    if not re.search(rf"export\s+(?:async\s+)?function\s+{re.escape(fn)}\b", body):
        bad(f"{f}.js does not export `{fn}()` (route fn for file '{f}')")

notes.append(f"{len(checked_pairs)} route handler exports verified")

# ── 2. static imports ───────────────────────────────────────────────────────
# Two failure modes here, and both are invisible to `node --check` (which only
# parses; it never resolves a module graph):
#   a) importing a file that does not exist, and
#   b) importing a NAME the target module does not export. (b) throws at link
#      time in the browser, which takes the whole route down with a blank page.
import_re = re.compile(r"""(?:import|from)\s+['"]\./([\w-]+\.js)(?:\?[\w=]+)?['"]""")
named_import_re = re.compile(
    r"""import\s+(?:[\w$]+\s*,\s*)?\{([^}]*)\}\s*from\s+['"]\./([\w-]+\.js)"""
    r"""(?:\?[\w=]+)?['"];?""", re.S)


def exports_of(path) -> set[str]:
    """Every name a module makes available to an importer."""
    text = path.read_text(encoding="utf-8")
    names: set[str] = set()
    names.update(re.findall(r"export\s+(?:async\s+)?function\s+([\w$]+)", text))
    names.update(re.findall(r"export\s+(?:const|let|var|class)\s+([\w$]+)", text))
    if re.search(r"export\s+default\b", text):
        names.add("default")
    for group in re.findall(r"export\s*\{([^}]*)\}", text, re.S):
        for part in group.split(","):
            part = part.strip()
            if not part:
                continue
            # `foo as bar` is exported as `bar`; a plain `foo` as itself.
            names.add(part.split(" as ")[-1].strip())
    return names


missing_imports: set[str] = set()
bad_names: list[tuple[str, str, str]] = []
_export_cache: dict[str, set[str]] = {}

for js in sorted(SRC.glob("*.js")):
    text = js.read_text(encoding="utf-8")
    for mod in import_re.findall(text):
        if not (SRC / mod).exists():
            missing_imports.add(f"{js.name} -> {mod}")
    for raw_names, mod in named_import_re.findall(text):
        if not (SRC / mod).exists():
            continue
        if mod not in _export_cache:
            _export_cache[mod] = exports_of(SRC / mod)
        have = _export_cache[mod]
        for part in raw_names.split(","):
            part = part.strip()
            if not part:
                continue
            # In `local as remote`, `remote` is local; the source must have `local`.
            source_name = part.split(" as ")[0].strip()
            if source_name and source_name not in have:
                bad_names.append((js.name, mod, source_name))

for m in sorted(missing_imports):
    bad(f"unresolved import: {m}")
for src_name, mod, name in bad_names:
    bad(f"{src_name} imports `{name}` but {mod} does not export it")

notes.append(f"{len(list(SRC.glob('*.js')))} modules scanned for imports"
             + (f", {len(bad_names)} bad names" if bad_names else ", all names resolve"))

# ── 3. icons ────────────────────────────────────────────────────────────────
icons_js = (SRC / "icons.js").read_text(encoding="utf-8")
registry = set(re.findall(r"^\s{2}(\w+):\s*'<", icons_js, re.M))

if not registry:
    bad("icons.js: ICON_PATHS registry not found")

used: dict[str, set[str]] = {}
call_re = re.compile(r"""iconSvg\(\s*['"](\w+)['"]""")
member_re = re.compile(r"""icon:\s*'(\w+)'""")

for js in sorted(SRC.glob("*.js")):
    if js.name == "icons.js":
        continue
    text = js.read_text(encoding="utf-8")
    for name in call_re.findall(text):
        used.setdefault(name, set()).add(js.name)
    for name in member_re.findall(text):
        used.setdefault(name, set()).add(js.name)

missing_icons = sorted(n for n in used if n not in registry)
for n in missing_icons:
    bad(f"icon '{n}' used in {', '.join(sorted(used[n]))} but not defined")

notes.append(f"{len(registry)} icons defined, {len(used)} referenced")

# ── 4. dead references ──────────────────────────────────────────────────────
DELETED = ["veda.js", "career.js", "careers.js", "tools.js", "premium.js", "sih.js"]
for js in sorted(SRC.glob("*.js")):
    text = js.read_text(encoding="utf-8")
    for dead in DELETED:
        if dead in text:
            bad(f"{js.name} still references deleted module {dead}")

index_html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
for dead in DELETED:
    if dead in index_html:
        bad(f"index.html still references deleted module {dead}")

# Legacy sections that must not survive in the shell.
for legacy in ("tab-veda", "page-college", "page-career", "tab-opportunities",
               "career-quiz-modal"):
    if legacy in index_html:
        bad(f"index.html still contains legacy markup: {legacy}")

if "Check &amp; Mate" not in index_html:
    bad("index.html: tagline 'Check &amp; Mate' missing")

# ── 5. served shell ─────────────────────────────────────────────────────────
base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else None
if base:
    try:
        with urllib.request.urlopen(base + "/", timeout=15) as r:
            body = r.read().decode("utf-8", "replace")
        if "id=\"view\"" not in body and "id='view'" not in body:
            bad("served / has no #view mount point")
        if "src/app.js" not in body:
            bad("served / does not load src/app.js")
        if "Check &amp; Mate" not in body:
            bad("served / is not the rebuilt shell")
        else:
            notes.append(f"served shell OK at {base}/")
    except Exception as e:  # noqa: BLE001
        bad(f"could not fetch {base}/: {e}")

    for f in sorted(route_files):
        try:
            req = urllib.request.Request(f"{base}/src/{f}.js", method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status != 200:
                    bad(f"{base}/src/{f}.js -> HTTP {r.status}")
        except Exception as e:  # noqa: BLE001
            bad(f"{base}/src/{f}.js not served: {e}")

# ── 2b. namespace members actually exist ────────────────────────────────────
# Modules import the toolkit as `import * as ui`. A typo like `ui.blanks()`
# parses fine and resolves fine, then throws a TypeError on first paint —
# which is exactly the blank screen this script exists to prevent.
ns_import_re = re.compile(r"import\s+\*\s+as\s+([\w$]+)\s+from\s+['\"]\./([\w-]+)\.js")
ns_bad: list[tuple[str, str, str]] = []
ns_counts: dict[str, int] = {}

for js in sorted(SRC.glob("*.js")):
    text = js.read_text(encoding="utf-8")
    # Drop module specifiers first: `from './ui.js'` would otherwise read as
    # a call to a member named `js`.
    scan = re.sub(r"['\"]\./[\w-]+\.js(?:\?[\w=]+)?['\"]", "''", text)
    for alias, mod in ns_import_re.findall(text):
        target = SRC / f"{mod}.js"
        if not target.exists():
            continue
        have = exports_of(target)
        for m in re.finditer(rf"\b{re.escape(alias)}\.([\w$]+)", scan):
            member = m.group(1)
            ns_counts[f"{alias}:{mod}"] = ns_counts.get(f"{alias}:{mod}", 0) + 1
            if member not in have:
                ns_bad.append((js.name, alias, member))

for src_name, alias, member in ns_bad:
    bad(f"{src_name} calls `{alias}.{member}()` but that member is not exported")

if ns_counts:
    notes.append("namespaces checked: "
                 + ", ".join(f"{k.replace(':', ' -> ')} x{v}"
                             for k, v in sorted(ns_counts.items()))
                 + (f" ({len(ns_bad)} bad)" if ns_bad else " (all members exist)"))

# ── 6. every API path the frontend calls exists in the backend ──────────────
# `api()` prefixes each path with `/api`, so a call written as
# `api('/api/auth/me')` silently resolves to `/api/api/auth/me` and 404s at
# runtime. Without a connected browser this is otherwise only found by clicking
# the page, so check every literal path against the generated contract.
API_MD = ROOT / "docs" / "API.md"
if API_MD.exists():
    contract_paths = re.findall(
        r"^###\s+`[A-Z]+\s+([^`\s]+)`",
        API_MD.read_text(encoding="utf-8"), re.M)
    contract_segs = [_seg_list(p.split("?")[0], "api") for p in contract_paths]

    call_re = re.compile(r"""\b(?:api|apiForm)\(\s*(['"`])([^'"`\n]+)\1""")
    called: dict[str, set[str]] = {}
    for js in sorted(SRC.glob("*.js")):
        for _q, raw in call_re.findall(js.read_text(encoding="utf-8")):
            p = raw.split("?")[0].rstrip("/") or "/"
            if not p.startswith("/api"):
                p = "/api" + p
            called.setdefault(p, set()).add(js.name)

    unknown = []
    for p in sorted(called):
        fe = _seg_list(p, "fe")
        if not any(_seg_match(fe, cs) for cs in contract_segs):
            unknown.append((p, sorted(called[p])))
    for p, where in unknown:
        bad(f"API path not in docs/API.md: {p}  (called from {', '.join(where)})")

    dynamic = {w for p, ws in called.items() for w in ws if "${" in p}
    notes.append(f"{len(called)} API paths checked against "
                 f"{len(contract_paths)} contract operations"
                 + (f", {len(unknown)} unknown" if unknown else ", all known")
                 + (f" ({len(dynamic)} built from variables, matched loosely)"
                    if dynamic else ""))
else:
    notes.append("docs/API.md not found — API path check skipped")

# ── report ──────────────────────────────────────────────────────────────────
for n in notes:
    print(f"  . {n}")

if problems:
    print(f"\nFRONTEND CHECK FAILED — {len(problems)} problem(s):")
    for p in problems:
        print(f"  X {p}")
    sys.exit(1)

print("\nFRONTEND CHECK PASSED")
