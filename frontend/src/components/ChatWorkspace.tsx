import { FileText } from "lucide-react";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import type { AskResponse, Corpus, Passage } from "../api/types";
import { useI18n } from "../i18n/context";
import { AnswerMessage } from "./AnswerMessage";
import { ErrorMessage } from "./ErrorMessage";
import { SkeletonLines } from "./Skeleton";

interface TurnBase {
  id: string;
  question: string;
  corpus: Corpus;
  /** the document the question was limited to, if any */
  documentId: string | null;
}

/** One question and what came of it. */
export type Turn =
  | (TurnBase & { state: "loading" })
  | (TurnBase & { state: "done"; response: AskResponse })
  | (TurnBase & { state: "error"; error: unknown });

interface Props {
  turns: Turn[];
  /** document id -> title */
  titles: Record<string, string>;
  activeChunkId: string | null;
  onViewSource: (passage: Passage) => void;
  onRetry: (turn: Turn) => void;
  onSearchAll: (turn: Turn) => void;
  /** the query composer, docked under the thread */
  children: ReactNode;
}

export function ChatWorkspace(props: Props) {
  const { turns, titles, activeChunkId, onViewSource, onRetry, onSearchAll, children } = props;
  const { t } = useI18n();
  const last = useRef<HTMLLIElement>(null);
  const lastId = turns.length ? turns[turns.length - 1].id : null;

  // a new question scrolls to its own start, so the result is read from the top
  useEffect(() => {
    last.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [lastId]);

  return (
    <div className="chat">
      <div className="chat__scroll">
        <ol className="chat__thread" aria-label={t("chat.thread")} aria-live="polite">
          {turns.map((turn, i) => (
            <li key={turn.id} className="turn" ref={i === turns.length - 1 ? last : undefined}>
              <div className="turn__question">
                <h2 className="turn__text">
                  <span className="visually-hidden">{t("chat.you")}: </span>{turn.question}
                </h2>
                {turn.documentId && (
                  <p className="turn__scope">
                    <FileText size={13} aria-hidden="true" />
                    {t("chat.scope", { title: titles[turn.documentId] ?? turn.documentId })}
                  </p>
                )}
              </div>
              <div className="turn__result">
                {turn.state === "loading" && (
                  <div className="searching" role="status">
                    <p className="searching__label">
                      <span className="searching__dots" aria-hidden="true"><i /><i /><i /></span>
                      {t("ask.loading")}
                    </p>
                    <div className="searching__card"><SkeletonLines widths={["38%", "96%", "88%", "62%"]} /></div>
                    <div className="searching__card"><SkeletonLines widths={["46%", "92%", "70%"]} /></div>
                  </div>
                )}
                {turn.state === "error" && (
                  <ErrorMessage error={turn.error} onRetry={() => onRetry(turn)} />
                )}
                {turn.state === "done" && (
                  <AnswerMessage response={turn.response} titles={titles}
                                 activeChunkId={activeChunkId} onViewSource={onViewSource}
                                 onSearchAll={turn.documentId ? () => onSearchAll(turn) : undefined} />
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>
      <div className="chat__dock">
        {children}
        <p className="chat__note">{t("chat.independent")}</p>
      </div>
    </div>
  );
}
