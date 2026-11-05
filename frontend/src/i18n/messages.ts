// UI strings. Uzbek is in the Latin script (the main script of the documents); questions
// themselves may be asked in Uzbek (Latin or Cyrillic) or Russian, whatever the UI language.

export const LANGS = ["uz", "ru", "en"] as const;
export type Lang = (typeof LANGS)[number];

export const LANG_NAMES: Record<Lang, string> = { uz: "Oʻzbekcha", ru: "Русский", en: "English" };

const en = {
  "app.tagline": "Answers with exact quotes from Uzbek and Russian legal documents",
  "lang.label": "Interface language",

  "ask.label": "Your question",
  "ask.placeholder": "e.g. Ijara haqi qachon toʻlanadi? / Когда вносится арендная плата?",
  "ask.hint": "Ask in Uzbek (Latin or Cyrillic) or Russian.",
  "ask.corpus": "Collection",
  "ask.scope": "Search in",
  "ask.scopeAll": "All documents",
  "ask.submit": "Ask",
  "ask.loading": "Searching…",

  "corpus.real": "Real documents",
  "corpus.synthetic": "Synthetic (test) documents",

  "results.heading": "Passages for: “{question}”",
  "results.count": "{n} passages",
  "results.empty": "No passages found. Try other words, or search all documents.",
  "results.idle": "Ask a question to see passages with the exact quote highlighted.",
  "results.check": "Quotes verified against the source text: {valid} of {checked}",

  "result.rank": "#{rank}",
  "result.article": "Article",
  "result.chunk": "Chunk",
  "result.source": "Open in source",
  "result.noSource": "No online source",
  "result.notExact": "The quote could not be located in the passage, so it is shown separately.",
  "result.quote": "Quote",

  "docs.heading": "Documents",
  "docs.loading": "Loading documents…",
  "docs.empty": "No documents in this collection yet. Ingest documents with “documind ingest”.",
  "docs.chunks": "{n} chunks",
  "docs.edition": "Edition: {edition}",
  "docs.source": "Source",
  "docs.askHere": "Search only here",
  "docs.selected": "Selected",
  "docs.synthetic": "synthetic",

  "error.title": "Something went wrong",
  "error.network": "The API cannot be reached. Check that the server is running (documind serve).",
  "error.unavailable": "No documents have been ingested in this collection yet.",
  "error.not_found": "This document is not in the selected collection.",
  "error.invalid": "The question was not accepted. Check its length and try again.",
  "error.server": "The server returned an error. Try again later.",
  "error.detail": "Details: {detail}",
  "error.retry": "Try again",

  "health.ok": "{documents} documents, {chunks} chunks · {mode} · {retriever}",
  "health.down": "API offline",
  "health.checking": "Connecting…",
} as const;

export type MessageKey = keyof typeof en;
export type Messages = Record<MessageKey, string>;

const ru: Messages = {
  "app.tagline": "Ответы с точными цитатами из узбекских и российских правовых документов",
  "lang.label": "Язык интерфейса",

  "ask.label": "Ваш вопрос",
  "ask.placeholder": "например: Когда вносится арендная плата? / Ijara haqi qachon toʻlanadi?",
  "ask.hint": "Спрашивайте на узбекском (латиница или кириллица) или русском.",
  "ask.corpus": "Коллекция",
  "ask.scope": "Искать в",
  "ask.scopeAll": "Во всех документах",
  "ask.submit": "Спросить",
  "ask.loading": "Поиск…",

  "corpus.real": "Реальные документы",
  "corpus.synthetic": "Синтетические (тестовые) документы",

  "results.heading": "Фрагменты по запросу: «{question}»",
  "results.count": "Фрагментов: {n}",
  "results.empty": "Ничего не найдено. Попробуйте другие слова или поиск по всем документам.",
  "results.idle": "Задайте вопрос, чтобы увидеть фрагменты с выделенной точной цитатой.",
  "results.check": "Цитаты сверены с текстом источника: {valid} из {checked}",

  "result.rank": "№{rank}",
  "result.article": "Статья",
  "result.chunk": "Фрагмент",
  "result.source": "Открыть в источнике",
  "result.noSource": "Нет онлайн-источника",
  "result.notExact": "Цитату не удалось найти во фрагменте, поэтому она показана отдельно.",
  "result.quote": "Цитата",

  "docs.heading": "Документы",
  "docs.loading": "Загрузка документов…",
  "docs.empty": "В этой коллекции пока нет документов. Загрузите их командой «documind ingest».",
  "docs.chunks": "Фрагментов: {n}",
  "docs.edition": "Редакция: {edition}",
  "docs.source": "Источник",
  "docs.askHere": "Искать только здесь",
  "docs.selected": "Выбран",
  "docs.synthetic": "синтетический",

  "error.title": "Что-то пошло не так",
  "error.network": "API недоступен. Проверьте, что сервер запущен (documind serve).",
  "error.unavailable": "В этой коллекции ещё нет загруженных документов.",
  "error.not_found": "Этого документа нет в выбранной коллекции.",
  "error.invalid": "Вопрос не принят. Проверьте его длину и попробуйте снова.",
  "error.server": "Сервер вернул ошибку. Попробуйте позже.",
  "error.detail": "Подробности: {detail}",
  "error.retry": "Повторить",

  "health.ok": "Документов: {documents}, фрагментов: {chunks} · {mode} · {retriever}",
  "health.down": "API недоступен",
  "health.checking": "Подключение…",
};

