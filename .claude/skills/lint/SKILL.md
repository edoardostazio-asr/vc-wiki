---
name: lint
description: Health-check the VC Wiki. Use for "lint", "health check", "clean up the wiki", and when the weekly scheduled task asks for "lint in scheduled mode". Finds broken links, duplicates, contradictions, stale claims, missing pages and cooling relationships, and proposes fixes.
---

# Lint

## 1. Mechanical checks
Run `python3 tools/validate.py`. ERRORs are real bugs (missing frontmatter, unquoted `[[[link]]` lists, stray tool markup, invalid relationship lines); fix them directly. Group the warnings for the report.

## 2. Judgment checks
- **Missing pages:** broken links that many pages point to (the top of the validator's broken-link list). Propose creating them from the raw notes that mention them.
- **Duplicates:** likely-duplicate people or companies (name variants, accents, emoji, ".io" suffixes). Propose a merge: keep the fuller page, move unique content, make the other name an alias, and fix links.
- **Contradictions and stale claims:** compare numbers and roles across pages (valuations, round sizes, who is CEO). Add an Open question on each affected page naming both sources; never pick a winner silently.
- **Index size:** if `wiki/index.md` exceeds ~300 lines, move the long tail (per-batch lists, minor pages) to `wiki/index-archive.md`. Check that no link is lost.
- **Relationships going cold:** people with `relationship: strong` or `warm` and `last_contact` older than 90 days. List them on `Home.md` under "Reconnect".
- **Relationship review:** low-confidence edges in `wiki/_graph/review.md`. Offer to confirm or drop the top 10.

## 3. Modes
- **Interactive** (a person asked): report findings with proposed fixes, apply what the user approves, then commit.
- **Scheduled** (the weekly task): apply only the safe fixes (validator ERRORs, index archiving, refreshing the Reconnect list). Write everything else to `wiki/lint-report.md` (overwrite it each week) so the user can review it on Monday.

## 4. Finish
Rebuild the graph (`python3 tools/build_graph.py --check`), append `## [YYYY-MM-DD] lint | <summary>` to `wiki/log.md`, and commit.
