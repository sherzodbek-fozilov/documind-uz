import { SearchX, ShieldCheck } from "lucide-react";
import type { AskResponse, Passage } from "../api/types";
import { useI18n } from "../i18n/context";
import { sectionLeaf } from "../lib/section";
import { safeHttpUrl } from "../lib/url";
import { CopyButton } from "./CopyButton";
import { SourceCard } from "./SourceCard";

interface Props {
  response: AskResponse;
  /** document id -> title */
  titles: Record<string, string>;
  /** chunk id of the passage open in the source viewer */
  activeChunkId?: string | null;
  onViewSource?: (passage: Passage) => void;
  /** the question was limited to one document: repeat it over all documents */
  onSearchAll?: () => void;
}

/** Plain text of a result, for the clipboard: the answer (if the API gave one) and every
 * quote with its document, article and link. */
function asText(response: AskResponse, titles: Record<string, string>): string {
  const quotes = response.passages.map((p) => {
    const where = [titles[p.document_id] ?? p.document_id, sectionLeaf(p.section_title)]
      .filter(Boolean).join(", ");
    const link = safeHttpUrl(p.link);
    return `${p.rank}. «${p.quote}»\n— ${where}${link ? `\n${link}` : ""}`;
  });
  return [response.answer, ...quotes].filter(Boolean).join("\n\n");
}

/**
 * The result of one question.
 *
 * - The API returned an `answer` (LLM mode): the answer text, then its sources.
 * - Otherwise (extractive mode): the passages are shown as search results. No answer
 *   text is composed in the browser.
 */
export function AnswerMessage({ response, titles, activeChunkId, onViewSource, onSearchAll }: Props) {
  const { t } = useI18n();
  const { passages, citation_check: check, answer } = response;
  const cited = new Set(response.citations.map((c) => c.chunk_id));
  const label = t("results.heading", { question: response.question });

  if (passages.length === 0) {
    return (
      <section className="answer answer--empty" aria-label={label}>
        <SearchX size={22} aria-hidden="true" />
        <p role="status">{t("results.empty")}</p>
        {onSearchAll && (
          <button type="button" className="btn btn--soft btn--sm" onClick={onSearchAll}>
            {t("results.searchAll")}
          </button>
        )}
      </section>
    );
  }

  return (
    <section className="answer" aria-label={label}>
      {answer ? (
        <div className="answer__generated">
          <p className="eyebrow">{t("results.answerLabel")}</p>
          <p className="answer__text">{answer}</p>
          <p className="answer__note">{t("results.answerNote")}</p>
        </div>
      ) : (
        <p className="answer__note">{t("results.extractiveNote")}</p>
      )}

      <div className="answer__bar">
        <p className="answer__summary">
          <span className="answer__count">
            {answer ? `${t("results.sources")} · ` : ""}{t("results.count", { n: passages.length })}
          </span>
          {check.checked > 0 && (
            <span className="answer__check">
              <ShieldCheck size={14} aria-hidden="true" />
              {t("results.check", { valid: check.valid, checked: check.checked })}
            </span>
          )}
        </p>
        <CopyButton getText={() => asText(response, titles)} label={t("results.copy")} />
      </div>

      <ol className="answer__sources">
        {passages.map((p) => (
          <li key={p.chunk_id}>
            <SourceCard passage={p} title={titles[p.document_id]}
                        active={p.chunk_id === activeChunkId} cited={cited.has(p.chunk_id)}
                        onView={onViewSource} />
          </li>
        ))}
      </ol>

      <details className="tech">
        <summary>{t("results.tech")}</summary>
        <dl className="tech__list">
          <div><dt>{t("tech.mode")}</dt><dd>{response.mode}</dd></div>
          <div><dt>{t("tech.retriever")}</dt><dd>{response.retriever}</dd></div>
          <div><dt>{t("tech.corpus")}</dt><dd>{response.corpus}</dd></div>
          <div>
            <dt>{t("tech.check")}</dt>
            <dd>
              {t("tech.checkValue", { valid: check.valid, checked: check.checked })}
              {Object.entries(check.failures).map(([reason, n]) => (
                <span key={reason} className="tech__failure"> · {reason}: {n}</span>
              ))}
            </dd>
          </div>
          <div>
            <dt>{t("tech.chunks")}</dt>
            <dd>
              <ol className="tech__chunks">
                {passages.map((p) => (
                  <li key={p.chunk_id}>
                    <code>{p.chunk_id}</code>
                    {p.anchor && <code className="tech__anchor"> #{p.anchor}</code>}
                  </li>
                ))}
              </ol>
            </dd>
          </div>
        </dl>
      </details>
    </section>
  );
}
