import { CloudOff } from "lucide-react";
import type { Health } from "../api/types";
import { useI18n } from "../i18n/context";

export type HealthState = { state: "checking" } | { state: "ok"; health: Health } | { state: "down" };

/** The service could not be reached. Normal connectivity is not shown at all; only a
 * failed health check produces this notice, with a way to try again. */
export function ServiceNotice({ status, onRetry }: { status: HealthState; onRetry: () => void }) {
  const { t } = useI18n();
  if (status.state !== "down") return null;
  return (
    <div className="notice" role="alert">
      <CloudOff size={16} aria-hidden="true" />
      <p className="notice__text">{t("health.down")}</p>
      <button type="button" className="btn btn--outline btn--sm" onClick={onRetry}>
        {t("error.retry")}
      </button>
    </div>
  );
}
