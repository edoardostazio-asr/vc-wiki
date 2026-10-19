#!/usr/bin/env python3
"""Import a LinkedIn Connections.csv export into the wiki.

Usage (from the vault root):
  python3 tools/import_linkedin.py [path/to/Connections.csv] [--all]   import the LinkedIn export
  python3 tools/import_linkedin.py --harmonic-upload [--all]            write raw/linkedin/harmonic-upload.csv
                                                                       (founders + investors; --all = everyone)
  python3 tools/import_linkedin.py --harmonic path/to/enriched.csv      merge a Harmonic export into person pages

- Existing person pages (wiki/people/**): adds linkedin, linkedin_connection, connected_since.
- Founders and investors without a page: creates a light profile in wiki/people/network/
  (--all does this for every connection).
- Company and investor pages: rewrites a "People you know (LinkedIn)" section listing
  your connections who work there.
Safe to re-run on a newer export. Never deletes pages.
"""
import csv, datetime, glob, io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI = os.path.join(ROOT, "wiki")
SECTION = "## People you know (LinkedIn)"
BACKGROUND = "## Background (Harmonic)"
FOUNDER = re.compile(r"founder|\bceo\b|co-founder|cofounder", re.I)
INVESTOR = re.compile(r"\b(partner|principal|investor|investment|associate|analyst|venture|vc)\b", re.I)
INVESTOR_CO = re.compile(r"capital|ventures?|partners|fund|invest", re.I)


def load(path):
    lines = open(path, encoding="utf-8-sig").read().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("First Name"))  # skip LinkedIn's notes header
    return list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))


def iso(d):
    try:
        return datetime.datetime.strptime(d.strip(), "%d %b %Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def role(c):
    if FOUNDER.search(c["Position"]):
        return "founder"
    if INVESTOR_CO.search(c["Company"]) or INVESTOR.search(c["Position"]) and INVESTOR_CO.search(c["Position"]):
        return "investor"
    return ""


def safe(name):
    return re.sub(r'[\\/:*?"<>|#^\[\]]', "", name).strip()


def set_props(path, props):
    s = open(path, encoding="utf-8").read()
    if not s.startswith("---\n"):
        return False
    end = s.find("\n---", 4)
    fm = s[4:end]
    add = "".join(f"\n{k}: {v}" for k, v in props.items() if v and not re.search(rf"^{k}:", fm, re.M))
    if add:
        open(path, "w", encoding="utf-8").write(s[:end] + add + s[end:])
    return bool(add)


def url_key(u):
    return re.sub(r"^(https?://)?(www\.)?", "", (u or "").strip().lower()).rstrip("/")


def harmonic_upload(conns, out):
    rows = [c for c in conns if "--all" in sys.argv or role(c)]
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["linkedin_url", "full_name", "company", "position"])
        for c in rows:
            w.writerow([c["URL"], f"{c['First Name']} {c['Last Name']}".strip(), c["Company"], c["Position"]])
    print(f"wrote {len(rows)} people to {os.path.relpath(out, ROOT)} (upload this file to Harmonic)")


