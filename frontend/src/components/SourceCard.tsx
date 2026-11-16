import { BookOpenText, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { useId, useState } from "react";
import type { Passage } from "../api/types";
import { useI18n } from "../i18n/context";
import { splitAroundQuote, trimContext } from "../lib/highlight";
import { sectionLeaf } from "../lib/section";
import { safeHttpUrl } from "../lib/url";
import { CopyButton } from "./CopyButton";

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
  /** this passage is open in the source viewer */
  active?: boolean;
  /** LLM mode: the answer cites this passage */
  cited?: boolean;
  /** open the passage in the source viewer; no button without it */
  onView?: (passage: Passage) => void;
}

/** One retrieved passage: the exact quote highlighted inside its context. Internal
 * identifiers (chunk id, anchor) are not shown here. */
export function SourceCard({ passage, title, active = false, cited = false, onView }: Props) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const headingId = useId();
  const full = splitAroundQuote(passage.text, passage.quote, passage.quote_start, passage.quote_end);
  const short = trimContext(full);
  const h = expanded ? full : short;
  const clipped = clip(passage.text);
  const canExpand = full.exact
    ? short.before !== full.before || short.after !== full.after
    : clipped !== passage.text;
  const link = safeHttpUrl(passage.link);
  const article = sectionLeaf(passage.section_title);

  return (
    <article className={active ? "source is-active" : "source"} aria-labelledby={headingId}>
      <header className="source__head">
        <span className="source__rank" aria-hidden="true">{passage.rank}</span>
        <div className="source__titles">
          <h3 id={headingId} className="source__title">{title ?? passage.document_id}</h3>
          {article && (
            <p className="source__article" lang={passage.language}>
              <span className="visually-hidden">{t("result.article")}: </span>{article}
            </p>
          )}
        </div>
        {cited && <span className="badge badge--accent">{t("result.cited")}</span>}
      </header>

      {h.exact ? (
        <p className="source__text" lang={passage.language}>
          {tidy(h.before).replace(/^…\s+/, "…")}
          <mark className="quote">{h.quote}</mark>
          {tidy(h.after).replace(/\s+…$/, "…")}
        </p>
      ) : (
        <>
          <p className="source__text" lang={passage.language}>
            {tidy(expanded ? passage.text : clipped)}
          </p>
          <p className="source__note" role="note">{t("result.notExact")}</p>
          <blockquote className="quote quote--separate" lang={passage.language}
                      aria-label={t("result.quote")}>
            {passage.quote}
          </blockquote>
        </>
      )}

      <footer className="source__foot">
        {onView && (
          <button type="button" className="btn btn--soft btn--sm" aria-pressed={active}
                  onClick={() => onView(passage)}>
            <BookOpenText size={15} aria-hidden="true" />
            <span>{t("result.view")}</span>
          </button>
        )}
        {canExpand && (
          <button type="button" className="btn btn--ghost btn--sm" aria-expanded={expanded}
                  onClick={() => setExpanded(!expanded)}>
            {expanded ? <ChevronUp size={15} aria-hidden="true" />
                      : <ChevronDown size={15} aria-hidden="true" />}
            <span>{expanded ? t("result.collapse") : t("result.expand")}</span>
          </button>
        )}
        <CopyButton getText={() => passage.quote} label={t("result.copyQuote")} iconOnly />
        <span className="source__spacer" />
        {link ? (
          <a className="source__link" href={link} target="_blank" rel="noopener noreferrer">
            {t("result.source")}
            <ExternalLink size={14} aria-hidden="true" />
          </a>
        ) : (
          <span className="source__nolink">{t("result.noSource")}</span>
        )}
      </footer>
    </article>
  );
}
