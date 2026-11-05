import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createClient } from "./api/client";
import type { ApiClient } from "./api/client";
import type { AskResponse, Corpus, DocumentInfo } from "./api/types";
import { AskForm } from "./components/AskForm";
import { DocumentList } from "./components/DocumentList";
import { ErrorMessage } from "./components/ErrorMessage";
import { LanguageSwitch } from "./components/LanguageSwitch";
import { ResultList } from "./components/ResultList";
import { StatusBar } from "./components/StatusBar";
import type { HealthState } from "./components/StatusBar";
import { useI18n } from "./i18n/context";

type AskState =
  | { state: "idle" }
  | { state: "loading"; question: string }
  | { state: "done"; response: AskResponse }
  | { state: "error"; question: string; error: unknown };

const defaultClient = createClient();

export function App({ api = defaultClient }: { api?: ApiClient }) {
  const { t } = useI18n();
  const [health, setHealth] = useState<HealthState>({ state: "checking" });
  const [docs, setDocs] = useState<DocumentInfo[] | null>(null);
  const [docsError, setDocsError] = useState<unknown>(null);
  const [corpus, setCorpus] = useState<Corpus>("real");
  const [scope, setScope] = useState<string | null>(null);
  const [ask, setAsk] = useState<AskState>({ state: "idle" });
  const inFlight = useRef<AbortController | null>(null);

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
  const titles = useMemo(() => Object.fromEntries((docs ?? []).map((d) => [d.id, d.title])), [docs]);

  const run = useCallback((question: string) => {
    inFlight.current?.abort(); // a new question replaces the one in flight
    const ctrl = new AbortController();
    inFlight.current = ctrl;
    setAsk({ state: "loading", question });
    api.ask({ question, corpus, document_id: scope }, ctrl.signal).then(
      (response) => { if (!ctrl.signal.aborted) setAsk({ state: "done", response }); },
      (error) => {
        if (ctrl.signal.aborted) return;
        setAsk({ state: "error", question, error });
      },
    );
  }, [api, corpus, scope]);

  function changeCorpus(next: Corpus) {
    setCorpus(next);
    if (scope && !(docs ?? []).some((d) => d.id === scope && d.corpus === next)) setScope(null);
  }

  return (
    <div className="app">
      <header className="app__header">
        <div className="brand">
          <h1 className="brand__name">DocuMind UZ</h1>
          <p className="brand__tagline muted">{t("app.tagline")}</p>
        </div>
        <div className="app__tools">
          <LanguageSwitch />
          <StatusBar status={health} />
        </div>
      </header>

      <main className="app__main">
        <div className="app__primary">
          <AskForm corpus={corpus} onCorpusChange={changeCorpus} documents={corpusDocs}
                   scope={scope} onScopeChange={setScope} loading={ask.state === "loading"}
                   onAsk={run} />
          <div className="app__results" aria-live="polite">
            {ask.state === "idle" && <p className="empty">{t("results.idle")}</p>}
            {ask.state === "loading" && <p className="muted" role="status">{t("ask.loading")}</p>}
            {ask.state === "error" && (
              <ErrorMessage error={ask.error} onRetry={() => run(ask.question)} />
            )}
            {ask.state === "done" && <ResultList response={ask.response} titles={titles} />}
          </div>
        </div>
        <aside className="app__aside">
          <DocumentList documents={docs === null ? null : corpusDocs} error={docsError}
                        selectedId={scope} onSelect={setScope} onRetry={loadDocs} />
        </aside>
      </main>
    </div>
  );
}
