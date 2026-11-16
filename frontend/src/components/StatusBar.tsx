import type { Health } from "../api/types";
import { useI18n } from "../i18n/context";

export type HealthState = { state: "checking" } | { state: "ok"; health: Health } | { state: "down" };

// only the fields the message shows; public_demo (boolean) is not a message parameter
function healthParams({ documents, chunks, mode, retriever }: Health) {
  return { documents, chunks, mode, retriever };
}

/** API status. The counts, answer mode and retriever are technical details: they are
 * behind a disclosure, not in the main interface. */
export function StatusBar({ status, compact = false }: { status: HealthState; compact?: boolean }) {
  const { t } = useI18n();
  const label = status.state === "ok" ? t("health.online")
    : t(status.state === "down" ? "health.down" : "health.checking");
  const dot = <span className="status__dot" aria-hidden="true" />;

  if (compact) {
    return (
      <p className={`status status--${status.state} status--compact`} role="status" title={label}>
        {dot}<span className="visually-hidden">{label}</span>
      </p>
    );
  }
  if (status.state !== "ok") {
    return (
      <p className={`status status--${status.state}`} role="status" aria-live="polite">
        {dot}{label}
      </p>
    );
  }
  return (
    <details className="status status--ok">
      <summary>{dot}{label}</summary>
      <p className="status__details">{t("health.ok", healthParams(status.health))}</p>
    </details>
  );
}
