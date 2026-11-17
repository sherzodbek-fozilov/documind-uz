import { CalendarDays, Check, ExternalLink, ListTree, Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { DocumentInfo } from "../api/types";
import { useI18n } from "../i18n/context";
import { kindKey, languageKey } from "../i18n/messages";
import { safeHttpUrl } from "../lib/url";
import { ErrorMessage } from "./ErrorMessage";
import { Select } from "./Select";
import { SkeletonLines } from "./Skeleton";

interface Props {
  /** documents of the current collection; null while loading */
  documents: DocumentInfo[] | null;
  error?: unknown;
  /** the document the search is restricted to, if any */
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onRetry?: () => void;
  /** open the structure of a document; no button without it */
  onOpenDetails?: (id: string) => void;
}

const ALL = "__all__"; // "no filter" (Radix has no empty value)

function unique(values: (string | null | undefined)[]): string[] {
  return [...new Set(values.filter((v): v is string => Boolean(v)))].sort();
}

/** The documents of the current collection, with a title search and filters. Filter
 * options come from the documents themselves; a filter with one option is not shown. */
export function DocumentLibrary(props: Props) {
  const { documents, error, selectedId, onSelect, onRetry, onOpenDetails } = props;
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState("");
  const [kind, setKind] = useState("");

  const languages = useMemo(() => unique((documents ?? []).map((d) => d.language)), [documents]);
  const kinds = useMemo(() => unique((documents ?? []).map((d) => d.kind)), [documents]);
  // a filter value that the current collection does not have is ignored
  const lang = languages.includes(language) ? language : "";
  const type = kinds.includes(kind) ? kind : "";
  const needle = query.trim().toLocaleLowerCase();
  const shown = (documents ?? []).filter((d) =>
    (!needle || d.title.toLocaleLowerCase().includes(needle))
    && (!lang || d.language === lang) && (!type || d.kind === type));
  const filtered = Boolean(needle || lang || type);

  const languageName = (code: string) => {
    const key = languageKey(code);
    return key ? t(key) : code;
  };
  const kindName = (k: string) => {
    const key = kindKey(k);
    return key ? t(key) : k;
  };

  let body;
  if (error) body = <ErrorMessage error={error} onRetry={onRetry} />;
  else if (documents === null) {
    body = (
      <div role="status">
        <span className="visually-hidden">{t("docs.loading")}</span>
        <div className="docs__grid" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="doc doc--skeleton"><SkeletonLines widths={["82%", "45%", "0", "60%"]} /></div>
          ))}
        </div>
      </div>
    );
  } else if (documents.length === 0) body = <p className="empty" role="status">{t("docs.empty")}</p>;
  else {
    body = (
      <>
        <div className="docs__tools">
          <label className="search-field">
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">{t("docs.search")}</span>
            <input type="search" value={query} placeholder={t("docs.search")}
                   onChange={(e) => setQuery(e.target.value)} />
          </label>
          {languages.length > 1 && (
            <div className="field">
              <span aria-hidden="true">{t("docs.filterLang")}</span>
              <Select label={t("docs.filterLang")} value={lang || ALL} align="end"
                      onChange={(v) => setLanguage(v === ALL ? "" : v)}
                      options={[{ value: ALL, label: t("docs.all") },
                                ...languages.map((l) => ({ value: l, label: languageName(l) }))]} />
            </div>
          )}
          {kinds.length > 1 && (
            <div className="field">
              <span aria-hidden="true">{t("docs.filterKind")}</span>
              <Select label={t("docs.filterKind")} value={type || ALL} align="end"
                      onChange={(v) => setKind(v === ALL ? "" : v)}
                      options={[{ value: ALL, label: t("docs.all") },
                                ...kinds.map((k) => ({ value: k, label: kindName(k) }))]} />
            </div>
          )}
        </div>

        {shown.length === 0 ? (
          <div className="empty" role="status">
            <p>{t("docs.noMatch")}</p>
            {filtered && (
              <button type="button" className="btn btn--soft btn--sm"
                      onClick={() => { setQuery(""); setLanguage(""); setKind(""); }}>
                {t("docs.reset")}
              </button>
            )}
          </div>
        ) : (
          <ul className="docs__grid">
            {shown.map((d) => {
              const selected = d.id === selectedId;
              const source = safeHttpUrl(d.source);
              return (
                <li key={d.id} className={selected ? "doc is-selected" : "doc"}>
                  <p className="doc__title" lang={d.language}>{d.title}</p>
                  <p className="doc__meta">
                    <span className="badge">{languageName(d.language)}</span>
                    {d.kind && <span className="badge">{kindName(d.kind)}</span>}
                    {d.is_synthetic && <span className="badge badge--warn">{t("docs.synthetic")}</span>}
                  </p>
                  <p className="doc__facts">
                    {d.edition && (
                      <span><CalendarDays size={14} aria-hidden="true" />{t("docs.edition", { edition: d.edition })}</span>
                    )}
                    <span>{t("docs.chunks", { n: d.n_chunks })}</span>
                  </p>
                  <div className="doc__actions">
                    <button type="button" aria-pressed={selected}
                            className={selected ? "btn btn--primary btn--sm" : "btn btn--soft btn--sm"}
                            onClick={() => onSelect(selected ? null : d.id)}>
                      {selected ? <Check size={15} aria-hidden="true" /> : <Search size={15} aria-hidden="true" />}
                      <span>{selected ? t("docs.selected") : t("docs.askHere")}</span>
                    </button>
                    {onOpenDetails && (
                      <button type="button" className="btn btn--ghost btn--sm" onClick={() => onOpenDetails(d.id)}>
                        <ListTree size={15} aria-hidden="true" />
                        <span>{t("docs.structure")}</span>
                      </button>
                    )}
                    {source && (
                      <a className="doc__source" href={source} target="_blank" rel="noopener noreferrer">
                        {t("docs.source")}<ExternalLink size={14} aria-hidden="true" />
                      </a>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </>
    );
  }
  return (
    <section className="docs" aria-labelledby="docs-heading">
      <header className="page-head">
        <h2 id="docs-heading" className="page-head__title">{t("docs.heading")}</h2>
        <p className="page-head__sub">{t("docs.subtitle")}</p>
      </header>
      {body}
    </section>
  );
}
