---
name: ask
description: Answer questions from the VC Wiki, including multi-hop relationship questions via the SQLite graph. Use for "who do I know at X", "intro path to", "who invests with", "what do we know about", "compare", "which founders", and any question about companies, people, investors or sectors in the wiki.
---

# Ask

1. Read `wiki/index.md`, then the candidate pages. Answer from the wiki first and say what it doesn't know. Only go to `raw/` when a page lacks the detail.
2. For questions that chain relationships (intro paths, co-investors, who knows whom at a customer), query `wiki/_graph/graph.db` with `sqlite3`. If the file is missing, run `python3 tools/build_graph.py` first.
3. Cite pages as `[[wikilinks]]`. For every relationship you rely on, show its `evidence` and `page`, and its status if not `confirmed`.
4. If the answer is a comparison, analysis or map worth keeping, offer to save it to `wiki/analyses/`.
5. Append `## [YYYY-MM-DD] query | <question>` to `wiki/log.md`.

## Graph basics
- `nodes(id, kind, status, sector, location, has_page, relationship, last_contact)`
- `edges(src, rel, dst, status, confidence, round, date, strategic, weight, evidence, page, origin)`
- The owner is the node named in `.wiki/state.json` ("owner"). `knows` edges run owner → person, with `weight` 3 = strong, 2 = warm, 1 = met or LinkedIn only.
- Prefer `status='confirmed'`. Mention `potential` edges as such.

## Recipes

**Who do I know at a company (directly)?**
```sql
SELECT k.dst AS person, k.weight, w.dst AS org FROM edges k
JOIN edges w ON w.src=k.dst AND w.rel='works_at'
WHERE k.src=:owner AND k.rel='knows' AND w.dst=:company ORDER BY k.weight DESC;
```

**Warm paths to a company (direct, or via its investors and partners):**
```sql
SELECT r.rel AS via_rel, r.dst AS via_org, k.dst AS my_contact, k.weight FROM edges r
JOIN edges w ON w.dst=r.dst AND w.rel='works_at'
JOIN edges k ON k.dst=w.src AND k.rel='knows' AND k.src=:owner
WHERE r.src=:company AND r.rel IN ('invested_in_by','partners_with','customer','supplier') AND r.status='confirmed'
ORDER BY k.weight DESC;
```

**Co-investors of a fund, and how many people I know at each:**
```sql
SELECT b.dst AS co_investor, count(DISTINCT a.src) AS shared, group_concat(DISTINCT a.src) AS companies
FROM edges a JOIN edges b ON a.src=b.src AND b.rel='invested_in_by' AND b.dst<>:fund
WHERE a.rel='invested_in_by' AND a.dst=:fund GROUP BY b.dst ORDER BY shared DESC;
```

**Portfolio companies' customers and partners where I know someone (commercial intros):**
```sql
SELECT DISTINCT p.id AS portco, r.rel, r.dst AS counterparty, k.dst AS my_contact FROM nodes p
JOIN edges r ON r.src=p.id AND r.rel IN ('customer','partners_with')
JOIN edges w ON w.dst=r.dst AND w.rel='works_at'
JOIN edges k ON k.dst=w.src AND k.rel='knows' AND k.src=:owner
WHERE p.status='portfolio';
```

**Shortest chain between two entities (any relationship, up to 4 hops):**
```sql
WITH RECURSIVE walk(node, path, depth) AS (
  SELECT :start, :start, 0
  UNION ALL
  SELECT CASE WHEN e.src=walk.node THEN e.dst ELSE e.src END,
         walk.path || ' -[' || e.rel || ']- ' || CASE WHEN e.src=walk.node THEN e.dst ELSE e.src END,
         depth+1
  FROM walk JOIN edges e ON (e.src=walk.node OR e.dst=walk.node) AND e.status='confirmed'
  WHERE depth < 4 AND instr(walk.path, CASE WHEN e.src=walk.node THEN e.dst ELSE e.src END)=0)
SELECT DISTINCT path, depth FROM walk WHERE node=:end ORDER BY depth LIMIT 5;
```

**Competitive map of a sector:**
```sql
SELECT e.src, e.rel, e.dst FROM edges e JOIN nodes n ON n.id=e.src
WHERE n.sector=:sector AND e.rel IN ('competes_with','comparable_to') AND e.confidence='high';
```
