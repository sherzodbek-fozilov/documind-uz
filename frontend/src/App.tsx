import { Menu, Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createClient } from "./api/client";
import type { ApiClient } from "./api/client";
import type { Corpus, DocumentInfo, OutlineSection, Passage } from "./api/types";
import { ChatWorkspace } from "./components/ChatWorkspace";
import type { Turn } from "./components/ChatWorkspace";
import { DocumentDetails } from "./components/DocumentDetails";
import { DocumentLibrary } from "./components/DocumentLibrary";
import { QueryComposer } from "./components/QueryComposer";
import { SearchHistory } from "./components/SearchHistory";
import { Sidebar } from "./components/Sidebar";
import type { View } from "./components/Sidebar";
import { SourceViewer } from "./components/SourceViewer";
import type { ViewerTarget } from "./components/SourceViewer";
import type { HealthState } from "./components/StatusBar";
import { WelcomeScreen } from "./components/WelcomeScreen";
import { useI18n } from "./i18n/context";
import { loadHistory, newId, saveHistory, upsertSession } from "./state/history";
import type { Session } from "./state/history";
import { useTheme } from "./state/theme";

type DoneTurn = Extract<Turn, { state: "done" }>;

const COLLAPSED_KEY = "documind.sidebar.collapsed";

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

const defaultClient = createClient();

