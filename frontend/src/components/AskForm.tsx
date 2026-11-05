import { useId, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import type { Corpus, DocumentInfo } from "../api/types";
import { useI18n } from "../i18n/context";

export const MAX_QUESTION = 1000; // same limit as the API (AskRequest.question)

interface Props {
  corpus: Corpus;
  onCorpusChange: (corpus: Corpus) => void;
  /** documents of the current corpus, for the scope selector */
  documents: DocumentInfo[];
  scope: string | null;
  onScopeChange: (id: string | null) => void;
  loading: boolean;
  onAsk: (question: string) => void;
}

export function AskForm(props: Props) {
  const { corpus, onCorpusChange, documents, scope, onScopeChange, loading, onAsk } = props;
  const { t } = useI18n();
  const [question, setQuestion] = useState("");
  const id = useId();
  const trimmed = question.trim();
  const canAsk = trimmed.length > 0 && !loading;

  function submit(e?: FormEvent) {
    e?.preventDefault();
    if (canAsk) onAsk(trimmed);
  }

  // Enter asks, Shift+Enter starts a new line
  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form className="ask" onSubmit={submit} aria-busy={loading}>
      <label htmlFor={`${id}-q`} className="ask__label">{t("ask.label")}</label>
      <textarea id={`${id}-q`} className="ask__input" rows={2} maxLength={MAX_QUESTION}
                value={question} placeholder={t("ask.placeholder")}
                aria-describedby={`${id}-hint`}
                onChange={(e) => setQuestion(e.target.value)} onKeyDown={onKeyDown} />
      <p id={`${id}-hint`} className="ask__hint muted">{t("ask.hint")}</p>

      <div className="ask__row">
        <label className="field">
          <span>{t("ask.corpus")}</span>
          <select value={corpus} onChange={(e) => onCorpusChange(e.target.value as Corpus)}>
            <option value="real">{t("corpus.real")}</option>
            <option value="synthetic">{t("corpus.synthetic")}</option>
          </select>
        </label>
        <label className="field">
          <span>{t("ask.scope")}</span>
          <select value={scope ?? ""} onChange={(e) => onScopeChange(e.target.value || null)}>
            <option value="">{t("ask.scopeAll")}</option>
            {documents.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
          </select>
        </label>
        <button type="submit" className="button ask__submit" disabled={!canAsk}>
          {loading ? t("ask.loading") : t("ask.submit")}
        </button>
      </div>
    </form>
  );
}
