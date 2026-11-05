import type { DocumentInfo } from "../api/types";
import { useI18n } from "../i18n/context";
import { safeHttpUrl } from "../lib/url";
import { ErrorMessage } from "./ErrorMessage";

interface Props {
  /** null while loading */
  documents: DocumentInfo[] | null;
  error?: unknown;
  /** the document the search is restricted to, if any */
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onRetry?: () => void;
}

export function DocumentList({ documents, error, selectedId, onSelect, onRetry }: Props) {
  const { t } = useI18n();
  let body;
  if (error) body = <ErrorMessage error={error} onRetry={onRetry} />;
  else if (documents === null) body = <p className="muted" role="status">{t("docs.loading")}</p>;
  else if (documents.length === 0) body = <p className="empty" role="status">{t("docs.empty")}</p>;
  else {
    body = (
      <ul className="docs__list">
        {documents.map((d) => {
          const selected = d.id === selectedId;
          const source = safeHttpUrl(d.source);
          return (
            <li key={d.id} className={selected ? "doc doc--selected" : "doc"}>
              <p className="doc__title">{d.title}</p>
              <p className="doc__meta muted">
                <span>{d.language}</span>
                {d.is_synthetic && <span> · {t("docs.synthetic")}</span>}
                {d.edition && <span> · {t("docs.edition", { edition: d.edition })}</span>}
                <span> · {t("docs.chunks", { n: d.n_chunks })}</span>
              </p>
              <div className="doc__actions">
                <button type="button" className="button button--small"
                        aria-pressed={selected}
                        onClick={() => onSelect(selected ? null : d.id)}>
                  {selected ? t("docs.selected") : t("docs.askHere")}
                </button>
                {source && (
                  <a href={source} target="_blank" rel="noopener noreferrer">
                    {t("docs.source")}<span aria-hidden="true"> ↗</span>
                  </a>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    );
  }
  return (
    <section className="docs" aria-labelledby="docs-heading">
      <h2 id="docs-heading">{t("docs.heading")}</h2>
      {body}
    </section>
  );
}
