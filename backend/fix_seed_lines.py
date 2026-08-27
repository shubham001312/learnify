import re

PATH = "backend/database/seed.py"
text = open(PATH, encoding="utf-8").read()
lines = text.split("\n")
TOUCHED = {
    "nirf_rank",
    "avg_package",
    "website",
    "affiliation",
    "founded",
    "description",
    "pros",
    "cons",
    "amount",
    "provider",
    "link",
}


def first_value(s):
    i, n = 0, len(s)
    while i < n and s[i] in " \t":
        i += 1
    if i >= n:
        return None
    c = s[i]
    if c == '"':
        j = i + 1
        while j < n:
            if s[j] == "\\":
                j += 2
                continue
            if s[j] == '"':
                return s[i : j + 1]
            j += 1
        return None
    if c == "[":
        depth = 0
        for j in range(i, n):
            if s[j] == "[":
                depth += 1
            elif s[j] == "]":
                depth -= 1
                if depth == 0:
                    return s[i : j + 1]
        return None
    if c == "{":
        depth = 0
        for j in range(i, n):
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    return s[i : j + 1]
        return None
    m = re.match(r"(null|true|false|-?\d+\.?\d*)", s[i:])
    return m.group(1) if m else None


out = []
fixed = 0
for line in lines:
    m = re.match(r'^(\s*)"([a-zA-Z_]+)":(.*)$', line)
    if m and m.group(2) in TOUCHED:
        indent, key, rest = m.group(1), m.group(2), m.group(3)
        val = first_value(rest)
        if val is None:
            out.append(line)
        else:
            out.append('%s"%s": %s,' % (indent, key, val))
            fixed += 1
    else:
        out.append(line)

open(PATH, "w", encoding="utf-8").write("\n".join(out))
print("fixed lines:", fixed)
