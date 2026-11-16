import { Monitor, Moon, Sun } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useI18n } from "../i18n/context";
import type { MessageKey } from "../i18n/messages";
import { THEMES } from "../state/theme";
import type { ThemeChoice } from "../state/theme";
import { LanguageSwitch } from "./LanguageSwitch";

const THEME_UI: Record<ThemeChoice, { icon: LucideIcon; label: MessageKey }> = {
  dark: { icon: Moon, label: "theme.dark" },
  light: { icon: Sun, label: "theme.light" },
  system: { icon: Monitor, label: "theme.system" },
};

interface Props {
  theme: ThemeChoice;
  onThemeChange: (theme: ThemeChoice) => void;
}

/** Interface language and color theme. */
export function SettingsPanel({ theme, onThemeChange }: Props) {
  const { t } = useI18n();
  return (
    <section className="settings" aria-label={t("settings.heading")}>
      <div className="settings__row">
        <span className="settings__label">{t("lang.label")}</span>
        <LanguageSwitch />
      </div>
      <div className="settings__row">
        <span className="settings__label">{t("theme.label")}</span>
        <div className="segmented" role="group" aria-label={t("theme.label")}>
          {THEMES.map((choice) => {
            const { icon: Icon, label } = THEME_UI[choice];
            return (
              <button key={choice} type="button" aria-pressed={choice === theme}
                      className={choice === theme ? "segmented__btn is-active" : "segmented__btn"}
                      aria-label={t(label)} title={t(label)}
                      onClick={() => onThemeChange(choice)}>
                <Icon size={15} aria-hidden="true" />
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
