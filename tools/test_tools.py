#!/usr/bin/env python3
"""Self-test for the tools on a throwaway sample vault. Run: python3 tools/test_tools.py"""
import json, os, shutil, sqlite3, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def run(vault, *args):
    return subprocess.run([sys.executable, os.path.join(vault, "tools", args[0]), *args[1:]], cwd=vault,
                          capture_output=True, text=True)


def write(vault, rel, text):
    p = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(text)


def main():
    v = tempfile.mkdtemp()
    shutil.copytree(HERE, os.path.join(v, "tools"))
    write(v, ".wiki/state.json", json.dumps({"owner": "Ada Investor"}))
    write(v, "wiki/companies/Acme Robotics.md", "---\ntype: company\nstatus: prospect\nsector: \"[[Robotics]]\"\n---\n\n"
          "# Acme Robotics\n\nFounded by [[Jane Doe]]. Seed led by [[Blue Fund]].\n")
    write(v, "wiki/investors/Blue Fund.md", "---\ntype: investor\nkind: vc\n---\n\n# Blue Fund\n")
    write(v, "wiki/sectors/Robotics.md", "---\ntype: sector\n---\n\n# Robotics\n")
    write(v, "wiki/people/Ada Investor.md", "---\ntype: person\nrole: self\nrelationship: strong\n---\n\n# Ada Investor\n")
    write(v, "raw/granola/2026-10-01-acme.md", "---\ntitle: x\n---\n")
    write(v, "wiki/people/Jane Doe.md", "---\ntype: person\nrole: founder\ncompany: \"[[Acme Robotics]]\"\n"
          "relationship: warm\nlast_contact: 2026-10-01\n---\n\n# Jane Doe\n")
    write(v, "wiki/_graph/relations.jsonl", "\n".join(json.dumps(e) for e in [
        {"source": "Acme Robotics", "rel": "founded_by", "target": "Jane Doe", "target_page": True, "status": "confirmed",
         "confidence": "high", "evidence": "Founded by [[Jane Doe]].", "page": "Acme Robotics"},
        {"source": "Acme Robotics", "rel": "invested_in_by", "target": "Blue Fund", "target_page": True, "status": "confirmed",
         "confidence": "high", "round": "seed", "evidence": "Seed led by [[Blue Fund]].", "page": "Acme Robotics"},
        {"source": "Acme Robotics", "rel": "customer", "target": "Big Corp", "target_page": False, "status": "potential",
         "confidence": "low", "evidence": "Seed led by [[Blue Fund]].", "page": "Acme Robotics"}]) + "\n")
    write(v, "raw/linkedin/Connections.csv", "Notes:\n\"LinkedIn note line\"\n\nFirst Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
          "Jane,Doe,https://www.linkedin.com/in/jane,,Acme Robotics,CEO & Co-founder,01 Mar 2025\n"
          "Max,Partner,https://www.linkedin.com/in/max,,Blue Fund,General Partner,05 Jan 2026\n"
          "Sam,Engineer,https://www.linkedin.com/in/sam,,Acme Robotics,Engineer,07 Feb 2026\n")

    r = run(v, "import_linkedin.py")
    assert r.returncode == 0, r.stderr
    assert os.path.exists(f"{v}/wiki/people/network/Max Partner.md"), "investor connection should get a network page"
    assert not os.path.exists(f"{v}/wiki/people/network/Sam Engineer.md"), "non-founder/investor skipped without --all"
    assert "linkedin_connection: true" in open(f"{v}/wiki/people/Jane Doe.md").read()
    acme = open(f"{v}/wiki/companies/Acme Robotics.md").read()
    assert "People you know (LinkedIn)" in acme and "Sam Engineer" in acme
    assert run(v, "import_linkedin.py").returncode == 0 and acme == open(f"{v}/wiki/companies/Acme Robotics.md").read(), \
        "re-import must be idempotent"

    r = run(v, "import_linkedin.py", "--harmonic-upload")
    up = open(f"{v}/raw/linkedin/harmonic-upload.csv").read()
    assert r.returncode == 0 and "jane" in up and "max" in up and "sam" not in up, up
    write(v, "raw/linkedin/harmonic-enriched.csv",
          "linkedin_url,full_name,linkedin_headline,location_city,location_country,current_roles_clean,"
          "current_company_stage,current_company_funding_usd,prior_experience_clean,prior_founder\n"
          "linkedin.com/in/jane/,Jane Doe,CEO @ Acme,Munich,Germany,CEO @ Acme Robotics,SEED,4000000,Engineer @ KUKA (2018-2022),1\n")
    for _ in range(2):  # merging twice must not duplicate the section
        r = run(v, "import_linkedin.py", "--harmonic", f"{v}/raw/linkedin/harmonic-enriched.csv")
        assert r.returncode == 0 and "1 person pages enriched" in r.stdout, r.stdout + r.stderr
    jane = open(f"{v}/wiki/people/Jane Doe.md").read()
    assert 'location: "Munich, Germany"' in jane and "prior_founder: true" in jane and jane.count("## Background (Harmonic)") == 1, jane
    assert run(v, "import_linkedin.py").returncode == 0, "a Harmonic CSV in raw/linkedin must not be mistaken for the LinkedIn export"

    r = run(v, "build_graph.py", "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    acme = open(f"{v}/wiki/companies/Acme Robotics.md").read()
    assert 'founded_by: ["[[Jane Doe]]"]' in acme and 'invested_in_by: ["[[Blue Fund]]"]' in acme
    assert "customer:" not in acme, "low-confidence edges must not reach page properties"
    db = sqlite3.connect(f"{v}/wiki/_graph/graph.db")
    path = db.execute("""SELECT k.dst FROM edges k JOIN edges w ON w.src=k.dst AND w.rel='works_at'
                         WHERE k.src='Ada Investor' AND k.rel='knows' AND w.dst='Acme Robotics'""").fetchall()
    assert not db.execute("SELECT 1 FROM edges WHERE src='Ada Investor' AND rel='knows' AND dst='Ada Investor'").fetchall(), \
        "the owner must not know themselves"
    assert ("Jane Doe",) in path, "owner -> knows -> works_at path should resolve"

    write(v, "wiki/people/Jane Doe.md", open(f"{v}/wiki/people/Jane Doe.md").read() + "\nSource: [[raw/granola/2026-10-01-acme]]\n")
    r = run(v, "validate.py")
    assert r.returncode == 0 and "raw/granola" not in r.stdout and "2026-10-01-acme" not in r.stdout, r.stdout
    write(v, "wiki/companies/Bad.md", "---\ntype: company\nrelated: [[[Acme Robotics]], [[Robotics]]]\n---\n</content>\n")
    r = run(v, "validate.py")
    assert r.returncode == 1 and "[[[link]]" in r.stdout and "stray tool markup" in r.stdout, r.stdout

    sys.path.insert(0, f"{v}/tools")
    import import_notes
    note = {"id": "x-coredata://n1", "title": "Robotics thesis", "created": "2026-10-01T09:00:00Z",
            "modified": "2026-10-02T09:00:00Z", "body": "Humanoids need cheap actuators."}
    secret = dict(note, id="x-coredata://n2", title="keys", body="openai sk-abcdefghijklmnopqrstu")
    out = f"{v}/raw/notes"
    empty = dict(note, id="x-coredata://n4", title="New Note", body="New Note")
    written, skipped = import_notes.write([note, secret, empty], out)
    assert len(written) == 1 and skipped == ["keys"], "notes holding keys must never be copied"
    twin, _ = import_notes.write([dict(note, id="x-coredata://n3")], out)
    assert twin[0] != written[0], "two notes with the same day and title must not overwrite each other"
    written2, _ = import_notes.write([dict(note, title="Renamed", body="v2")], out)
    assert written2 == written and "v2" in open(written[0]).read(), "an edited note updates its existing file"

    import compile as comp
    comp.ROOT, comp.DONE = v, f"{v}/.wiki/compiled.txt"
    for i in range(12):
        write(v, f"raw/granola/2026-10-{i+1:02d}-m{i}.md", f"---\ntitle: m{i}\n---\n")
    first = comp.pending()
    assert [len(f) for s, f in first if s == "granola"] == [10, 3], first
    fake = f"{v}/fake-claude"
    write(v, "fake-claude", "#!/bin/sh\necho '{\"total_cost_usd\": 0.42, \"is_error\": false, \"result\": \"ok\"}'\n")
    os.chmod(fake, 0o755)
    comp.CLAUDE = fake
    comp.ENV_FILE = f"{v}/test.env"
    write(v, "test.env", "# key\nANTHROPIC_API_KEY='sk-ant-test'\n")
    comp.keychain = lambda: "xx sk-ant-abc sk-ant-a"  # a garbled keychain entry must be skipped
    assert comp.api_key() == "sk-ant-test", "env-file fallback"
    write(v, "test.env", "* sk-ant-bare\n")
    assert comp.api_key() == "sk-ant-bare", "a bare key line works too"
    ok, cost, _ = comp.run_batch(first[0][1], "sk-test", 5)
    assert ok and cost == 0.42
    for s, f in first:
        comp.mark(f)
    assert comp.pending() == [], "compiled files must not be queued again"
    write(v, "raw/notes/2026-10-02-thesis.md", "---\ntitle: t\n---\nv1\n")
    comp.mark([f"{v}/raw/notes/2026-10-02-thesis.md"])
    write(v, "raw/notes/2026-10-02-thesis.md", "---\ntitle: t\n---\nv2\n")
    assert [s for s, _ in comp.pending()] == ["notes"], "an edited note must be recompiled"
    shutil.rmtree(v)
    print("all tool tests passed")


if __name__ == "__main__":
    main()
