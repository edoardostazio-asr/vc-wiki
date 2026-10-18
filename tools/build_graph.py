#!/usr/bin/env python3
"""Rebuild wiki/_graph/graph.db from relations.jsonl + page frontmatter, and write
confirmed relationships into company/investor page properties.

Usage (from the vault root):  python3 tools/build_graph.py [--check]
Safe to re-run: the database is rebuilt from scratch and properties are regenerated.
--check runs it twice and fails if the second run changes any page.
"""
import json, os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI = os.path.join(ROOT, "wiki")
GRAPH = os.path.join(WIKI, "_graph")
FOLDERS = [("people", "person"), ("people/network", "person"), ("companies", "company"),
           ("investors", "investor"), ("sectors", "sector"), ("concepts", "concept")]
RELS = ["founded_by", "key_person", "advisor", "board_member", "works_at", "invested_in_by", "customer",
        "supplier", "partners_with", "competes_with", "comparable_to", "licenses_to", "sister_company",
        "subsidiary_of", "acquired_by", "spun_out_of", "introduced"]
PROPERTY_PAGES = {"company", "investor"}  # pages whose frontmatter gets relationship properties
KNOWS = {"strong": 3, "warm": 2, "met": 1}


def owner():
    try:
        return json.load(open(os.path.join(ROOT, ".wiki", "state.json")))["owner"] or "Me"
    except (OSError, KeyError, ValueError):
        return "Me"


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return None, None
    end = text.find("\n---", 4)
    return (text[4:end], end) if end > 0 else (None, None)


def prop(fm, key):
    m = re.search(rf"^{key}:\s*(.*)$", fm or "", re.M)
    return m.group(1).strip().strip("\"'") if m else ""


def link_target(value):
    m = re.search(r"\[\[([^\]|#]+)", value or "")
    return m.group(1).strip() if m else (value or "").strip()


def load_pages():
    pages = {}
    for folder, kind in FOLDERS:
        d = os.path.join(WIKI, folder)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".md"):
                pages[f[:-3]] = (os.path.join(d, f), kind)
    return pages


def build():
    pages, me = load_pages(), owner()
    os.makedirs(GRAPH, exist_ok=True)
    db_path = os.path.join(GRAPH, "graph.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    db = sqlite3.connect(db_path)
    db.executescript("""
      CREATE TABLE nodes(id TEXT PRIMARY KEY, kind TEXT, status TEXT, sector TEXT, location TEXT,
                         has_page INTEGER, relationship TEXT, last_contact TEXT);
      CREATE TABLE edges(src TEXT, rel TEXT, dst TEXT, status TEXT, confidence TEXT, round TEXT, date TEXT,
                         strategic INTEGER, weight INTEGER, evidence TEXT, page TEXT, origin TEXT);
      CREATE INDEX e_src ON edges(src); CREATE INDEX e_dst ON edges(dst); CREATE INDEX e_rel ON edges(rel);
    """)
    nodes, edges = {}, []

    def node(name, kind="unknown", **fields):
        n = nodes.setdefault(name, dict(kind=kind, status="", sector="", location="", has_page=0,
                                        relationship="", last_contact=""))
        if n["kind"] == "unknown":
            n["kind"] = kind
        n.update({k: v for k, v in fields.items() if v})

    for name, (path, kind) in pages.items():
        fm, _ = split_frontmatter(open(path, encoding="utf-8", errors="ignore").read())
        rel_strength = prop(fm, "relationship")
        node(name, kind, has_page=1, status=prop(fm, "status"), sector=link_target(prop(fm, "sector")),
             location=prop(fm, "location") or prop(fm, "hq"), relationship=rel_strength,
             last_contact=prop(fm, "last_contact"))
        if kind == "person" and prop(fm, "company"):
            edges.append(dict(src=name, rel="works_at", dst=link_target(prop(fm, "company")), status="confirmed",
                              confidence="high", origin="property", page=name))
        # "knows" edges: people you have met (weighted) and LinkedIn connections (weight 1)
        weight = KNOWS.get(rel_strength, 1 if prop(fm, "linkedin_connection") == "true" else 0)
        if kind == "person" and weight:
            edges.append(dict(src=me, rel="knows", dst=name, status="confirmed", confidence="high",
                              weight=weight, origin="relationship", page=name,
                              date=prop(fm, "last_contact") or prop(fm, "connected_since")))
    node(me, "person", has_page=1 if me in pages else 0)

    rel_file = os.path.join(GRAPH, "relations.jsonl")
    if os.path.exists(rel_file):
        for n, line in enumerate(open(rel_file, encoding="utf-8"), 1):
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except ValueError:
                sys.exit(f"relations.jsonl line {n} is not valid JSON")
            e["src"], e["dst"], e["origin"] = e.pop("source"), e.pop("target"), "extracted"
            edges.append(e)

    for e in edges:
        node(e["src"]); node(e["dst"])
    db.executemany("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
                   [(k, v["kind"], v["status"], v["sector"], v["location"], v["has_page"], v["relationship"],
                     v["last_contact"]) for k, v in nodes.items()])
    db.executemany("INSERT INTO edges VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   [(e["src"], e["rel"], e["dst"], e.get("status"), e.get("confidence"), e.get("round"),
                     e.get("date"), 1 if e.get("strategic") else 0, e.get("weight", 1), e.get("evidence"),
                     e.get("page"), e["origin"]) for e in edges])
    db.commit()
    assert db.execute("SELECT count(*) FROM edges").fetchone()[0] == len(edges)

    # Write confirmed, high-confidence extracted edges into the subject page's properties.
    props = {}
    for e in edges:
        if e["origin"] == "extracted" and e.get("status") == "confirmed" and e.get("confidence") == "high" \
                and e["src"] in pages and pages[e["src"]][1] in PROPERTY_PAGES and e["rel"] in RELS:
            value = f'"[[{e["dst"]}]]"' if e["dst"] in pages else json.dumps(e["dst"], ensure_ascii=False)
            values = props.setdefault(e["src"], {}).setdefault(e["rel"], [])
            if value not in values:
                values.append(value)
    changed = 0
    for name, (path, kind) in pages.items():
        if kind not in PROPERTY_PAGES:
            continue
        text = open(path, encoding="utf-8", errors="ignore").read()
        fm, end = split_frontmatter(text)
        if fm is None:
            continue
        kept = [l for l in fm.split("\n") if not re.match(rf"^({'|'.join(RELS)}):", l)]
        added = [f"{r}: [{', '.join(sorted(props[name][r]))}]" for r in RELS if r in props.get(name, {})]
        new = "---\n" + "\n".join(kept + added) + text[end:]
        if new != text:
            open(path, "w", encoding="utf-8").write(new)
            changed += 1
    print(f"graph.db: {len(nodes)} nodes, {len(edges)} edges; relationship properties updated on {changed} pages")
    return changed


if __name__ == "__main__":
    build()
    if "--check" in sys.argv:
        if build() != 0:
            sys.exit("check failed: a second run changed pages (property writing is not idempotent)")
        print("check passed")
