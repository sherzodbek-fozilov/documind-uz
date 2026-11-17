import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useI18n } from "../i18n/context";
import type { Session } from "../state/history";

interface Props {
  sessions: Session[];
  /** the session open in the workspace, if any */
  activeId: string | null;
  onOpen: (session: Session) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
}

/** Earlier queries, kept in this browser only. */
export function SearchHistory({ sessions, activeId, onOpen, onDelete, onClear }: Props) {
  const { t, lang } = useI18n();
  const [confirming, setConfirming] = useState(false);

  // the confirmation lapses on its own, so a later stray click cannot clear the history
  useEffect(() => {
    if (!confirming) return;
    const timer = window.setTimeout(() => setConfirming(false), 4000);
    return () => window.clearTimeout(timer);
  }, [confirming]);

  const date = new Intl.DateTimeFormat(lang, { day: "numeric", month: "short" });

  return (
    <section className="history" aria-labelledby="history-heading">
      <div className="history__head">
        <h2 id="history-heading" className="eyebrow">{t("history.heading")}</h2>
        {sessions.length > 0 && (
          <button type="button" className="link-btn"
                  onClick={() => {
                    if (confirming) onClear();
                    setConfirming(!confirming);
                  }}>
            {confirming ? t("history.clearConfirm") : t("history.clear")}
          </button>
        )}
      </div>
      {sessions.length === 0 ? (
        <p className="history__empty">{t("history.empty")}</p>
      ) : (
        <ul className="history__list">
          {sessions.map((s) => (
            <li key={s.id} className={s.id === activeId ? "history__item is-active" : "history__item"}>
              <button type="button" className="history__open"
                      aria-current={s.id === activeId ? "true" : undefined}
                      onClick={() => onOpen(s)}>
                <span className="history__title">{s.title}</span>
                <time className="history__date" dateTime={new Date(s.updatedAt).toISOString()}>
                  {date.format(s.updatedAt)}
                </time>
              </button>
              <button type="button" className="icon-btn history__delete"
                      aria-label={t("history.delete", { title: s.title })}
                      onClick={() => onDelete(s.id)}>
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
