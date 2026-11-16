import { ArrowUp, FileText, FolderOpen, LoaderCircle } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import type { Corpus, DocumentInfo } from "../api/types";
import { useI18n } from "../i18n/context";

export const MAX_QUESTION = 1000; // same limit as the API (AskRequest.question)
const COUNTER_FROM = 800; // the character counter appears near the limit

interface Props {
  corpus: Corpus;
  onCorpusChange: (corpus: Corpus) => void;
  /** documents of the current corpus, for the scope selector */
  documents: DocumentInfo[];
  scope: string | null;
  onScopeChange: (id: string | null) => void;
  loading: boolean;
  onAsk: (question: string) => void;
  /** larger input, for the start screen */
  size?: "default" | "large";
  /** changes whenever the input should take the focus (new query, scope picked) */
  focusKey?: number;
}

export function QueryComposer(props: Props) {
  const { corpus, onCorpusChange, documents, scope, onScopeChange, loading, onAsk,
          size = "default", focusKey } = props;
  const { t } = useI18n();
  const [question, setQuestion] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const id = useId();
  const trimmed = question.trim();
  const canAsk = trimmed.length > 0 && !loading;

  useEffect(() => {
    if (focusKey !== undefined) input.current?.focus();
  }, [focusKey]);

  // grow with the text, up to the max-height set in the stylesheet
  useEffect(() => {
    const el = input.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [question]);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    if (!canAsk) return;
    onAsk(trimmed);
    setQuestion("");
  }

  // Enter asks, Shift+Enter starts a new line
  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form className={`composer composer--${size}`} onSubmit={submit} aria-busy={loading}>
      <div className="composer__box">
        <label htmlFor={`${id}-q`} className="visually-hidden">{t("ask.label")}</label>
        <textarea id={`${id}-q`} ref={input} className="composer__input" rows={1}
                  maxLength={MAX_QUESTION} value={question} placeholder={t("ask.placeholder")}
                  aria-describedby={`${id}-hint`}
                  onChange={(e) => setQuestion(e.target.value)} onKeyDown={onKeyDown} />
        <div className="composer__bar">
          <label className="pill-select">
            <FolderOpen size={15} aria-hidden="true" />
            <span className="visually-hidden">{t("ask.corpus")}</span>
            <select value={corpus} onChange={(e) => onCorpusChange(e.target.value as Corpus)}>
              <option value="real">{t("corpus.real")}</option>
              <option value="synthetic">{t("corpus.synthetic")}</option>
            </select>
          </label>
          <label className={scope ? "pill-select is-set" : "pill-select"}>
            <FileText size={15} aria-hidden="true" />
            <span className="visually-hidden">{t("ask.scope")}</span>
            <select value={scope ?? ""} onChange={(e) => onScopeChange(e.target.value || null)}>
              <option value="">{t("ask.scopeAll")}</option>
              {documents.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
            </select>
          </label>
          {question.length >= COUNTER_FROM && (
            <span className="composer__count" aria-hidden="true">
              {question.length} / {MAX_QUESTION}
            </span>
          )}
          <button type="submit" className="composer__send" disabled={!canAsk}
                  aria-label={loading ? t("ask.loading") : t("ask.submit")}
                  title={loading ? t("ask.loading") : t("ask.submit")}>
            {loading ? <LoaderCircle size={18} className="spin" aria-hidden="true" />
                     : <ArrowUp size={18} aria-hidden="true" />}
          </button>
        </div>
      </div>
      <p id={`${id}-hint`} className="composer__hint">{t("ask.hint")}</p>
    </form>
  );
}
