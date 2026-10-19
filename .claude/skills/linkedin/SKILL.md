---
name: linkedin
description: Import a LinkedIn connections export into the VC Wiki and, optionally, enrich it by hand in the Harmonic app. Use for "import LinkedIn", "add my LinkedIn network", "I dropped Connections.csv", "enrich with Harmonic", "import Harmonic", or a newer export to refresh.
---

# LinkedIn (+ Harmonic enrichment)

LinkedIn has no API for your own connections, so the user exports them by hand (every six months or so is enough). The export has no location or career history; the user adds those by enriching the list **in the Harmonic app**. Never use a Harmonic connector/MCP tool for this, never scrape LinkedIn, and never log in on the user's behalf. Walk the user through one step at a time and wait for them.

## Step 1: download your connections from LinkedIn (about 10 minutes, mostly waiting)
Tell the user:
1. On linkedin.com, click **Me** (your photo, top right) → **Settings & Privacy**.
2. **Data privacy** → **Get a copy of your data**.
3. Choose **Want something in particular?**, tick only **Connections**, click **Request archive** (LinkedIn may ask for your password).
4. LinkedIn emails you a download link, usually within 10 minutes. Download the zip, open it, and drag `Connections.csv` into the vault's `raw/linkedin/` folder.
5. Say "import LinkedIn".

## Step 2: import into the wiki
1. Rename the file to `raw/linkedin/Connections-YYYY-MM-DD.csv` (today) if it has the default name.
2. Run `python3 tools/import_linkedin.py`. It tags existing person pages (`linkedin`, `linkedin_connection`, `connected_since`), creates light profiles in `wiki/people/network/` for founders and investors (`--all` for everyone; usually not worth it), and adds a "People you know (LinkedIn)" section to company and investor pages.
3. Run `python3 tools/build_graph.py --check` so "knows" edges and intro paths update.
4. Report: connections imported, pages tagged and created, companies where they know the most people. Then offer Step 3.

## Step 3 (optional): enrich in Harmonic
Explain the value first: where people are based, their current role and company stage, and who has founded before. It uses Harmonic credits (roughly one per person), so by default only founders and investors are enriched.

1. Run `python3 tools/import_linkedin.py --harmonic-upload` (add `--all` only if the user wants everyone). It writes `raw/linkedin/harmonic-upload.csv` (LinkedIn URL, name, company, position) and prints how many people are in it; tell the user that number, since it's roughly the credit cost.
2. Tell the user, in the Harmonic app (console.harmonic.ai):
   1. Create a new **people list** by **importing a CSV** (Harmonic matches people by LinkedIn URL). Upload `raw/linkedin/harmonic-upload.csv` from the vault folder (in Finder: Documents → vc-wiki → raw → linkedin) and map the column `linkedin_url` to LinkedIn URL.
   2. When the import finishes, open the list and use Harmonic's AI (an AI/custom column on the list, or the AI assistant on that list) with the **enrichment prompt** below.
   3. **Export** the result as CSV and drag it into `raw/linkedin/`, named `harmonic-enriched-YYYY-MM-DD.csv`.
   4. Say "import Harmonic".
   Harmonic's menus change; if a label doesn't match, the user should look for "import CSV", "add column / AI field" and "export" on the list.
3. Give the user this prompt to paste into Harmonic, exactly:

```text
For every person in this list, return one row with exactly these columns, in this order, as CSV with a header row:

linkedin_url, full_name, linkedin_headline, location_city, location_state, location_country, current_roles_clean, current_company, current_company_stage, current_company_funding_usd, current_company_country, prior_experience_clean, num_past_roles, prior_founder

Rules:
- linkedin_url: the person's LinkedIn profile URL exactly as in the list (this is the match key, never leave it empty).
- location_*: where the person is based now (city, state/region, country). Leave empty if unknown; do not guess from the company HQ.
- current_roles_clean: current roles as "Title @ Company", several separated by " | ".
- current_company_stage: Harmonic's stage for the main current company (e.g. PRE_SEED, SEED, SERIES_A, SERIES_B, SERIES_C, GROWTH, PUBLIC, EXITED), or empty.
- current_company_funding_usd: total funding raised in USD as a plain number, no symbols; 0 or empty if unknown.
- prior_experience_clean: previous roles, most recent first, as "Title @ Company (start-end)", separated by " | ", at most 8.
- num_past_roles: number of previous roles as an integer.
- prior_founder: 1 if they founded or co-founded a company before their current one, else 0.
- Use only Harmonic's data. No commentary, no extra columns, no notes outside the CSV.
```

4. When the file is in `raw/linkedin/`, run `python3 tools/import_linkedin.py --harmonic raw/linkedin/<file>.csv`. It matches rows to person pages by LinkedIn URL and adds `location`, `country`, `company_stage`, `company_funding_usd`, `prior_founder`, `harmonic_enriched` (it never overwrites values already on a page) plus a "Background (Harmonic)" section. If it says the file has no `linkedin_url` column, the export used different headers: ask the user to re-run the prompt, or map the columns by hand.
5. Run `python3 tools/build_graph.py --check`.

## Finish
Update `.wiki/state.json` (`linkedin_imported`: today), log the import (and enrichment), commit. Report what changed, e.g. "312 people now have a location: 40% in Germany, 25% in the US; 58 are repeat founders."
