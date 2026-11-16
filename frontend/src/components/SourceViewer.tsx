import { ChevronDown, ChevronUp, ExternalLink, Search, X } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ApiClient } from "../api/client";
import type { DocumentInfo, DocumentPassage, Passage } from "../api/types";
import { useI18n } from "../i18n/context";
import { languageKey } from "../i18n/messages";
import { splitAroundQuote } from "../lib/highlight";
import { sectionParts } from "../lib/section";
import { safeHttpUrl } from "../lib/url";
import { CopyButton } from "./CopyButton";
import { ErrorMessage } from "./ErrorMessage";
import { SkeletonLines } from "./Skeleton";

/** What the viewer shows: a cited passage (highlighted, with the text around it), or a
 * place in a document picked from its structure. */
export interface ViewerTarget {
  documentId: string;
  /** the cited passage; null when opened from the document structure */
  passage: Passage | null;
  /** index of the first passage to show, when there is no cited passage */
  startIdx: number;
}

const WINDOW = 7; // passages loaded at first
const STEP = 6; // passages added by "show earlier / later"

type Load =
  | { state: "loading" }
  | { state: "ready"; passages: DocumentPassage[]; total: number }
  /** the server has no document text endpoint: only the cited passage can be shown */
  | { state: "fallback" }
  | { state: "error"; error: unknown };

interface Props {
  target: ViewerTarget;
  /** the document, when it is in the loaded list */
  document?: DocumentInfo;
  api: ApiClient;
  onClose: () => void;
  /** limit the search to this document */
  onSearchHere?: (documentId: string) => void;
}

function hostOf(url: string): string {
  return new URL(url).hostname.replace(/^www\./, "");
}

