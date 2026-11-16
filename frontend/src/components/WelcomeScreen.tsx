import { ArrowUpRight, Languages, Link2, Quote } from "lucide-react";
import type { ReactNode } from "react";
import { useI18n } from "../i18n/context";

// Example questions in the languages of the documents (Russian and Uzbek). They are
// sent to the API like any typed question; nothing about their results is assumed.
export const EXAMPLES: readonly { text: string; lang: string }[] = [
  { text: "Когда вносится арендная плата?", lang: "ru" },
  { text: "Ijara haqi qachon toʻlanadi?", lang: "uz-Latn" },
  { text: "Какова продолжительность ежегодного трудового отпуска?", lang: "ru" },
  { text: "Mehnat shartnomasi qanday hollarda bekor qilinadi?", lang: "uz-Latn" },
];

interface Props {
  /** the query composer */
  children: ReactNode;
  onExample: (question: string) => void;
  disabled: boolean;
}

export function WelcomeScreen({ children, onExample, disabled }: Props) {
  const { t } = useI18n();
  const features = [
    { icon: <Quote size={18} aria-hidden="true" />, title: t("feature.quotes.title"), text: t("feature.quotes.text") },
    { icon: <Languages size={18} aria-hidden="true" />, title: t("feature.languages.title"), text: t("feature.languages.text") },
    { icon: <Link2 size={18} aria-hidden="true" />, title: t("feature.sources.title"), text: t("feature.sources.text") },
  ];
  return (
    <div className="welcome">
      <div className="welcome__inner">
        <h2 className="welcome__title">{t("welcome.title")}</h2>
        <p className="welcome__subtitle">{t("welcome.subtitle")}</p>

        {children}

        <section className="examples" aria-labelledby="examples-heading">
          <h3 id="examples-heading" className="eyebrow">{t("welcome.examples")}</h3>
          <ul className="examples__list">
            {EXAMPLES.map((ex) => (
              <li key={ex.text}>
                <button type="button" className="example" lang={ex.lang} disabled={disabled}
                        onClick={() => onExample(ex.text)}>
                  <span>{ex.text}</span>
                  <ArrowUpRight size={16} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        </section>

        <ul className="features">
          {features.map((f) => (
            <li key={f.title} className="feature">
              <span className="feature__icon">{f.icon}</span>
              <div>
                <p className="feature__title">{f.title}</p>
                <p className="feature__text">{f.text}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
