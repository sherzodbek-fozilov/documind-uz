# Frontend

React + TypeScript (Vite) UI for the DocuMind UZ API: ask a question, see each passage
with the exact quote highlighted and a link to the source anchor.
The UI language can be
switched between Uzbek, Russian and English; questions are asked in Uzbek (Latin or
Cyrillic) or Russian.

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
| `src/lib/url.ts` | only http(s) URLs become links |
| `src/i18n/` | UI strings (uz, ru, en), language choice remembered in the browser |
| `src/components/` | ask form, result cards, document list, language switch, status line, error message |
| `src/App.tsx` | page state: health, documents, collection and scope, the question in flight |
| `src/test/` | handwritten sample passages and documents, test helpers |

## Status

Done:

- API: `POST /ask` returns each passage's full text, so the quote is highlighted inside it.
- Ask box (Uzbek or Russian questions; Enter asks, Shift+Enter adds a line), collection
  (real / synthetic) and an optional single-document scope.
- Result cards: passage with the exact quote highlighted, document title, article and
  chunk id, rank, link to the source anchor (or "no online source"); a quote that cannot
  be located is shown separately and not highlighted.
- Document list with language, edition, chunk count, source link and "search only here".
- UI language switch (uz, ru, en).
- Error and empty states: API unreachable, nothing ingested (503), unknown document
  (404), rejected question (422), server error, no passages, no documents; a status line
  from `GET /health`.
- Layout for phones and desktops, light and dark themes.
- Component tests on handwritten samples (no server, no LLM key).

Not done yet: serving the built bundle next to the API (Docker Compose, stage 6) and
showing the LLM-mode answer (`answer`, `citations`) when that mode is enabled.
