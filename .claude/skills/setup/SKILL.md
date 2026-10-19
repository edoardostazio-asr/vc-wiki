---
name: setup
description: First-time setup of the VC Wiki vault. Use when the user says "set up", "setup", "get started", "install the wiki", or opens a fresh copy of this repo (CLAUDE.md still contains {{OWNER_NAME}}). Interviews the user, fills the firm profile, checks connectors, schedules the daily ingest and weekly lint, and starts the backfill. Asks which sources to use before fetching anything.
---

# Setup

Goal: from a fresh clone to a working, self-updating wiki in one sitting, with as few questions as possible. Do the steps in order. If a step can't be completed (a missing connector, for example), note it, keep going, and list it at the end with the exact fix.

## 1. Check where you are
- Confirm the working directory is this repo (it contains `CLAUDE.md` and `tools/`). If `CLAUDE.md` no longer contains `{{OWNER_NAME}}`, setup has already run: ask before running it again.
- Check `python3 --version` and `git --version`. Both ship with macOS; if `git` is missing, tell the user to run `xcode-select --install` and stop until it's done.

## 2. What should feed the wiki? (ask before fetching anything)
One AskUserQuestion call with these three questions. Give each source option a `preview` showing exactly what is read, so the card is self-explanatory:
1. **Sources** (multiSelect): *Granola meetings* (preview: "Your own meeting notes and summaries. Colleagues' meetings are never read."), *Outlook email* (preview: "Everything you receive and send, minus newsletters, notifications and calendar noise. Never sends, moves or deletes."), *Apple Notes* (preview: "One folder you choose, e.g. 'VC Wiki'. Notes with passwords or keys are skipped."), *LinkedIn connections* (preview: "A one-off export you download yourself; adds who you know at each company.").
2. **History**: how far back to backfill: *2 weeks*, *4 weeks (Recommended)*, *7 weeks*.
3. **Anthropic API key**: *Yes, I have one (Recommended)* (preview: "The heavy processing runs on your key with Sonnet, so your Claude Pro allowance stays free. A month of history costs roughly $20–60 depending on your inbox; daily upkeep about $1–2 a day."), *No, use my Claude Pro plan* (preview: "Free, but slower: one week of history per weekday, to stay within Pro limits.").

Files dropped into `raw/` always work and need no choice. Save the answers in `.wiki/state.json` (step 4): `sources`, `backfill`, `api_key`. Only ever fetch the chosen sources, now and in scheduled runs; the user can change them later by saying "change my sources".

