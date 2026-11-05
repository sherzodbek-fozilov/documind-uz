import type { AskResponse } from "../api/types";
import { useI18n } from "../i18n/context";
import { ResultCard } from "./ResultCard";

interface Props {
  response: AskResponse;
  /** document id -> title */
  titles: Record<string, string>;
}

export function ResultList({ response, titles }: Props) {
  const { t } = useI18n();
  const { passages, citation_check: check } = response;
  return (
    <section className="results" aria-labelledby="results-heading">
      <h2 id="results-heading" className="results__heading">
        {t("results.heading", { question: response.question })}
      </h2>
      {passages.length === 0 ? (
        <p className="empty" role="status">{t("results.empty")}</p>
      ) : (
        <>
          <p className="results__summary muted">
            {t("results.count", { n: passages.length })}
            {check.checked > 0 && <> · {t("results.check", { valid: check.valid, checked: check.checked })}</>}
          </p>
          <ol className="results__list">
            {passages.map((p) => (
              <li key={p.chunk_id}>
                <ResultCard passage={p} title={titles[p.document_id]} />
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
