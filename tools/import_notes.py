#!/usr/bin/env python3
"""Copy Apple Notes from one folder into raw/notes/ so ingest can read them.

Usage (from the vault root):  python3 tools/import_notes.py --folder "VC Wiki" [--since 2026-08-01]

- Reads only the named Notes folder (any account), via macOS's own scripting bridge; no extra install.
- Writes one file per note to raw/notes/<created>-<slug>.md, keyed by the note's id.
  Notes are living documents, so a note edited since the last import is re-written in place.
- Prints the files written and the newest modification time (the next --since cursor).
macOS asks once for permission to let the Claude app control Notes.
"""
import argparse, glob, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "raw", "notes")
# Notes often hold keys and passwords; a note that looks like one is never copied.
SECRET = re.compile(r"\b(sk|pk|rk|ghp|xox[bp])[-_][A-Za-z0-9_-]{16,}|\bpassword\b|\bapi[ _-]?key\b|\biban\b|-----BEGIN", re.I)
JXA = """
function run(argv) {
  const Notes = Application('Notes'), since = new Date(argv[1] || 0), out = [];
  Notes.folders.whose({name: argv[0]})().forEach(f => {
    const ids = f.notes.id(), names = f.notes.name(), created = f.notes.creationDate(), mod = f.notes.modificationDate();
    ids.forEach((id, i) => {
      if (mod[i] <= since) return;
      out.push({id, title: names[i], created: created[i].toISOString(), modified: mod[i].toISOString(),
                body: f.notes.byId(id).plaintext()});
    });
  });
  return JSON.stringify(out);
}"""


def fetch(folder, since):
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", JXA, folder, since or ""], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"Apple Notes export failed: {r.stderr.strip()}\n"
                 "If macOS blocked it: System Settings > Privacy & Security > Automation > allow Claude to control Notes.")
    return json.loads(r.stdout or "[]")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "note"


def write(notes, out=OUT):
    os.makedirs(out, exist_ok=True)
    existing = {}
    for p in glob.glob(os.path.join(out, "*.md")):
        m = re.search(r"^notes_id: (.+)$", open(p, encoding="utf-8").read(), re.M)
        if m:
            existing[m.group(1)] = p
    written, skipped = [], []
    for n in notes:
        if SECRET.search(n["title"] + "\n" + n["body"]):
            skipped.append(n["title"][:40])
            continue
        path = existing.get(n["id"])
        if not path:
            base, k = os.path.join(out, f"{n['created'][:10]}-{slug(n['title'])}"), 1
            path = base + ".md"
            while os.path.exists(path):  # same day and title as another note
                k += 1
                path = f"{base}-{k}.md"
            existing[n["id"]] = path
        title = n["title"].replace('"', "'")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f'---\nnotes_id: {n["id"]}\ntitle: "{title}"\ncreated: {n["created"]}\n'
                    f'modified: {n["modified"]}\nsource: apple-notes\n---\n\n{n["body"].strip()}\n')
        written.append(path)
    return written, skipped


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--folder", required=True)
    a.add_argument("--since", help="ISO date or datetime; only notes modified after it")
    args = a.parse_args()
    notes = fetch(args.folder, args.since)
    written, skipped = write(notes)
    for p in written:
        print(os.path.relpath(p, ROOT))
    if skipped:
        print(f"skipped {len(skipped)} note(s) that look like they hold a key or password")
    print(f"{len(notes)} notes; newest modified: {max((n['modified'] for n in notes), default=args.since or '-')}")
