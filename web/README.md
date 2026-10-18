# Mycelium web

Next.js 16 app: live org view (force graph + live event stream), recall and ask-the-org, vector-vs-Mycelium comparison,
agent-to-agent threads, company brain, lineage. Talks to the Mycelium API (`NEXT_PUBLIC_API_URL`, defaults to the
deployed demo API).

```bash
npm install
npm run dev -- -p 3001     # http://localhost:3001
# against a local API:
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev -- -p 3001
```
