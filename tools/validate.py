#!/usr/bin/env python3
"""Mechanical health check of the wiki. Prints a report; exits 1 on hard errors.

Usage (from the vault root):  python3 tools/validate.py [--quiet]

Hard errors (fix before committing): page without frontmatter or type, unquoted
[[[link]] lists in YAML, stray tool markup, invalid relations.jsonl lines.
Warnings (report in lint): broken links, likely duplicate people, people missing
company/last_contact, index.md over the size cap.
"""
import json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI = os.path.join(ROOT, "wiki")
SPECIAL = {"Home", "index", "index-archive", "log"}
RELS = {"founded_by", "key_person", "advisor", "board_member", "works_at", "invested_in_by", "customer",
        "supplier", "partners_with", "competes_with", "comparable_to", "licenses_to", "sister_company",
        "subsidiary_of", "acquired_by", "spun_out_of", "introduced"}
STATUSES, CONFIDENCE = {"confirmed", "potential", "former", "rejected"}, {"high", "low"}
INDEX_CAP = 300
STRAY = re.compile(r"^</?(content|invoke|parameter|antml:[a-z_]+)>\s*$", re.M)


def norm(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def md_files():
    for d, _, fs in os.walk(WIKI):
        for f in fs:
            if f.endswith(".md"):
                yield os.path.join(d, f)


def run():
    errors, warnings = [], []
    names, aliases, people = {}, {}, []
    texts = {}
    for p in md_files():
        name, rel = os.path.basename(p)[:-3], os.path.relpath(p, ROOT)
        s = open(p, encoding="utf-8", errors="ignore").read()
        texts[p] = s
        names[name.lower()] = p
        if s.startswith("---\n") and s.find("\n---", 4) > 0:
            fm = s[4:s.find("\n---", 4)]
            m = re.search(r"^aliases:\s*\[(.*?)\]", fm, re.M)
            for a in (m.group(1).split(",") if m else []):
                if a.strip().strip("\"'"):
                    aliases[a.strip().strip("\"'").lower()] = p
            if name not in SPECIAL and not re.search(r"^type:\s*\S", fm, re.M):
                errors.append(f"{rel}: frontmatter has no `type`")
            if re.search(r"\[\[\[", fm):
                errors.append(f"{rel}: unquoted [[[link]] list in frontmatter; write [\"[[A]]\", \"[[B]]\"]")
            if "/people/" in p and "/network/" not in p:
                people.append(name)
                for k in ("company", "last_contact"):
                    if not re.search(rf"^{k}:\s*\S", fm, re.M):
                        warnings.append(f"{rel}: person page missing `{k}`")
        elif name not in SPECIAL:
            errors.append(f"{rel}: no YAML frontmatter")
        if STRAY.search(s):
            errors.append(f"{rel}: stray tool markup line (e.g. </content>)")

    broken = {}
    for p, s in texts.items():
        for t in re.findall(r"(?<!!)\[\[([^\]|#]+)", s):
            t = t.strip().split("/")[-1]
            if t.lower() not in names and t.lower() not in aliases:
                broken.setdefault(t, set()).add(os.path.basename(p)[:-3])
    for t, src in sorted(broken.items(), key=lambda x: -len(x[1]))[:25]:
        warnings.append(f"broken link [[{t}]] from {len(src)} page(s), e.g. {sorted(src)[0]}")

    seen = {}
    for n in people:
        seen.setdefault(norm(n), []).append(n)
    for group in seen.values():
        if len(group) > 1:
            warnings.append(f"likely duplicate people: {group}")

    idx = os.path.join(WIKI, "index.md")
    if os.path.exists(idx) and len(open(idx).read().splitlines()) > INDEX_CAP:
        warnings.append(f"index.md is over {INDEX_CAP} lines; move the long tail to index-archive.md")

    rel_file = os.path.join(WIKI, "_graph", "relations.jsonl")
    if os.path.exists(rel_file):
        for n, line in enumerate(open(rel_file, encoding="utf-8"), 1):
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except ValueError:
                errors.append(f"relations.jsonl:{n}: invalid JSON"); continue
            bad = [k for k in ("source", "rel", "target", "status", "confidence", "evidence", "page") if not e.get(k)]
            if bad:
                errors.append(f"relations.jsonl:{n}: missing {bad}"); continue
            if e["rel"] not in RELS or e["status"] not in STATUSES or e["confidence"] not in CONFIDENCE:
                errors.append(f"relations.jsonl:{n}: rel/status/confidence not in schema")
            page = names.get(e["page"].lower())
            if page and e["evidence"] not in texts[page]:
                warnings.append(f"relations.jsonl:{n}: evidence not found verbatim in [[{e['page']}]] (page edited since?)")

    if "--quiet" not in sys.argv or errors:
        print(f"{len(texts)} pages checked: {len(errors)} errors, {len(warnings)} warnings")
        for x in errors:
            print("ERROR  ", x)
        for x in warnings:
            print("warning", x)
    return errors, warnings


if __name__ == "__main__":
    errs, _ = run()
    sys.exit(1 if errs else 0)
