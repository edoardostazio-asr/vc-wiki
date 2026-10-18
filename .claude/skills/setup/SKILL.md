---
name: setup
description: First-time setup of the VC Wiki vault. Use when the user says "set up", "setup", "get started", "install the wiki", or opens a fresh copy of this repo (CLAUDE.md still contains {{OWNER_NAME}}). Interviews the user, fills the firm profile, checks connectors, schedules the daily ingest and weekly lint, and starts the 7-week backfill.
---

# Setup

Goal: from a fresh clone to a working, self-updating wiki in one sitting, with as few questions as possible. Do the steps in order. If a step can't be completed (a missing connector, for example), note it, keep going, and list it at the end with the exact fix.

## 1. Check where you are
- Confirm the working directory is this repo (it contains `CLAUDE.md` and `tools/`). If `CLAUDE.md` no longer contains `{{OWNER_NAME}}`, setup has already run: ask before running it again.
- Check `python3 --version` and `git --version`. Both ship with macOS; if `git` is missing, tell the user to run `xcode-select --install` and stop until it's done.

## 2. Interview (one AskUserQuestion call, 4 questions max)
Ask only what you can't infer. Prefer options plus "Other":
1. Name and role (e.g. "Jane Doe, Investment Manager").
2. Firm, plus any strategic parent group or business units whose involvement matters (e.g. a corporate VC's parent companies). "None" is a valid answer.
3. Focus sectors / theses (multi-select from common VC sectors, plus Other).
4. Stages and geographies.

Write the answers into the **Firm profile** section of `CLAUDE.md` (replace every `{{...}}` placeholder; `SETUP_DATE` is today). Create one sector page per focus sector in `wiki/sectors/` from `templates/sector.md`.

## 3. State file
Write `.wiki/state.json`:
```json
{"owner": "<Name>", "setup_date": "<YYYY-MM-DD>",
 "granola_cursor": "<today minus 7 weeks, ISO date>", "email_cursor": "<same>",
 "backfill": {"start": "<today minus 7 weeks>", "end": "<today>", "weeks_done": []},
 "linkedin_imported": null, "notes": {"folder": null, "cursor": "<today minus 7 weeks>"}}
```
The owner's name is the "me" node in the relationship graph. Also create `wiki/people/<Name>.md` from `templates/person.md` with `role: colleague`.

## 4. Connectors
Check which tools are available in this session:
- **Granola** (a tool that lists meetings, such as `list_meetings`). If missing: "Open claude.ai → Settings → Connectors → Granola → Connect, sign in, then start a new Claude session in this folder."
- **Microsoft 365 / Outlook** (an email search tool, such as `outlook_email_search`). If missing: same path, "Microsoft 365".
- Optional: **Harmonic** (enriches LinkedIn connections with location and background), **Affinity** (CRM).
- Optional: **Apple Notes** (no connector; read locally). Ask: "Do you keep work notes in Apple Notes? If so, make one folder for them (e.g. **VC Wiki**) and tell me its name. I only ever read that folder." Save the name in `notes.folder`, then run `python3 tools/import_notes.py --folder "<name>" --since <notes.cursor>` once: macOS will ask to let Claude control Notes; tell the user to click **Allow**.
Make one tiny read call to each available connector (e.g. list one meeting) to confirm it really works. Never send or modify anything through a connector during setup.

## 5. Obsidian
- If `/Applications/Obsidian.app` doesn't exist: tell the user to install it from https://obsidian.md (free), then "Open folder as vault" and pick this folder.
- The repo ships `.obsidian/` settings: attachments go to `raw/assets/`, templates come from `templates/`, and the graph hides `wiki/people/network/`.

## 6. Git
- `git init` if there is no `.git`; then commit the configured template ("Setup: <Name>").
- If the clone still points at the template repo (`git remote -v`), remove that remote (`git remote remove origin`) so personal data can never be pushed there. Offer, without pushing anything, to create a **private** personal backup repo later.

## 7. Schedule the automatic runs
Use the scheduled-tasks tool (create a scheduled task). Create two tasks with this folder as the working directory:
- **"VC Wiki: daily ingest"**: weekdays at 18:30 local time, prompt: `Run the ingest skill in daily mode.`
- **"VC Wiki: weekly lint"**: Fridays at 17:00, prompt: `Run the lint skill in scheduled mode.`
If no scheduled-tasks tool is available, explain: "In the Claude desktop app, open the Code tab → Scheduled → New task", and give both prompts and times. Note that scheduled runs only fire while the computer is awake and the Claude app is running.

## 8. LinkedIn (manual, optional now)
Explain: "LinkedIn → Me → Settings & Privacy → Data privacy → Get a copy of your data → tick only Connections → Request. The email arrives in about 10 minutes. Drop `Connections.csv` into `raw/linkedin/` and say 'import LinkedIn'." If a CSV is already there, run the `linkedin` skill now.

## 9. Start the backfill
Run the `ingest` skill in **backfill** mode for the most recent week only, so the user sees value immediately. The daily scheduled run then processes one more backfill week per weekday on top of new activity, so the 7 weeks complete within about 7 working days without hitting Claude Pro usage limits.

## 10. Finish
Report in plain language: what's set up, what's scheduled and when, what's still missing (with the exact click path), and what to do next: "Open the vault in Obsidian and start at Home. Ask me questions any time, e.g. 'who do I know at X?'".
