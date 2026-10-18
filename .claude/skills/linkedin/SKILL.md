---
name: linkedin
description: Import a LinkedIn connections export into the VC Wiki. Use for "import LinkedIn", "add my LinkedIn network", "I dropped Connections.csv", or a newer export to refresh. Optionally enriches founders and investors with location and background via the Harmonic connector.
---

# LinkedIn import

LinkedIn has no API for your own connections, so the user exports them by hand (about every six months is enough).

## If there's no CSV yet
Tell the user: "LinkedIn → Me → Settings & Privacy → Data privacy → Get a copy of your data → choose **Want something in particular?** → tick only **Connections** → Request archive. You'll get an email within about 10 minutes. Unzip it and drop `Connections.csv` into `raw/linkedin/`." Never scrape LinkedIn or log in on the user's behalf.

## Import
1. Rename the file to `raw/linkedin/Connections-YYYY-MM-DD.csv` (today's date) if it has the default name.
2. Run `python3 tools/import_linkedin.py`. It:
   - tags existing person pages with `linkedin`, `linkedin_connection: true`, `connected_since`;
   - creates light profiles in `wiki/people/network/` for founders and investors (add `--all` to include everyone; usually not worth it);
   - adds a "People you know (LinkedIn)" section to every company and investor page where you know someone.
3. Run `python3 tools/build_graph.py --check` so the "knows" edges and intro paths update.

## Optional: Harmonic enrichment
LinkedIn's export has no location or career history. If a Harmonic tool is available, enrich the founder and investor profiles in `wiki/people/network/` (location city/country, current role, company stage and funding, prior roles):
- Tell the user it uses Harmonic credits, and give the count before starting.
- Work in batches of 50. Write the fields into each page's frontmatter (`location`, `country`, `company_stage`, `prior_founder`) and a short "Background" section. Leave existing content alone.
- If enrichment fails or the tool isn't available, skip it: the import is still useful.

## Finish
Update `.wiki/state.json` (`linkedin_imported`: today), log the import, commit. Report: connections imported, pages tagged and created, and the companies where you know the most people.