export function SourceViewer({ target, document: doc, api, onClose, onSearchHere }: Props) {
  const { t } = useI18n();
  const { documentId, passage, startIdx } = target;
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [more, setMore] = useState<"earlier" | "later" | null>(null);
  const [attempt, setAttempt] = useState(0);
  const scroller = useRef<HTMLDivElement>(null);
  const focus = useRef<HTMLElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  /** scroll height before earlier text was added, to keep the reading position */
  const heightBefore = useRef<number | null>(null);
  const focusChunk = passage?.chunk_id ?? null;

  useEffect(() => {
    const ctrl = new AbortController();
    setLoad({ state: "loading" });
    const range = focusChunk ? { around: focusChunk, limit: WINDOW } : { start: startIdx, limit: WINDOW };
    api.passages(documentId, range, ctrl.signal).then(
      (r) => { if (!ctrl.signal.aborted) setLoad({ state: "ready", passages: r.passages, total: r.total }); },
      (error) => {
        if (ctrl.signal.aborted) return;
        setLoad(focusChunk ? { state: "fallback" } : { state: "error", error });
      },
    );
    return () => ctrl.abort();
  }, [api, documentId, focusChunk, startIdx, attempt]);

  // the viewer opens over the page on small screens: move the focus into it
  useEffect(() => {
    closeBtn.current?.focus();
  }, [documentId, focusChunk, startIdx]);

  // bring the quote (or the chosen section) into view once the text is there
  const ready = load.state === "ready" || load.state === "fallback";
  useEffect(() => {
    if (ready) focus.current?.scrollIntoView?.({ block: "center" });
  }, [ready, documentId, focusChunk, startIdx]);

  useLayoutEffect(() => {
    const el = scroller.current;
    if (el && heightBefore.current !== null) {
      el.scrollTop += el.scrollHeight - heightBefore.current;
      heightBefore.current = null;
    }
  });

  const extend = useCallback((direction: "earlier" | "later") => {
    if (load.state !== "ready" || more || load.passages.length === 0) return;
    const first = load.passages[0].idx;
    const lastIdx = load.passages[load.passages.length - 1].idx;
    const start = direction === "earlier" ? Math.max(first - STEP, 0) : lastIdx + 1;
    const limit = direction === "earlier" ? first - start : STEP;
    setMore(direction);
    api.passages(documentId, { start, limit }).then(
      (r) => {
        if (direction === "earlier") heightBefore.current = scroller.current?.scrollHeight ?? null;
        setLoad((cur) => cur.state !== "ready" ? cur : {
          ...cur,
          total: r.total,
          passages: direction === "earlier" ? [...r.passages, ...cur.passages]
                                            : [...cur.passages, ...r.passages],
        });
        setMore(null);
      },
      (error) => {
        setLoad({ state: "error", error });
        setMore(null);
      },
    );
  }, [api, documentId, load, more]);

  const link = safeHttpUrl(passage?.link) ?? safeHttpUrl(doc?.source);
  const title = doc?.title ?? documentId;
  const shown = load.state === "ready" ? load.passages : [];
  const section = passage?.section_title
    ?? shown.find((p) => p.idx === startIdx)?.section_title ?? shown[0]?.section_title ?? null;
  const crumbs = sectionParts(section);
  const lang = passage?.language ?? doc?.language;
  const langKey = doc ? languageKey(doc.language) : null;

  function renderPassage(p: DocumentPassage) {
    const cited = passage !== null && p.chunk_id === passage.chunk_id;
    if (!cited || passage === null) {
      const start = passage === null && p.idx === startIdx;
      return (
        <section key={p.chunk_id} className="viewer__passage"
                 ref={start ? focus : undefined}>
          {p.text}
        </section>
      );
    }
    const h = splitAroundQuote(p.text, passage.quote, passage.quote_start, passage.quote_end);
    return (
      <section key={p.chunk_id} className="viewer__passage is-cited" aria-label={t("viewer.quoted")}>
        {h.exact ? (
          <>{h.before}<mark className="quote" ref={focus}>{h.quote}</mark>{h.after}</>
        ) : (
          <span ref={focus}>{p.text}</span>
        )}
      </section>
    );
  }

  return (
    <aside className="viewer" aria-label={t("viewer.title")}>
      <header className="viewer__head">
        <div className="viewer__titles">
          <p className="eyebrow">{t("viewer.title")}</p>
          <h2 className="viewer__title">{title}</h2>
        </div>
        <button type="button" ref={closeBtn} className="icon-btn" aria-label={t("viewer.close")}
                onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
      </header>

      <div className="viewer__meta">
        {crumbs.length > 0 && (
          <ol className="crumbs" lang={lang}>
            {crumbs.map((c, i) => (
              <li key={i} className={i === crumbs.length - 1 ? "crumbs__leaf" : undefined}>{c}</li>
            ))}
          </ol>
        )}
        <div className="viewer__facts">
          {doc && <span className="badge">{langKey ? t(langKey) : doc.language}</span>}
          {doc?.edition && <span className="badge">{t("docs.edition", { edition: doc.edition })}</span>}
          {load.state === "ready" && shown.length > 0 && (
            <span className="viewer__range">
              {t("viewer.range", { from: shown[0].idx + 1, to: shown[shown.length - 1].idx + 1, total: load.total })}
            </span>
          )}
        </div>
        <div className="viewer__actions">
          {link && (
            <a className="btn btn--soft btn--sm" href={link} target="_blank" rel="noopener noreferrer">
              <ExternalLink size={15} aria-hidden="true" />
              <span>{t("result.source")} · {hostOf(link)}</span>
            </a>
          )}
          {onSearchHere && doc && (
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => onSearchHere(documentId)}>
              <Search size={15} aria-hidden="true" />
              <span>{t("docs.askHere")}</span>
            </button>
          )}
          {passage && <CopyButton getText={() => passage.quote} label={t("result.copyQuote")} />}
        </div>
      </div>

      <div className="viewer__body" ref={scroller} tabIndex={0} lang={lang}>
        {load.state === "loading" && (
          <div role="status">
            <span className="visually-hidden">{t("viewer.loading")}</span>
            <SkeletonLines widths={["55%", "97%", "92%", "95%", "71%", "0", "48%", "96%", "90%", "64%"]} />
          </div>
        )}

        {load.state === "error" && (
          <ErrorMessage error={load.error} onRetry={() => setAttempt((n) => n + 1)} />
        )}

        {load.state === "fallback" && passage && (
          <>
            <p className="viewer__notice" role="note">{t("viewer.fallback")}</p>
            {renderPassage({ idx: 0, chunk_id: passage.chunk_id, section_title: passage.section_title,
                             char_start: 0, char_end: passage.text.length, text: passage.text })}
          </>
        )}

        {load.state === "ready" && shown.length > 0 && (
          <>
            {shown[0].idx > 0 ? (
              <button type="button" className="viewer__more" disabled={more !== null}
                      onClick={() => extend("earlier")}>
                <ChevronUp size={15} aria-hidden="true" />{t("viewer.earlier")}
              </button>
            ) : (
              <p className="viewer__edge">{t("viewer.start")}</p>
            )}
            {shown.map(renderPassage)}
            {shown[shown.length - 1].idx < load.total - 1 ? (
              <button type="button" className="viewer__more" disabled={more !== null}
                      onClick={() => extend("later")}>
                <ChevronDown size={15} aria-hidden="true" />{t("viewer.later")}
              </button>
            ) : (
              <p className="viewer__edge">{t("viewer.end")}</p>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