const uz: Messages = {
  "app.tagline": "Oʻzbek va rus huquqiy hujjatlaridan aniq iqtiboslar bilan javoblar",
  "lang.label": "Interfeys tili",

  "ask.label": "Savolingiz",
  "ask.placeholder": "masalan: Ijara haqi qachon toʻlanadi? / Когда вносится арендная плата?",
  "ask.hint": "Oʻzbek (lotin yoki kirill) yoki rus tilida soʻrang.",
  "ask.corpus": "Toʻplam",
  "ask.scope": "Qayerda qidirish",
  "ask.scopeAll": "Barcha hujjatlarda",
  "ask.submit": "Soʻrash",
  "ask.loading": "Qidirilmoqda…",

  "corpus.real": "Haqiqiy hujjatlar",
  "corpus.synthetic": "Sintetik (sinov) hujjatlar",

  "results.heading": "Soʻrov boʻyicha parchalar: “{question}”",
  "results.count": "Parchalar: {n}",
  "results.empty": "Hech narsa topilmadi. Boshqa soʻzlarni sinab koʻring yoki barcha hujjatlarda qidiring.",
  "results.idle": "Aniq iqtibos ajratib koʻrsatilgan parchalarni koʻrish uchun savol bering.",
  "results.check": "Iqtiboslar manba matni bilan tekshirildi: {checked} tadan {valid} tasi",

  "result.rank": "№{rank}",
  "result.article": "Modda",
  "result.chunk": "Parcha",
  "result.source": "Manbada ochish",
  "result.noSource": "Onlayn manba yoʻq",
  "result.notExact": "Iqtibos parcha ichida topilmadi, shuning uchun alohida koʻrsatilgan.",
  "result.quote": "Iqtibos",

  "docs.heading": "Hujjatlar",
  "docs.loading": "Hujjatlar yuklanmoqda…",
  "docs.empty": "Bu toʻplamda hali hujjat yoʻq. Hujjatlarni “documind ingest” buyrugʻi bilan yuklang.",
  "docs.chunks": "Parchalar: {n}",
  "docs.edition": "Tahrir: {edition}",
  "docs.source": "Manba",
  "docs.askHere": "Faqat shu yerda qidirish",
  "docs.selected": "Tanlangan",
  "docs.synthetic": "sintetik",

  "error.title": "Xatolik yuz berdi",
  "error.network": "API bilan bogʻlanib boʻlmadi. Server ishga tushirilganini tekshiring (documind serve).",
  "error.unavailable": "Bu toʻplamga hali hujjat yuklanmagan.",
  "error.not_found": "Bu hujjat tanlangan toʻplamda yoʻq.",
  "error.invalid": "Savol qabul qilinmadi. Uzunligini tekshirib, qayta urinib koʻring.",
  "error.server": "Server xato qaytardi. Keyinroq urinib koʻring.",
  "error.detail": "Tafsilotlar: {detail}",
  "error.retry": "Qayta urinish",

  "health.ok": "Hujjatlar: {documents}, parchalar: {chunks} · {mode} · {retriever}",
  "health.down": "API ishlamayapti",
  "health.checking": "Ulanmoqda…",
};

export const MESSAGES: Record<Lang, Messages> = { uz, ru, en };

export type Params = Record<string, string | number>;

/** Look up a message and fill in {placeholders}; an unknown placeholder is left as is. */
export function translate(lang: Lang, key: MessageKey, params?: Params): string {
  const template = MESSAGES[lang][key] ?? MESSAGES.en[key];
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (m, name: string) =>
    name in params ? String(params[name]) : m);
}

export function isLang(value: unknown): value is Lang {
  return typeof value === "string" && (LANGS as readonly string[]).includes(value);
}

/** First supported language among the browser's preferences, otherwise Uzbek. */
export function detectLang(preferred: readonly string[]): Lang {
  for (const tag of preferred) {
    const base = tag.toLowerCase().split("-")[0];
    if (isLang(base)) return base;
  }
  return "uz";
}