export function App({ api = defaultClient }: { api?: ApiClient }) {
  const { t } = useI18n();
  const [theme, setTheme] = useTheme();
  const [health, setHealth] = useState<HealthState>({ state: "checking" });
  const [docs, setDocs] = useState<DocumentInfo[] | null>(null);
  const [docsError, setDocsError] = useState<unknown>(null);
  const [corpus, setCorpus] = useState<Corpus>("real");
  const [scope, setScope] = useState<string | null>(null);

  const [view, setView] = useState<View>("workspace");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sessionId, setSessionId] = useState(newId);
  const [history, setHistory] = useState<Session[]>(loadHistory);
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);
  const [detailsId, setDetailsId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [focusKey, setFocusKey] = useState(0);

  const inFlight = useRef<AbortController | null>(null);
  /** a turn was answered since the history was last updated */
  const answered = useRef(false);

  const loadDocs = useCallback(() => {
    setDocsError(null);
    setDocs(null);
    api.health().then((h) => setHealth({ state: "ok", health: h }),
                      () => setHealth({ state: "down" }));
    api.documents().then(setDocs, (e) => setDocsError(e));
  }, [api]);

  useEffect(() => {
    loadDocs();
    return () => inFlight.current?.abort();
  }, [loadDocs]);

  const corpusDocs = useMemo(() => (docs ?? []).filter((d) => d.corpus === corpus), [docs, corpus]);
  const byId = useMemo(() => new Map((docs ?? []).map((d) => [d.id, d])), [docs]);
  const titles = useMemo(() => Object.fromEntries((docs ?? []).map((d) => [d.id, d.title])), [docs]);

  const run = useCallback((question: string,
                           over?: { corpus: Corpus; documentId: string | null; replace?: string }) => {
    inFlight.current?.abort(); // a new question replaces the one in flight
    const ctrl = new AbortController();
    inFlight.current = ctrl;
    const turn: Turn = {
      id: over?.replace ?? newId(), question, state: "loading",
      corpus: over ? over.corpus : corpus, documentId: over ? over.documentId : scope,
    };
    setView("workspace");
    setTurns((prev) => {
      const rest = prev.filter((x) => x.state !== "loading" || x.id === turn.id);
      return rest.some((x) => x.id === turn.id) ? rest.map((x) => (x.id === turn.id ? turn : x))
                                                : [...rest, turn];
    });
    const settle = (next: Turn) => setTurns((prev) => prev.map((x) => (x.id === turn.id ? next : x)));
    api.ask({ question, corpus: turn.corpus, document_id: turn.documentId }, ctrl.signal).then(
      (response) => {
        if (ctrl.signal.aborted) return;
        answered.current = true;
        settle({ ...turn, state: "done", response });
      },
      (error) => {
        if (!ctrl.signal.aborted) settle({ ...turn, state: "error", error });
      },
    );
  }, [api, corpus, scope]);

  // keep the current session in the history once a question is answered
  useEffect(() => {
    if (!answered.current) return;
    answered.current = false;
    const done = turns.filter((x): x is DoneTurn => x.state === "done");
    if (done.length === 0) return;
    setHistory((prev) => upsertSession(prev, {
      id: sessionId, title: done[0].question, updatedAt: Date.now(),
      turns: done.map(({ id, question, corpus: c, documentId, response }) =>
        ({ id, question, corpus: c, documentId, response })),
    }));
  }, [turns, sessionId]);

  useEffect(() => saveHistory(history), [history]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      if (drawerOpen) setDrawerOpen(false);
      else if (viewer) setViewer(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen, viewer]);

  function newQuery() {
    inFlight.current?.abort();
    setTurns([]);
    setSessionId(newId());
    setViewer(null);
    setView("workspace");
    setDrawerOpen(false);
    setFocusKey((n) => n + 1);
  }

  function openSession(session: Session) {
    inFlight.current?.abort();
    setSessionId(session.id);
    setTurns(session.turns.map((x) => ({ ...x, state: "done" as const })));
    setViewer(null);
    setView("workspace");
    setDrawerOpen(false);
  }

  function deleteSession(id: string) {
    setHistory((prev) => prev.filter((s) => s.id !== id));
    if (id === sessionId) newQuery();
  }

  function clearHistory() {
    setHistory([]);
    setSessionId(newId()); // the thread on screen, if any, is a new session from now on
  }

  function changeCorpus(next: Corpus) {
    setCorpus(next);
    if (scope && byId.get(scope)?.corpus !== next) setScope(null);
    if (detailsId && byId.get(detailsId)?.corpus !== next) setDetailsId(null);
  }

  /** Limit the search to a document (and go and ask), or lift the limit. */
  function selectScope(id: string | null) {
    setScope(id);
    if (!id) return;
    const doc = byId.get(id);
    if (doc) setCorpus(doc.corpus);
    setView("workspace");
    setDrawerOpen(false);
    setFocusKey((n) => n + 1);
  }

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    try {
      window.localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
    } catch {
      // not remembered when storage is blocked
    }
  }

  const viewSource = (passage: Passage) =>
    setViewer({ documentId: passage.document_id, passage, startIdx: 0 });
  const openSection = (documentId: string, section: OutlineSection) =>
    setViewer({ documentId, passage: null, startIdx: section.idx });

  const loading = turns.some((x) => x.state === "loading");
  const detailsDoc = detailsId ? byId.get(detailsId) : undefined;
  const composer = (
    <QueryComposer corpus={corpus} onCorpusChange={changeCorpus} documents={corpusDocs}
                   scope={scope} onScopeChange={setScope} loading={loading} onAsk={run}
                   size={turns.length === 0 ? "large" : "default"} focusKey={focusKey} />
  );
  const shell = ["shell", collapsed ? "is-collapsed" : "", viewer ? "has-viewer" : ""]
    .filter(Boolean).join(" ");

  return (
    <div className={shell}>
      <Sidebar view={view} onNavigate={(v) => { setView(v); setDrawerOpen(false); }}
               onNewQuery={newQuery} collapsed={collapsed} onToggleCollapsed={toggleCollapsed}
               drawerOpen={drawerOpen} onCloseDrawer={() => setDrawerOpen(false)}
               health={health} theme={theme} onThemeChange={setTheme}>
        <SearchHistory sessions={history} activeId={turns.length ? sessionId : null}
                       onOpen={openSession} onDelete={deleteSession} onClear={clearHistory} />
      </Sidebar>
      {drawerOpen && <div className="backdrop backdrop--nav" onClick={() => setDrawerOpen(false)} />}

      <main className="main">
        <header className="topbar">
          <button type="button" className="icon-btn" aria-label={t("nav.open")}
                  aria-expanded={drawerOpen} onClick={() => setDrawerOpen(true)}>
            <Menu size={20} aria-hidden="true" />
          </button>
          <span className="topbar__name">DocuMind UZ</span>
          <button type="button" className="icon-btn" aria-label={t("nav.newQuery")} onClick={newQuery}>
            <Plus size={20} aria-hidden="true" />
          </button>
        </header>

        {view === "workspace" && turns.length === 0 && (
          <WelcomeScreen onExample={(q) => run(q)} disabled={loading}>{composer}</WelcomeScreen>
        )}
        {view === "workspace" && turns.length > 0 && (
          <ChatWorkspace turns={turns} titles={titles}
                         activeChunkId={viewer?.passage?.chunk_id ?? null}
                         onViewSource={viewSource}
                         onRetry={(x) => run(x.question, { corpus: x.corpus, documentId: x.documentId, replace: x.id })}
                         onSearchAll={(x) => run(x.question, { corpus: x.corpus, documentId: null })}>
            {composer}
          </ChatWorkspace>
        )}
        {view === "library" && (
          <div className="page">
            {detailsDoc ? (
              <DocumentDetails document={detailsDoc} api={api} selected={scope === detailsDoc.id}
                               onSelect={selectScope} onBack={() => setDetailsId(null)}
                               onOpenSection={(s) => openSection(detailsDoc.id, s)}
                               activeIdx={viewer && !viewer.passage && viewer.documentId === detailsDoc.id
                                 ? viewer.startIdx : null} />
            ) : (
              <DocumentLibrary documents={docs === null ? null : corpusDocs} error={docsError}
                               selectedId={scope} onSelect={selectScope} onRetry={loadDocs}
                               onOpenDetails={setDetailsId}
                               corpus={corpus} onCorpusChange={changeCorpus} />
            )}
          </div>
        )}
      </main>

      {viewer && (
        <>
          <div className="backdrop backdrop--viewer" onClick={() => setViewer(null)} />
          <SourceViewer target={viewer} document={byId.get(viewer.documentId)} api={api}
                        onClose={() => setViewer(null)} onSearchHere={selectScope} />
        </>
      )}
    </div>
  );
}