## 3. Profile (second AskUserQuestion call, 4 questions max)
Ask only what you can't infer. Prefer options plus "Other":
1. Name and role (e.g. "Jane Doe, Investment Manager").
2. Firm, plus any strategic parent group or business units whose involvement matters (e.g. a corporate VC's parent companies). "None" is a valid answer.
3. Focus sectors / theses (multi-select from common VC sectors, plus Other).
4. Stages and geographies.

Write the answers into the **Firm profile** section of `CLAUDE.md` (replace every `{{...}}` placeholder; `SETUP_DATE` is today). Create one sector page per focus sector in `wiki/sectors/` from `templates/sector.md`.

## 4. State file
Write `.wiki/state.json`:
```json
{"owner": "<Name>", "setup_date": "<YYYY-MM-DD>",
 "sources": ["granola", "email", "notes", "linkedin"], "api_key": true,
 "granola_cursor": "<today, ISO datetime>", "email_cursor": "<same>",
 "backfill": {"start": "<today minus N weeks>", "end": "<today>", "weeks_done": []},
 "linkedin_imported": null, "notes": {"folder": null, "cursor": "<backfill start>"}}
```
Daily cursors start at setup; the backfill covers the N weeks before, so nothing is fetched twice.
The owner's name is the "me" node in the relationship graph. Also create the owner page `wiki/people/<Name>.md` (`type: person`, `role: self`, `company: "[[<Firm>]]"`, no `relationship` field, a one-line Summary), and the firm's own page `wiki/investors/<Firm>.md` from `templates/investor.md`.

## 5. API key (only if they said yes)
You never see or type the key. Tell the user:
1. Create a key at https://console.anthropic.com → **API Keys** (a few dollars of credit is enough to start; set a monthly limit under **Limits** if they like).
2. Store it in the macOS keychain (never in the vault). The Claude app's own terminal pane can't paste into hidden prompts, so use one of:
   - The **Terminal** app (Cmd+Space, "Terminal"): run `security add-generic-password -s vc-wiki-anthropic -a "$USER" -w`, paste the key with Cmd+V at each of the two hidden prompts, pressing Enter after each.
   - Or **Keychain Access** → File → New Password Item: name `vc-wiki-anthropic`, account = their Mac user name (`whoami`), password = the key.
3. If `claude --version` fails in Terminal, install the Claude Code command line once: `curl -fsSL https://claude.ai/install.sh | bash`.
Then check with `python3 tools/compile.py --dry-run` (it must not say "No API key"). If anything fails, set `api_key: false` and continue on Pro; they can add the key later.

## 6. Connectors (chosen sources only)
Check only the sources the user chose:
- **Granola** (a tool that lists meetings, such as `list_meetings`). If missing: "Open claude.ai → Settings → Connectors → Granola → Connect, sign in, then start a new Claude session in this folder."
- **Microsoft 365 / Outlook** (an email search tool, such as `outlook_email_search`). If missing: same path, "Microsoft 365".
- Optional: **Harmonic** (enriches LinkedIn connections with location and background), **Affinity** (CRM).
- **Apple Notes** (no connector; read locally). Ask which folder holds their work notes (suggest making one called **VC Wiki**); "I only ever read that folder." Save the name in `notes.folder`, then run `python3 tools/import_notes.py --folder "<name>" --since <today>` once as an access check (nothing old is imported; the backfill picks those up): macOS will ask to let Claude control Notes; tell the user to click **Allow**.
Make one tiny read call to each available connector (e.g. list one meeting) to confirm it really works. Never send or modify anything through a connector during setup.

## 7. Obsidian
- If `/Applications/Obsidian.app` doesn't exist: tell the user to install it from https://obsidian.md (free), then "Open folder as vault" and pick this folder.
- The repo ships `.obsidian/` settings: attachments go to `raw/assets/`, templates come from `templates/`, and the graph hides `wiki/people/network/`.

## 8. Git
- `git init` if there is no `.git`. If `git config user.email` is empty (normal on a fresh Mac), set a repo-local identity from the interview: `git config user.name "<Name>"` and `git config user.email "<their work email>"` (the Microsoft 365 connector's profile tool gives the address). Then commit the configured template ("Setup: <Name>").
- If the clone still points at the template repo (`git remote -v`), remove that remote (`git remote remove origin`) so personal data can never be pushed there. Offer, without pushing anything, to create a **private** personal backup repo later.

## 9. Schedule the automatic runs
Use the scheduled-tasks tool (create a scheduled task). Scheduled runs don't start in this folder, so each prompt must name it (use the absolute path from `pwd`):
- **"VC Wiki: daily ingest"**: cron `30 18 * * 1-5`, prompt: `Working directory: <absolute path>. cd there first. Read .claude/skills/ingest/SKILL.md and run it in daily mode.`
- **"VC Wiki: weekly lint"**: cron `0 17 * * 5`, prompt: `Working directory: <absolute path>. cd there first. Read .claude/skills/lint/SKILL.md and run it in scheduled mode.`
The scheduler may shift the time by a few minutes; that's expected. Tell the user to open **Scheduled** in the sidebar and click **Run now** on the daily ingest once, after setup: it approves the connectors for future unattended runs, and it processes the next backfill week.
If no scheduled-tasks tool is available, explain: "In the Claude desktop app, open the Code tab → Scheduled → New task", and give both prompts and times. Note that scheduled runs only fire while the computer is awake and the Claude app is running.

## 10. LinkedIn (only if chosen)
Explain: "LinkedIn → Me → Settings & Privacy → Data privacy → Get a copy of your data → tick only Connections → Request. The email arrives in about 10 minutes. Drop `Connections.csv` into `raw/linkedin/` and say 'import LinkedIn'." If a CSV is already there, run the `linkedin` skill now.

## 11. Start the backfill
- **With an API key:** run the `ingest` skill in **backfill** mode for *all* chosen weeks now, newest week first. In this mode the session only fetches (cheap); `tools/compile.py` does the processing on the API key after each fetched week, so pages appear as you go. Tell the user the rough cost before starting (2 weeks ≈ $10–30, 4 weeks ≈ $20–60, 7 weeks ≈ $35–100, depending on meeting and email volume) and that `compile.py` stops at $40 per run unless they say otherwise. If Claude Pro limits stop the fetching, the daily scheduled run continues it.
- **Without a key:** run the `ingest` skill in **backfill** mode for the most recent week only. The daily scheduled run then does one more week per weekday, so the history completes without hitting Claude Pro limits.

## 12. Finish
Report in plain language: what's set up, what's scheduled and when, what's still missing (with the exact click path), and what to do next: "Open the vault in Obsidian and start at Home. Ask me questions any time, e.g. 'who do I know at X?'".
