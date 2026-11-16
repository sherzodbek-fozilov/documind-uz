import { ArrowLeft, CalendarDays, Check, ChevronRight, ExternalLink, Search } from "lucide-react";
import { useEffect, useState } from "react";
import type { ApiClient } from "../api/client";
import type { DocumentInfo, DocumentOutline, OutlineSection } from "../api/types";
import { useI18n } from "../i18n/context";
import { kindKey, languageKey } from "../i18n/messages";
import { sectionLeaf, sectionParents } from "../lib/section";
import { safeHttpUrl } from "../lib/url";
import { ErrorMessage } from "./ErrorMessage";
import { SkeletonLines } from "./Skeleton";

type Load =
  | { state: "loading" }
  | { state: "ready"; outline: DocumentOutline }
  | { state: "error"; error: unknown };

interface Props {
  document: DocumentInfo;
  api: ApiClient;
  /** the search is restricted to this document */
  selected: boolean;
  onSelect: (id: string | null) => void;
  onBack: () => void;
  /** open a section in the source viewer */
  onOpenSection: (section: OutlineSection) => void;
  /** index of the section open in the viewer, if it belongs to this document */
  activeIdx?: number | null;
}

/** One document: what is known about it and its structure (the headings in reading
 * order, from the API). */
export function DocumentDetails(props: Props) {
  const { document: doc, api, selected, onSelect, onBack, onOpenSection, activeIdx } = props;
  const { t } = useI18n();
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [query, setQuery] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoad({ state: "loading" });
    api.outline(doc.id, ctrl.signal).then(
      (outline) => { if (!ctrl.signal.aborted) setLoad({ state: "ready", outline }); },
      (error) => { if (!ctrl.signal.aborted) setLoad({ state: "error", error }); },
    );
    return () => ctrl.abort();
  }, [api, doc.id, attempt]);

  const source = safeHttpUrl(doc.source);
  const langKey = languageKey(doc.language);
  const typeKey = doc.kind ? kindKey(doc.kind) : null;
  const needle = query.trim().toLocaleLowerCase();
  const sections = load.state === "ready"
    ? load.outline.sections.filter((s) => !needle || (s.title ?? "").toLocaleLowerCase().includes(needle))
    : [];

  return (
    <section className="details" aria-labelledby="details-heading">
      <button type="button" className="btn btn--ghost btn--sm details__back" onClick={onBack}>
        <ArrowLeft size={15} aria-hidden="true" />
        <span>{t("docs.back")}</span>
      </button>

      <header className="details__head">
        <h2 id="details-heading" className="page-head__title" lang={doc.language}>{doc.title}</h2>
        <p className="doc__meta">
          <span className="badge">{langKey ? t(langKey) : doc.language}</span>
          {doc.kind && <span className="badge">{typeKey ? t(typeKey) : doc.kind}</span>}
          {doc.is_synthetic && <span className="badge badge--warn">{t("docs.synthetic")}</span>}
        </p>
        <p className="doc__facts">
          {doc.edition && (
            <span><CalendarDays size={14} aria-hidden="true" />{t("docs.edition", { edition: doc.edition })}</span>
          )}
          <span>{t("docs.chunks", { n: doc.n_chunks })}</span>
          {load.state === "ready" && <span>{t("docs.sections", { n: load.outline.sections.length })}</span>}
        </p>
        <div className="doc__actions">
          <button type="button" aria-pressed={selected}
                  className={selected ? "btn btn--primary btn--sm" : "btn btn--soft btn--sm"}
                  onClick={() => onSelect(selected ? null : doc.id)}>
            {selected ? <Check size={15} aria-hidden="true" /> : <Search size={15} aria-hidden="true" />}
            <span>{selected ? t("docs.selected") : t("docs.askHere")}</span>
          </button>
          {source && (
            <a className="doc__source" href={source} target="_blank" rel="noopener noreferrer">
              {t("docs.source")}<ExternalLink size={14} aria-hidden="true" />
            </a>
          )}
        </div>
      </header>

      <div className="outline">
        <div className="outline__head">
          <h3 className="eyebrow">{t("docs.outline")}</h3>
          {load.state === "ready" && load.outline.sections.length > 8 && (
            <label className="search-field search-field--sm">
              <Search size={15} aria-hidden="true" />
              <span className="visually-hidden">{t("docs.outlineSearch")}</span>
              <input type="search" value={query} placeholder={t("docs.outlineSearch")}
                     onChange={(e) => setQuery(e.target.value)} />
            </label>
          )}
        </div>

        {load.state === "loading" && (
          <div role="status">
            <span className="visually-hidden">{t("docs.outlineLoading")}</span>
            <SkeletonLines widths={["60%", "74%", "52%", "68%", "57%", "71%"]} />
          </div>
        )}
        {load.state === "error" && (
          <ErrorMessage error={load.error} onRetry={() => setAttempt((n) => n + 1)} />
        )}
        {load.state === "ready" && sections.length === 0 && (
          <p className="empty" role="status">{t("docs.outlineEmpty")}</p>
        )}
        {load.state === "ready" && sections.length > 0 && (
          <ol className="outline__list" lang={doc.language}>
            {sections.map((s) => {
              const parents = sectionParents(s.title);
              return (
                <li key={s.chunk_id}>
                  {parents.length > 0 && <p className="outline__group">{parents.join(" · ")}</p>}
                  <button type="button"
                          className={s.idx === activeIdx ? "outline__item is-active" : "outline__item"}
                          onClick={() => onOpenSection(s)}>
                    <span>{sectionLeaf(s.title) ?? t("docs.untitled")}</span>
                    <ChevronRight size={15} aria-hidden="true" />
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </section>
  );
}
