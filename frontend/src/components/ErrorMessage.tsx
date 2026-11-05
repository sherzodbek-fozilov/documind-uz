import { ApiError } from "../api/client";
import { useI18n } from "../i18n/context";
import type { MessageKey } from "../i18n/messages";

interface Props {
  error: unknown;
  onRetry?: () => void;
}

/** A failed request, explained in the UI language; the server's reason is shown below. */
export function ErrorMessage({ error, onRetry }: Props) {
  const { t } = useI18n();
  const kind = error instanceof ApiError ? error.kind : "server";
  const detail = error instanceof ApiError && kind !== "network" ? error.message : null;
  return (
    <div className="error" role="alert">
      <p className="error__title">{t("error.title")}</p>
      <p>{t(`error.${kind}` as MessageKey)}</p>
      {detail && <p className="error__detail muted">{t("error.detail", { detail })}</p>}
      {onRetry && (
        <button type="button" className="button button--secondary" onClick={onRetry}>
          {t("error.retry")}
        </button>
      )}
    </div>
  );
}
