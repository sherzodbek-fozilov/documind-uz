import type { Health } from "../api/types";
import { useI18n } from "../i18n/context";

export type HealthState = { state: "checking" } | { state: "ok"; health: Health } | { state: "down" };

export function StatusBar({ status }: { status: HealthState }) {
  const { t } = useI18n();
  const text = status.state === "ok"
    ? t("health.ok", { ...status.health })
    : t(status.state === "down" ? "health.down" : "health.checking");
  return (
    <p className={`status status--${status.state}`} role="status" aria-live="polite">
      <span className="status__dot" aria-hidden="true" />
      {text}
    </p>
  );
}
