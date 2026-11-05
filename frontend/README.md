# Frontend

React + TypeScript (Vite) UI for the DocuMind UZ API: ask a question, see each passage
with the exact quote highlighted and a link to the source anchor. **The UI itself is not
built yet**; see [Status and next steps](#status-and-next-steps).

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

## Status and next steps

Paused after the foundation; the pages and components are not written yet
(`src/main.tsx` renders a placeholder).

Done:

- API: `POST /ask` returns each passage's full text (`text`), so the quote can be
  highlighted inside it (`quote == text[quote_start:quote_end]`).
- Project setup: Vite, React 19, strict TypeScript, Vitest with jsdom; the dev server
  proxies `/api/*` to the FastAPI server.
- `src/api/`: types mirroring the API schemas and a `fetch` client that maps failures to
  `network`, `not_found` (404), `invalid` (422), `unavailable` (503, nothing ingested)
  or `server`.
- `src/lib/highlight.ts`: splits a passage around its exact quote (offsets first, then a
  verbatim search, otherwise no highlight) and trims long context without cutting the
  quote.
- 13 tests on handwritten uz-Latn, uz-Cyrl and ru samples.

Remaining (step 3, one commit):

- Ask box: question input in Uzbek or Russian, corpus choice (real / synthetic),
  optional single-document scope, submit with loading state; a new question cancels
  the previous request.
- Result cards: passage with the quote highlighted, document title, article
  (`section_title`) and chunk id, rank, and a link to the source anchor when there is
  one; the quote is shown on its own if it cannot be highlighted exactly.
- Document list from `GET /documents` (title, language, edition, number of chunks,
  source link), usable to restrict the question to one document.
- UI language switch (uz, ru, en) for all labels and messages, remembered in the
  browser.
- Clear states: API unreachable, nothing ingested (503), unknown document (404),
  invalid question (422), server error, no results, empty document list; status line
  from `GET /health`.
- Mobile-friendly layout and basic accessibility (labels, focus, contrast).
- Component tests with handwritten samples (no server, no LLM key).
