import { Check, Copy, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n/context";
import { copyText } from "../lib/clipboard";

interface Props {
  /** the text to copy, read at the moment of the click */
  getText: () => string;
  label: string;
  /** show only the icon; the label stays as the accessible name */
  iconOnly?: boolean;
}

/** Copies text and reports the outcome for two seconds. */
export function CopyButton({ getText, label, iconOnly = false }: Props) {
  const { t } = useI18n();
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copy() {
    const ok = await copyText(getText());
    setState(ok ? "copied" : "failed");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setState("idle"), 2000);
  }

  const feedback = state === "copied" ? t("results.copied")
    : state === "failed" ? t("results.copyFailed") : null;
  const Icon = state === "copied" ? Check : state === "failed" ? X : Copy;
  return (
    <button type="button" className={`btn btn--ghost btn--sm copy copy--${state}`}
            aria-label={iconOnly ? label : undefined} title={iconOnly ? label : undefined}
            onClick={copy}>
      <Icon size={15} aria-hidden="true" />
      {!iconOnly && <span>{feedback ?? label}</span>}
      <span className="visually-hidden" aria-live="polite">{iconOnly ? feedback : null}</span>
    </button>
  );
}
