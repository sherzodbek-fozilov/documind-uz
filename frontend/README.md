# Frontend

React + TypeScript (Vite) UI for the DocuMind UZ API: ask a question, see each passage
with the exact quote highlighted and a link to the source anchor.

```bash
npm install        # npm 11+ (npm 10 cannot resolve vitest's optional peers)
npm run dev        # http://localhost:5173, /api/* is proxied to the API
npm test           # vitest, handwritten samples only
npm run typecheck
npm run build      # static files in dist/
```

Start the API first (`documind serve`, port 8000). The dev server forwards `/api/*` to
`http://127.0.0.1:8000`, so the API needs no CORS settings; set `DOCUMIND_API_URL` to
point the proxy elsewhere. A built bundle calls `VITE_API_BASE` (default `/api`), which
the reverse proxy in front of it must route to the API.

No LLM key is needed: the default extractive mode returns verbatim quotes.

| Path | Contents |
|---|---|
| `src/api/types.ts` | response types, mirroring `documind/api/schemas.py` |
| `src/api/client.ts` | `fetch` wrapper; maps failures to `ApiError` kinds for the UI |
| `src/lib/highlight.ts` | splits a passage around its exact quote; never highlights a non-exact span |
