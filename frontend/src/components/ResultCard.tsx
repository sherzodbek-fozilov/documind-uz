import type { Passage } from "../api/types";
import { useI18n } from "../i18n/context";
import { splitAroundQuote, trimContext } from "../lib/highlight";
import { safeHttpUrl } from "../lib/url";

const CLIP = 600;

/** Blocks of a chunk are separated by blank lines; one line break is enough on screen.
 * Only the context around the quote is changed, never the quote. */
function tidy(text: string): string {
  return text.replace(/\n{2,}/g, "\n");
}

/** The start of a passage, cut at a word boundary, for cards without a highlight. */
function clip(text: string): string {
  return text.length <= CLIP ? text : `${text.slice(0, CLIP).replace(/\s\S*$/, "")}…`;
}

interface Props {
  passage: Passage;
  /** document title; the document id is shown when it is unknown */
  title?: string;
}

export function ResultCard({ passage, title }: Props) {
  const { t } = useI18n();
  const h = trimContext(splitAroundQuote(passage.text, passage.quote, passage.quote_start,
                                         passage.quote_end));
  const link = safeHttpUrl(passage.link);
  const headingId = `result-${passage.rank}-title`;

  return (
    <article className="result" aria-labelledby={headingId}>
      <header className="result__head">
        <span className="result__rank">{t("result.rank", { rank: passage.rank })}</span>
        <h3 id={headingId} className="result__title">{title ?? passage.document_id}</h3>
      </header>
      <dl className="result__meta">
        {passage.section_title && (
          <div>
            <dt>{t("result.article")}</dt>
            <dd>{passage.section_title}</dd>
          </div>
        )}
        <div>
          <dt>{t("result.chunk")}</dt>
          <dd><code>{passage.chunk_id}</code></dd>
        </div>
      </dl>

      {h.exact ? (
        <p className="result__passage" lang={passage.language}>
          {tidy(h.before)}
          <mark className="result__quote">{h.quote}</mark>
          {tidy(h.after)}
        </p>
      ) : (
        <>
          <p className="result__passage" lang={passage.language}>{tidy(clip(passage.text))}</p>
          <p className="result__note" role="note">{t("result.notExact")}</p>
          <blockquote className="result__quote result__quote--separate" lang={passage.language}
                      aria-label={t("result.quote")}>
            {passage.quote}
          </blockquote>
        </>
      )}

      <footer className="result__foot">
        {link ? (
          <a href={link} target="_blank" rel="noopener noreferrer">
            {t("result.source")}
            {passage.anchor && <span className="result__anchor"> #{passage.anchor}</span>}
            <span aria-hidden="true"> ↗</span>
          </a>
        ) : (
          <span className="muted">{t("result.noSource")}</span>
        )}
      </footer>
    </article>
  );
}
