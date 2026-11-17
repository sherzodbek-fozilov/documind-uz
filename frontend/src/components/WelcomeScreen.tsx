import { ArrowUpRight, ChevronDown, Languages, Link2, Quote } from "lucide-react";
import { useEffect, useId, useState } from "react";
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

/** Examples shown on a phone before "Show more". */
export const MOBILE_EXAMPLES = 2;

/** Same breakpoint as the phone layout in the stylesheet. */
const PHONE_QUERY = "(max-width: 640px)";

function matchesPhone(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(PHONE_QUERY).matches;
}

/** True on phone widths; false where matchMedia is unavailable (tests, old browsers). */
function usePhone(): boolean {
  const [phone, setPhone] = useState(matchesPhone);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(PHONE_QUERY);
    const onChange = () => setPhone(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);
  return phone;
}

interface Props {
  /** the query composer */
  children: ReactNode;
  onExample: (question: string) => void;
  disabled: boolean;
}

export function WelcomeScreen({ children, onExample, disabled }: Props) {
  const { t } = useI18n();
  const phone = usePhone();
  const [allExamples, setAllExamples] = useState(false);
  const listId = useId();
  const features = [
    { icon: <Quote size={18} aria-hidden="true" />, title: t("feature.quotes.title"), text: t("feature.quotes.text") },
    { icon: <Languages size={18} aria-hidden="true" />, title: t("feature.languages.title"), text: t("feature.languages.text") },
    { icon: <Link2 size={18} aria-hidden="true" />, title: t("feature.sources.title"), text: t("feature.sources.text") },
  ];
  // phones show the first examples and a toggle for the rest; wider screens show all
  const examples = phone && !allExamples ? EXAMPLES.slice(0, MOBILE_EXAMPLES) : EXAMPLES;
  const featureList = (
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
  );

  return (
    <div className="welcome">
      <div className="welcome__inner">
        <header className="welcome__head">
          <h2 className="welcome__title">{t("welcome.title")}</h2>
          <p className="welcome__subtitle">{t("welcome.subtitle")}</p>
        </header>

        {children}

        <section className="examples" aria-labelledby="examples-heading">
          <h3 id="examples-heading" className="eyebrow">{t("welcome.examples")}</h3>
          <ul id={listId} className="examples__list">
            {examples.map((ex) => (
              <li key={ex.text}>
                <button type="button" className="example" lang={ex.lang} disabled={disabled}
                        onClick={() => onExample(ex.text)}>
                  <span>{ex.text}</span>
                  <ArrowUpRight size={16} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
          {phone && EXAMPLES.length > MOBILE_EXAMPLES && (
            <button type="button" className="examples__more" aria-expanded={allExamples}
                    aria-controls={listId} onClick={() => setAllExamples(!allExamples)}>
              {allExamples ? t("welcome.fewerExamples") : t("welcome.moreExamples")}
              <ChevronDown size={15} aria-hidden="true" />
            </button>
          )}
        </section>

        {/* on a phone the product facts are folded away under the primary content */}
        {phone ? (
          <details className="about">
            <summary className="about__summary">
              {t("welcome.about")}
              <ChevronDown size={16} aria-hidden="true" />
            </summary>
            {featureList}
          </details>
        ) : featureList}
      </div>
    </div>
  );
}