def harmonic_merge(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    if not rows or "linkedin_url" not in rows[0]:
        sys.exit("This doesn't look like the Harmonic export: it needs a linkedin_url column (see the linkedin skill).")
    pages = {}
    for p in glob.glob(os.path.join(WIKI, "people", "**", "*.md"), recursive=True):
        m = re.search(r"^linkedin:\s*(\S+)", open(p, encoding="utf-8").read(3000), re.M)
        if m:
            pages[url_key(m.group(1))] = p
    g = lambda r, k: (r.get(k) or "").replace("\ufffd", "").strip()  # Harmonic exports can carry U+FFFD
    done = 0
    for r in rows:
        p = pages.get(url_key(r["linkedin_url"]))
        if not p:
            continue
        city, country = g(r, "location_city"), g(r, "location_country")
        set_props(p, {"location": f'"{", ".join(x for x in (city, country) if x)}"' if city or country else "",
                      "country": f'"{country}"' if country else "",
                      "company_stage": g(r, "current_company_stage").lower(),
                      "company_funding_usd": g(r, "current_company_funding_usd") if g(r, "current_company_funding_usd") not in ("", "0") else "",
                      "prior_founder": "true" if g(r, "prior_founder") in ("1", "true", "True", "yes") else "",
                      "harmonic_enriched": str(datetime.date.today())})
        lines = [f"- {x}" for x in (g(r, "linkedin_headline"),
                                    "Now: " + g(r, "current_roles_clean") if g(r, "current_roles_clean") else "",
                                    "Before: " + g(r, "prior_experience_clean") if g(r, "prior_experience_clean") else "") if x]
        s = open(p, encoding="utf-8").read()
        s = re.sub(rf"\n{re.escape(BACKGROUND)}\n.*?(?=\n## |\Z)", "", s, flags=re.S).rstrip("\n")
        if lines:
            s += f"\n\n{BACKGROUND}\n\n" + "\n".join(lines) + f"\n\nSource: Harmonic export `{os.path.basename(path)}`.\n"
        open(p, "w", encoding="utf-8").write(s)
        done += 1
    print(f"{len(rows)} Harmonic rows: {done} person pages enriched, {len(rows) - done} had no page with that LinkedIn URL")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--harmonic" in sys.argv:
        return harmonic_merge(args[0] if args else sys.exit("Give the Harmonic export: --harmonic path/to/file.csv"))
    exports = glob.glob(os.path.join(ROOT, "raw", "linkedin", "Connections*.csv"))
    path = args[0] if args else max(exports, key=os.path.getmtime, default=None)
    if not path:
        sys.exit("No CSV found: put your LinkedIn Connections.csv in raw/linkedin/")
    conns = load(path)
    if "--harmonic-upload" in sys.argv:
        return harmonic_upload(conns, os.path.join(ROOT, "raw", "linkedin", "harmonic-upload.csv"))
    people = {os.path.basename(p)[:-3].lower(): p for p in glob.glob(os.path.join(WIKI, "people", "**", "*.md"), recursive=True)}
    orgs = {}
    for folder in ("companies", "investors"):
        for p in glob.glob(os.path.join(WIKI, folder, "*.md")):
            orgs[os.path.basename(p)[:-3].lower()] = p
            m = re.search(r"^aliases:\s*\[(.*?)\]", open(p, encoding="utf-8").read(4000), re.M)
            for a in (m.group(1).split(",") if m else []):
                if a.strip().strip("\"'"):
                    orgs.setdefault(a.strip().strip("\"'").lower(), p)
    os.makedirs(os.path.join(WIKI, "people", "network"), exist_ok=True)
    tagged = created = 0
    for c in conns:
        name = safe(f"{c['First Name']} {c['Last Name']}")
        if not name:
            continue
        since, kind = iso(c["Connected On"]), role(c)
        org = orgs.get(c["Company"].strip().lower())
        company = f'"[[{os.path.basename(org)[:-3]}]]"' if org else (f'"{c["Company"]}"' if c["Company"] else "")
        if name.lower() in people:
            tagged += set_props(people[name.lower()], {"linkedin": c["URL"], "linkedin_connection": "true",
                                                        "connected_since": since})
        elif kind or "--all" in sys.argv:
            p = os.path.join(WIKI, "people", "network", f"{name}.md")
            open(p, "w", encoding="utf-8").write(
                f"---\ntype: person\nrole: {kind or 'contact'}\ncompany: {company}\ntitle: \"{c['Position']}\"\n"
                f"linkedin: {c['URL']}\nlinkedin_connection: true\nconnected_since: {since}\ntier: network\n"
                f"last_updated: {datetime.date.today()}\ntags: [person, linkedin-network]\n---\n\n# {name}\n\n"
                f"{c['Position'] or 'Role not listed'} at {company.strip(chr(34)) or 'company not listed'}. "
                f"LinkedIn connection since {since or 'unknown date'}.\n\n## Sources\n- LinkedIn export `{os.path.basename(path)}`\n")
            people[name.lower()] = p
            created += 1
    by_org = {}
    for c in conns:
        org = orgs.get(c["Company"].strip().lower())
        if org:
            by_org.setdefault(org, []).append(c)
    for org, lst in by_org.items():
        s = open(org, encoding="utf-8").read()
        s = re.sub(rf"\n{re.escape(SECTION)}\n.*?(?=\n## |\Z)", "", s, flags=re.S).rstrip("\n")
        rows = []
        for c in sorted(lst, key=lambda c: c["Last Name"]):
            n = safe(f"{c['First Name']} {c['Last Name']}")
            rows.append(f"- {'[[' + n + ']]' if n.lower() in people else n} — {c['Position'] or 'role n/a'} · connected {iso(c['Connected On'])}")
        open(org, "w", encoding="utf-8").write(s + f"\n\n{SECTION}\n\n" + "\n".join(rows) + "\n")
    print(f"{len(conns)} connections: {tagged} existing pages tagged, {created} network profiles created, "
          f"{len(by_org)} company/investor pages got a '{SECTION[3:]}' section")


if __name__ == "__main__":
    main()
