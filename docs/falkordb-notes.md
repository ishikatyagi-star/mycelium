# FalkorDB notes from building Mycelium (feedback for the FalkorDB team)

These are things we hit while building, each with what we did about it. We hope they save someone an hour.

## What worked really well
- **One engine for vectors and the graph.** The vector index on `Task.embedding` gives us "similar problems". The next `MATCH` in the *same query* applies visibility rules and walks `SOLVES`, `PRODUCED` and `MEMBER_OF`. There's no second database and no sync job.
- **`GRAPH.COPY` makes per-visitor sandboxes trivial.** `POST /api/sandbox` clones the whole demo org in one command. Every judge gets a private, writable copy of a company with live data.
- **One graph per tenant.** `org_<slug>` graphs are cheap, and isolation is structural, not a `WHERE tenant = ?` you can forget. There's a test for it.
- **`GRAPH.RO_QUERY`** lets us guarantee the read path can never mutate memory.
- **`algo.pageRank(label, relType)`** made "who knows X" a single call over our `CREDITS` edges.
- **Speed:** hybrid recall (vector KNN plus 3 graph queries) runs at about 3 ms p50 locally. 50 concurrent agents through our API produced 0 errors.

## Gotchas (each with a workaround)
1. **The `falkordb/falkordb:latest` image is v4.22.1** as of 2026-10-15. The FalkorDB 6.0 announcement suggests `docker pull falkordb/falkordb:latest`, but the Rust engine was only on `edge-rs` when we checked. We pinned v4.22.1 by digest. It's the same engine line as Cloud free (4.22.0), and our suite passes on both.
2. **`db.idx.vector.queryNodes` returns a distance, not a similarity.** With `similarityFunction:'cosine'`, `score` is `1 - cosine`, so `0` means identical. We use `1 - score AS sim` everywhere.
3. **`shortestPath` must be in `WITH` or `RETURN`.** `MATCH p = shortestPath(...)` errors with "FalkorDB currently only supports shortestPaths in WITH or RETURN clauses".
4. **`RO_QUERY` on a graph that doesn't exist yet** raises `Invalid graph operation on empty key`. Our `Org.read` treats that as "no rows", so a brand-new org can be read before its first write.
5. **Variable-length bounds can't be parameters** (`-[:DEPENDS_ON*1..$depth]->`). We validate the depth as an integer from 1 to 4 in code, then inline it.
6. **Cloud free:** use a plain connection (TLS hangs) and set `socket_timeout`, because the Python client has no default. Our host was the `r-<id>.instance-...cloud:<port>` endpoint; the `node-f-0...` name is internal.
7. **Cross-region latency adds up for chatty agent loops.** Our API started in Railway's US region while Cloud was in ap-south-1. We moved it to Singapore, where each query takes about 56 ms. Co-locate the app and the database region.
8. **FalkorDB Cloud free doesn't grant `PUBLISH`/`SUBSCRIBE`** (`User falkordb has no permissions to run the 'publish' command`). Our first event bus used Redis pub/sub on the FalkorDB instance, which works on Docker. On Cloud we fan events out inside the API process instead (every agent talks to the API anyway).
9. **The default `TIMEOUT 1000` (ms)** on the server module is fine for our queries, but variable-length walks over dense graphs could hit it. We cap depth at 4.

## Things we'd love
- `algo.betweenness` with a `direction: 'both'` option. The community sponsor-feedback notes describe the workaround, which we avoided by using PageRank.
- A documented way to run the 6.0 engine via Docker (a stable tag) and a Cloud rollout date. We'd have liked to run our suite on 6.0 too.
