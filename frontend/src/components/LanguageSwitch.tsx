import { useI18n } from "../i18n/context";
import { LANGS, LANG_NAMES } from "../i18n/messages";

export function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <div className="lang-switch" role="group" aria-label={t("lang.label")}>
      {LANGS.map((l) => (
        <button key={l} type="button" lang={l} aria-pressed={l === lang}
                className={l === lang ? "lang-switch__btn is-active" : "lang-switch__btn"}
                title={LANG_NAMES[l]} onClick={() => setLang(l)}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
