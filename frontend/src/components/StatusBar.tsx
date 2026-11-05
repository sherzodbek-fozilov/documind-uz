import type { Health } from "../api/types";
import { useI18n } from "../i18n/context";

export type HealthState = { state: "checking" } | { state: "ok"; health: Health } | { state: "down" };

// only the fields the message shows; public_demo (boolean) is not a message parameter
function healthParams({ documents, chunks, mode, retriever }: Health) {
  return { documents, chunks, mode, retriever };
}

export function StatusBar({ status }: { status: HealthState }) {
  const { t } = useI18n();
  const text = status.state === "ok"
    ? t("health.ok", healthParams(status.health))
    : t(status.state === "down" ? "health.down" : "health.checking");
  return (
    <p className={`status status--${status.state}`} role="status" aria-live="polite">
      <span className="status__dot" aria-hidden="true" />
      {text}
    </p>
  );
}
