# Cypher the product depends on

All queries live in `core/*.py`, are parameterised, and are executed through `Org.read` (`GRAPH.RO_QUERY`)
or `Org.write`. Every API response includes a `trace` with the exact queries that produced it, which is
what the UI's **Show Cypher** panel displays.

## How we write Cypher (and why)
- **Parameterised, always.** User and agent text only enters as `$params`. The only inlined values are a variable-length bound (validated as an integer from 1 to 4, because FalkorDB can't parameterise `*1..$n`) and labels from our own constants.
- **Reads are read-only.** All reads go through `GRAPH.RO_QUERY`, so the read path can't change memory.
- **The LLM never writes Cypher.** Agents call a fixed catalogue of tools (MCP), and each tool runs a query we wrote. That rules out invented labels, broken syntax and injection, which is the main failure mode of text-to-Cypher.
- **Idempotent writes.** `MERGE` for every entity and relationship. Re-running a save, a seed or a heartbeat doesn't create duplicates.
- **Batching with `UNWIND`.** Lists (libraries, lessons, candidate ids, components) are written and read in one round trip, not one query per item.
- **Vector and graph in one query.** `db.idx.vector.queryNodes` finds similar tasks, and the same query continues with `MATCH` (visibility, authorship) instead of fetching rows and joining in Python.
- **Indexes up front.** Range indexes on every lookup key and vector indexes on `Task` / `Question` are created idempotently at startup (`core/schema.py`).
- **Seeding is code, not a `.cypher` dump.** The demo org is rebuilt in about 20 seconds with `python -m seed.graphhq`, through the same functions the product uses. Data loss is a re-run, not a manual re-import.

## The five queries that matter most

**1. Hybrid recall, step 1: vector candidates, with visibility enforced in the graph** (`recall.vector_candidates`)
```cypher
CALL db.idx.vector.queryNodes('Task','embedding',$n,vecf32($emb)) YIELD node AS t, score
WITH t, 1 - score AS sim WHERE sim >= $min_sim
MATCH (s:Solution)-[:SOLVES]->(t)
MATCH (s)<-[:PRODUCED]-(:Session)<-[:RAN]-(a:Dev)-[:MEMBER_OF]->(at:Team)
MATCH (v:Dev {name:$viewer})-[:MEMBER_OF]->(vt:Team)
WHERE s.visibility = 'org' OR (s.visibility = 'team' AND at = vt) OR a = v
RETURN t.id AS task_id, t.text AS task_text, sim, s.id AS solution_id, s.status AS status
```

**2. Hybrid recall, step 2: walk past stale fixes to the newest one** (`recall.supersede_walk`)
```cypher
UNWIND $ids AS sid
MATCH (s0:Solution {id:sid})
OPTIONAL MATCH p = (newer:Solution)-[:SUPERSEDES*1..4]->(s0)
WITH s0, p ORDER BY length(p) DESC
WITH s0, collect(p)[0] AS longest
RETURN s0.id AS id,
       CASE WHEN longest IS NULL THEN [s0.id] ELSE reverse([n IN nodes(longest) | n.id]) END AS chain
```

**3. Change impact: who breaks if this component changes, and who is live on it right now** (`notice.impact` + `notice.live_sessions`)
```cypher
MATCH (c:Component {name:$c})
MATCH p = (dep:Component)-[:DEPENDS_ON*1..3]->(c)        // depth validated in code, then inlined (FalkorDB can't parameterise it)
WITH dep, p ORDER BY length(p)
WITH dep, collect(p)[0] AS p
OPTIONAL MATCH (t:Team)-[:OWNS]->(dep)
RETURN dep.name AS component, length(p) AS depth, [n IN nodes(p) | n.name] AS chain, t.name AS owner
```

**4. Routing a question to whoever is live on the relevant component** (`route.live_on_components`)
```cypher
UNWIND $comps AS cw MATCH (c:Component {name:cw.name})
MATCH (d:Dev)-[:RAN]->(s:Session {status:'live'})-[:TOUCHES]->(c)
WHERE s.last_seen >= $since AND d.name <> $asker
MATCH (d)-[:MEMBER_OF]->(t:Team)
RETURN d.name AS dev, t.name AS team, s.id AS sid, s.task AS task, c.name AS component, cw.w AS w
```

**5. Expertise authority: PageRank over who credits whom** (`brain.pagerank`)
```cypher
CALL algo.pageRank('Dev','CREDITS') YIELD node, score RETURN node.name AS dev, score
```
`CREDITS` edges are written whenever someone reuses your fix successfully or your answer resolves their question.
