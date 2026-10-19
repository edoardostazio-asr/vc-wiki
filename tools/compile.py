#!/usr/bin/env python3
"""Compile new raw/ captures into wiki pages on the user's Anthropic API key.

Usage (from the vault root):
  python3 tools/compile.py                 compile everything pending, batch by batch
  python3 tools/compile.py --dry-run       list pending batches and stop
  python3 tools/compile.py --budget 20     stop once this run has spent $20 (default 40)
  python3 tools/compile.py --mark FILE...  record files as compiled (used after an in-session compile on Pro)

Fetching (Granola, Outlook) happens in a normal Claude session, which writes raw/ files. This script then
runs one short headless Claude Code session per batch on the API key, with Sonnet, no connectors and the
vault's own permissions. The key is read from the macOS keychain (service "vc-wiki-anthropic"), or else from
~/.vc-wiki.env (a line ANTHROPIC_API_KEY=...); both live outside the vault, so it never touches the repo. Progress is in .wiki/compiled.txt (path + content hash), so an edited note is recompiled
and an interrupted run resumes where it stopped. Each batch is committed; spend is logged to .wiki/costs.log.
"""
import argparse, datetime, glob, hashlib, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONE = os.path.join(ROOT, ".wiki", "compiled.txt")
COSTS = os.path.join(ROOT, ".wiki", "costs.log")
SOURCES = ["granola", "email", "notes", "web"]
BATCH = {"granola": 10, "email": 1, "notes": 10, "web": 5}  # files per session; an email digest is already a batch
CLAUDE = os.environ.get("VC_WIKI_CLAUDE", "claude")
PROMPT = """Read CLAUDE.md, then the "Compile" section of .claude/skills/ingest/SKILL.md, and compile these raw \
captures into the wiki. Do not fetch anything and do not commit; the caller commits.

{files}"""


def digest(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]


def compiled():
    if not os.path.exists(DONE):
        return set()
    return {tuple(l.split()) for l in open(DONE) if l.strip()}


def mark(paths):
    os.makedirs(os.path.dirname(DONE), exist_ok=True)
    with open(DONE, "a") as f:
        for p in paths:
            f.write(f"{os.path.relpath(os.path.abspath(p), ROOT)} {digest(p)}\n")


def pending():
    done = compiled()
    batches = []
    for src in SOURCES:
        files = sorted(p for p in glob.glob(os.path.join(ROOT, "raw", src, "*.md"))
                       if (os.path.relpath(p, ROOT), digest(p)) not in done)
        n = BATCH[src]
        batches += [(src, files[i:i + n]) for i in range(0, len(files), n)]
    return batches


ENV_FILE = os.path.expanduser("~/.vc-wiki.env")  # outside the vault, so Claude never reads or commits it


def keychain():
    r = subprocess.run(["security", "find-generic-password", "-s", "vc-wiki-anthropic", "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def api_key():
    k = keychain()
    if re.fullmatch(r"sk-ant-[A-Za-z0-9_-]+", k):  # a mangled paste (twice, stray chars) is ignored, not sent
        return k
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE):
            k, _, v = line.strip().partition("=")
            if k.strip() == "ANTHROPIC_API_KEY" and v.strip():
                return v.strip().strip('"\'')
    return None


def run_batch(files, key, cap):
    rel = [os.path.relpath(p, ROOT) for p in files]
    cmd = [CLAUDE, "-p", PROMPT.format(files="\n".join(f"- {r}" for r in rel)),
           "--model", "sonnet", "--output-format", "json", "--max-budget-usd", f"{cap:.2f}",
           "--setting-sources", "project", "--strict-mcp-config", "--no-session-persistence",
           "--permission-mode", "acceptEdits",
           # explicit, because headless runs ignore .claude/settings.json until the folder is trusted interactively
           "--allowedTools", "Read", "Edit", "Write", "Glob", "Grep",
           "Bash(python3 tools/build_graph.py:*)", "Bash(python3 tools/validate.py:*)"]
    env = dict(os.environ, ANTHROPIC_API_KEY=key)
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    try:
        out = json.loads(r.stdout)
    except ValueError:
        out = {"is_error": True, "result": (r.stderr or r.stdout)[-500:]}
    return r.returncode == 0 and not out.get("is_error"), float(out.get("total_cost_usd") or 0), out.get("result", "")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--budget", type=float, default=40.0)
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--mark", nargs="+")
    args = a.parse_args()
    if args.mark:
        mark(args.mark)
        return print(f"marked {len(args.mark)} file(s) as compiled")
    batches = pending()
    print(f"{len(batches)} batch(es) pending: " + ", ".join(f"{s}:{len(f)}" for s, f in batches) if batches else "nothing pending")
    if args.dry_run or not batches:
        return
    key = api_key()
    if not key:
        sys.exit("No API key found (keychain service vc-wiki-anthropic, or ANTHROPIC_API_KEY=... in ~/.vc-wiki.env). "
                 "Compile in the Claude session instead, or add the key.")
    spent = 0.0
    for src, files in batches:
        left = args.budget - spent
        if left < 1:
            print(f"budget reached (${spent:.2f}); run again to continue")
            break
        ok, cost, result = run_batch(files, key, min(left, 5.0))  # shortcut: $5 cap per batch, raise if batches grow
        spent += cost
        with open(COSTS, "a") as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {src} {len(files)} files ${cost:.2f} {'ok' if ok else 'FAILED'}\n")
        if not ok:
            print(f"batch failed ({src}, {len(files)} files, ${cost:.2f}): {result[:300]}\nStopped; nothing marked. Run again to retry.")
            sys.exit(1)
        mark(files)
        subprocess.run(["git", "add", "-A"], cwd=ROOT)
        subprocess.run(["git", "commit", "-qm", f"Compile {src}: {len(files)} file(s) (API, ${cost:.2f})"], cwd=ROOT)
        print(f"compiled {src}: {len(files)} file(s), ${cost:.2f} (run total ${spent:.2f})")
    print(f"done: ${spent:.2f} spent this run")


if __name__ == "__main__":
    main()
