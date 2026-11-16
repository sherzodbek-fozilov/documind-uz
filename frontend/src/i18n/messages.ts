// UI strings. Uzbek is in the Latin script (the main script of the documents); questions
// themselves may be asked in Uzbek (Latin or Cyrillic) or Russian, whatever the UI language.

export const LANGS = ["uz", "ru", "en"] as const;
export type Lang = (typeof LANGS)[number];

export const LANG_NAMES: Record<Lang, string> = { uz: "Oʻzbekcha", ru: "Русский", en: "English" };

const en = {
  "app.tagline": "Answers with exact quotes from the legislation of Uzbekistan, in Uzbek and Russian",
  "app.product": "Legal search workspace",
  "lang.label": "Interface language",

  "nav.label": "Main navigation",
  "nav.newQuery": "New query",
  "nav.workspace": "Workspace",
  "nav.library": "Document library",
  "nav.collapse": "Collapse sidebar",
  "nav.expand": "Expand sidebar",
  "nav.open": "Open menu",
  "nav.close": "Close menu",

  "history.heading": "History",
  "history.empty": "Your queries will appear here.",
  "history.note": "Saved only in this browser.",
  "history.delete": "Delete “{title}”",
  "history.clear": "Clear",
  "history.clearConfirm": "Delete all?",

  "settings.heading": "Settings",
  "theme.label": "Theme",
  "theme.dark": "Dark",
  "theme.light": "Light",
  "theme.system": "System",

  "welcome.title": "What do you want to find in the legislation?",
  "welcome.subtitle": "DocuMind searches the legislation of Uzbekistan and returns the exact passages that match your question, each with a link to its source.",
  "welcome.examples": "Try an example",
  "feature.quotes.title": "Exact quotes",
  "feature.quotes.text": "Every result is a verbatim excerpt, checked against the source text.",
  "feature.languages.title": "Uzbek and Russian",
  "feature.languages.text": "Ask in Uzbek (Latin or Cyrillic) or in Russian.",
  "feature.sources.title": "Traceable sources",
  "feature.sources.text": "Read any excerpt in its context and open the original.",

  "ask.label": "Your question",
  "ask.placeholder": "e.g. Ijara haqi qachon toʻlanadi? / Когда вносится арендная плата?",
  "ask.hint": "Ask in Uzbek (Latin or Cyrillic) or Russian. Enter sends, Shift+Enter adds a line.",
  "ask.corpus": "Collection",
  "ask.scope": "Search in",
  "ask.scopeAll": "All documents",
  "ask.submit": "Ask",
  "ask.loading": "Searching…",

  "corpus.real": "Real documents",
  "corpus.synthetic": "Synthetic (test) documents",

  "chat.thread": "Questions and results",
  "chat.you": "Your question",
  "chat.scope": "In: {title}",
  "chat.independent": "Each question is searched on its own; earlier questions are not taken into account.",

  "results.heading": "Passages for: “{question}”",
  "results.count": "{n} passages",
  "results.empty": "No passages found. Try other words, or search all documents.",
  "results.check": "Quotes verified against the source text: {valid} of {checked}",
  "results.extractiveNote": "Exact excerpts from the source text, in order of relevance to your question. This is a search result, not a generated answer or legal advice.",
  "results.answerLabel": "Answer",
  "results.answerNote": "Generated from the excerpts below. Check the quotes before relying on it.",
  "results.sources": "Sources",
  "results.copy": "Copy",
  "results.copied": "Copied",
  "results.copyFailed": "Could not copy",
  "results.searchAll": "Search all documents",
  "results.tech": "Technical details",

  "tech.mode": "Answer mode",
  "tech.retriever": "Retriever",
  "tech.corpus": "Collection",
  "tech.check": "Citation check",
  "tech.checkValue": "{valid} of {checked} valid",
  "tech.chunks": "Passage identifiers",

  "result.article": "Article",
  "result.source": "Open original",
  "result.noSource": "No online source",
  "result.notExact": "The quote could not be located in the passage, so it is shown separately.",
  "result.quote": "Quote",
  "result.expand": "Show full passage",
  "result.collapse": "Show less",
  "result.view": "View in context",
  "result.copyQuote": "Copy quote",
  "result.cited": "Cited in the answer",

  "viewer.title": "Source",
  "viewer.close": "Close source viewer",
  "viewer.loading": "Loading the text…",
  "viewer.range": "Passages {from}–{to} of {total}",
  "viewer.earlier": "Show earlier text",
  "viewer.later": "Show later text",
  "viewer.fallback": "Only this passage can be shown: the server did not return the surrounding text.",
  "viewer.start": "Beginning of the document",
  "viewer.end": "End of the document",
  "viewer.quoted": "Quoted passage",

  "docs.heading": "Documents",
  "docs.subtitle": "The documents the search runs over.",
  "docs.search": "Search by title",
  "docs.filterLang": "Language",
  "docs.filterKind": "Type",
  "docs.all": "All",
  "docs.noMatch": "No documents match these filters.",
  "docs.reset": "Reset filters",
  "docs.loading": "Loading documents…",
  "docs.empty": "No documents in this collection yet. Ingest documents with “documind ingest”.",
  "docs.chunks": "{n} passages",
  "docs.edition": "Edition: {edition}",
  "docs.source": "Source",
  "docs.askHere": "Search only here",
  "docs.selected": "Selected",
  "docs.synthetic": "synthetic",
  "docs.structure": "Structure",
  "docs.back": "Back to the library",
  "docs.outline": "Document structure",
  "docs.outlineSearch": "Find a section",
  "docs.outlineEmpty": "No sections match.",
  "docs.outlineLoading": "Loading the structure…",
  "docs.sections": "{n} sections",
  "docs.untitled": "Untitled section",

  "language.ru": "Russian",
  "language.uzLatn": "Uzbek (Latin)",
  "language.uzCyrl": "Uzbek (Cyrillic)",
  "kind.law": "Law",
  "kind.upload": "Uploaded file",

  "error.title": "Something went wrong",
  "error.network": "The API cannot be reached. Check that the server is running (documind serve).",
  "error.unavailable": "No documents have been ingested in this collection yet.",
  "error.not_found": "This document is not in the selected collection.",
  "error.invalid": "The question was not accepted. Check its length and try again.",
  "error.server": "The server returned an error. Try again later.",
  "error.detail": "Details: {detail}",
  "error.retry": "Try again",

  "health.online": "API online",
  "health.ok": "{documents} documents, {chunks} chunks · {mode} · {retriever}",
  "health.down": "API offline",
  "health.checking": "Connecting…",
} as const;

export type MessageKey = keyof typeof en;
export type Messages = Record<MessageKey, string>;

const ru: Messages = {
  "app.tagline": "Ответы с точными цитатами из законодательства Узбекистана на узбекском и русском языках",
  "app.product": "Рабочее пространство правового поиска",
  "lang.label": "Язык интерфейса",

  "nav.label": "Основная навигация",
  "nav.newQuery": "Новый запрос",
  "nav.workspace": "Рабочая область",
  "nav.library": "Библиотека документов",
  "nav.collapse": "Свернуть боковую панель",
  "nav.expand": "Развернуть боковую панель",
  "nav.open": "Открыть меню",
  "nav.close": "Закрыть меню",

  "history.heading": "История",
  "history.empty": "Здесь появятся ваши запросы.",
  "history.note": "Хранится только в этом браузере.",
  "history.delete": "Удалить «{title}»",
  "history.clear": "Очистить",
  "history.clearConfirm": "Удалить всё?",

  "settings.heading": "Настройки",
  "theme.label": "Тема",
  "theme.dark": "Тёмная",
  "theme.light": "Светлая",
  "theme.system": "Системная",

  "welcome.title": "Что вы хотите найти в законодательстве?",
  "welcome.subtitle": "DocuMind ищет по законодательству Узбекистана и возвращает точные фрагменты, соответствующие вопросу, со ссылкой на источник.",
  "welcome.examples": "Попробуйте пример",
  "feature.quotes.title": "Точные цитаты",
  "feature.quotes.text": "Каждый результат — дословная выдержка, сверенная с текстом источника.",
  "feature.languages.title": "Узбекский и русский",
  "feature.languages.text": "Спрашивайте на узбекском (латиница или кириллица) или на русском.",
  "feature.sources.title": "Проверяемые источники",
  "feature.sources.text": "Читайте выдержку в контексте и открывайте оригинал.",

  "ask.label": "Ваш вопрос",
  "ask.placeholder": "например: Когда вносится арендная плата? / Ijara haqi qachon toʻlanadi?",
  "ask.hint": "Спрашивайте на узбекском (латиница или кириллица) или русском. Enter — отправить, Shift+Enter — новая строка.",
  "ask.corpus": "Коллекция",
  "ask.scope": "Искать в",
  "ask.scopeAll": "Во всех документах",
  "ask.submit": "Спросить",
  "ask.loading": "Поиск…",

  "corpus.real": "Реальные документы",
  "corpus.synthetic": "Синтетические (тестовые) документы",

  "chat.thread": "Вопросы и результаты",
  "chat.you": "Ваш вопрос",
  "chat.scope": "В документе: {title}",
  "chat.independent": "Каждый вопрос ищется отдельно; предыдущие вопросы не учитываются.",

  "results.heading": "Фрагменты по запросу: «{question}»",
  "results.count": "Фрагментов: {n}",
  "results.empty": "Ничего не найдено. Попробуйте другие слова или поиск по всем документам.",
  "results.check": "Цитаты сверены с текстом источника: {valid} из {checked}",
  "results.extractiveNote": "Точные выдержки из текста источника в порядке соответствия вопросу. Это результат поиска, а не сгенерированный ответ и не юридическая консультация.",
  "results.answerLabel": "Ответ",
  "results.answerNote": "Сформирован по выдержкам ниже. Сверьте цитаты, прежде чем на него полагаться.",
  "results.sources": "Источники",
  "results.copy": "Копировать",
  "results.copied": "Скопировано",
  "results.copyFailed": "Не удалось скопировать",
  "results.searchAll": "Искать во всех документах",
  "results.tech": "Техническая информация",

  "tech.mode": "Режим ответа",
  "tech.retriever": "Ретривер",
  "tech.corpus": "Коллекция",
  "tech.check": "Проверка цитат",
  "tech.checkValue": "корректны {valid} из {checked}",
  "tech.chunks": "Идентификаторы фрагментов",

  "result.article": "Статья",
  "result.source": "Открыть оригинал",
  "result.noSource": "Нет онлайн-источника",
  "result.notExact": "Цитату не удалось найти во фрагменте, поэтому она показана отдельно.",
  "result.quote": "Цитата",
  "result.expand": "Показать фрагмент полностью",
  "result.collapse": "Свернуть",
  "result.view": "Открыть в контексте",
  "result.copyQuote": "Копировать цитату",
  "result.cited": "Процитировано в ответе",

  "viewer.title": "Источник",
  "viewer.close": "Закрыть просмотр источника",
  "viewer.loading": "Загрузка текста…",
  "viewer.range": "Фрагменты {from}–{to} из {total}",
  "viewer.earlier": "Показать текст выше",
  "viewer.later": "Показать текст ниже",
  "viewer.fallback": "Можно показать только этот фрагмент: сервер не вернул окружающий текст.",
  "viewer.start": "Начало документа",
  "viewer.end": "Конец документа",
  "viewer.quoted": "Процитированный фрагмент",

  "docs.heading": "Документы",
  "docs.subtitle": "Документы, по которым выполняется поиск.",
  "docs.search": "Поиск по названию",
  "docs.filterLang": "Язык",
  "docs.filterKind": "Тип",
  "docs.all": "Все",
  "docs.noMatch": "Нет документов, подходящих под эти фильтры.",
  "docs.reset": "Сбросить фильтры",
  "docs.loading": "Загрузка документов…",
  "docs.empty": "В этой коллекции пока нет документов. Загрузите их командой «documind ingest».",
  "docs.chunks": "Фрагментов: {n}",
  "docs.edition": "Редакция: {edition}",
  "docs.source": "Источник",
  "docs.askHere": "Искать только здесь",
  "docs.selected": "Выбран",
  "docs.synthetic": "синтетический",
  "docs.structure": "Структура",
  "docs.back": "Назад в библиотеку",
  "docs.outline": "Структура документа",
  "docs.outlineSearch": "Найти раздел",
  "docs.outlineEmpty": "Подходящих разделов нет.",
  "docs.outlineLoading": "Загрузка структуры…",
  "docs.sections": "Разделов: {n}",
  "docs.untitled": "Раздел без названия",

  "language.ru": "Русский",
  "language.uzLatn": "Узбекский (латиница)",
  "language.uzCyrl": "Узбекский (кириллица)",
  "kind.law": "Закон",
  "kind.upload": "Загруженный файл",

  "error.title": "Что-то пошло не так",
  "error.network": "API недоступен. Проверьте, что сервер запущен (documind serve).",
  "error.unavailable": "В этой коллекции ещё нет загруженных документов.",
  "error.not_found": "Этого документа нет в выбранной коллекции.",
  "error.invalid": "Вопрос не принят. Проверьте его длину и попробуйте снова.",
  "error.server": "Сервер вернул ошибку. Попробуйте позже.",
  "error.detail": "Подробности: {detail}",
  "error.retry": "Повторить",

  "health.online": "API доступен",
  "health.ok": "Документов: {documents}, фрагментов: {chunks} · {mode} · {retriever}",
  "health.down": "API недоступен",
  "health.checking": "Подключение…",
};

const uz: Messages = {
  "app.tagline": "Oʻzbekiston qonunchiligidan aniq iqtiboslar bilan javoblar (oʻzbek va rus tillarida)",
  "app.product": "Huquqiy qidiruv ish maydoni",
  "lang.label": "Interfeys tili",

  "nav.label": "Asosiy navigatsiya",
  "nav.newQuery": "Yangi soʻrov",
  "nav.workspace": "Ish maydoni",
  "nav.library": "Hujjatlar kutubxonasi",
  "nav.collapse": "Yon panelni yigʻish",
  "nav.expand": "Yon panelni yoyish",
  "nav.open": "Menyuni ochish",
  "nav.close": "Menyuni yopish",

  "history.heading": "Tarix",
  "history.empty": "Soʻrovlaringiz shu yerda koʻrinadi.",
  "history.note": "Faqat shu brauzerda saqlanadi.",
  "history.delete": "“{title}”ni oʻchirish",
  "history.clear": "Tozalash",
  "history.clearConfirm": "Hammasi oʻchirilsinmi?",

  "settings.heading": "Sozlamalar",
  "theme.label": "Mavzu",
  "theme.dark": "Tungi",
  "theme.light": "Yorugʻ",
  "theme.system": "Tizim",

  "welcome.title": "Qonunchilikdan nimani topmoqchisiz?",
  "welcome.subtitle": "DocuMind Oʻzbekiston qonunchiligi boʻyicha qidiradi va savolingizga mos aniq parchalarni manbaga havola bilan qaytaradi.",
  "welcome.examples": "Misolni sinab koʻring",
  "feature.quotes.title": "Aniq iqtiboslar",
  "feature.quotes.text": "Har bir natija — manba matni bilan tekshirilgan soʻzma-soʻz parcha.",
  "feature.languages.title": "Oʻzbek va rus tillari",
  "feature.languages.text": "Oʻzbek (lotin yoki kirill) yoki rus tilida soʻrang.",
  "feature.sources.title": "Tekshiriladigan manbalar",
  "feature.sources.text": "Parchani kontekstda oʻqing va asl manbani oching.",

  "ask.label": "Savolingiz",
  "ask.placeholder": "masalan: Ijara haqi qachon toʻlanadi? / Когда вносится арендная плата?",
  "ask.hint": "Oʻzbek (lotin yoki kirill) yoki rus tilida soʻrang. Enter — yuborish, Shift+Enter — yangi qator.",
  "ask.corpus": "Toʻplam",
  "ask.scope": "Qayerda qidirish",
  "ask.scopeAll": "Barcha hujjatlarda",
  "ask.submit": "Soʻrash",
  "ask.loading": "Qidirilmoqda…",

  "corpus.real": "Haqiqiy hujjatlar",
  "corpus.synthetic": "Sintetik (sinov) hujjatlar",

  "chat.thread": "Savollar va natijalar",
  "chat.you": "Savolingiz",
  "chat.scope": "Hujjatda: {title}",
  "chat.independent": "Har bir savol alohida qidiriladi; oldingi savollar hisobga olinmaydi.",

  "results.heading": "Soʻrov boʻyicha parchalar: “{question}”",
  "results.count": "Parchalar: {n}",
  "results.empty": "Hech narsa topilmadi. Boshqa soʻzlarni sinab koʻring yoki barcha hujjatlarda qidiring.",
  "results.check": "Iqtiboslar manba matni bilan tekshirildi: {checked} tadan {valid} tasi",
  "results.extractiveNote": "Manba matnidan savolga mosligi tartibidagi aniq parchalar. Bu qidiruv natijasi boʻlib, yaratilgan javob yoki yuridik maslahat emas.",
  "results.answerLabel": "Javob",
  "results.answerNote": "Quyidagi parchalar asosida tuzilgan. Unga tayanishdan oldin iqtiboslarni tekshiring.",
  "results.sources": "Manbalar",
  "results.copy": "Nusxalash",
  "results.copied": "Nusxalandi",
  "results.copyFailed": "Nusxalab boʻlmadi",
  "results.searchAll": "Barcha hujjatlarda qidirish",
  "results.tech": "Texnik maʼlumot",

  "tech.mode": "Javob rejimi",
  "tech.retriever": "Retriver",
  "tech.corpus": "Toʻplam",
  "tech.check": "Iqtiboslarni tekshirish",
  "tech.checkValue": "{checked} tadan {valid} tasi toʻgʻri",
  "tech.chunks": "Parcha identifikatorlari",

  "result.article": "Modda",
  "result.source": "Asl manbani ochish",
  "result.noSource": "Onlayn manba yoʻq",
  "result.notExact": "Iqtibos parcha ichida topilmadi, shuning uchun alohida koʻrsatilgan.",
  "result.quote": "Iqtibos",
  "result.expand": "Parchani toʻliq koʻrsatish",
  "result.collapse": "Yigʻish",
  "result.view": "Kontekstda ochish",
  "result.copyQuote": "Iqtibosni nusxalash",
  "result.cited": "Javobda iqtibos keltirilgan",

  "viewer.title": "Manba",
  "viewer.close": "Manba koʻrinishini yopish",
  "viewer.loading": "Matn yuklanmoqda…",
  "viewer.range": "Parchalar {from}–{to}, jami {total}",
  "viewer.earlier": "Oldingi matnni koʻrsatish",
  "viewer.later": "Keyingi matnni koʻrsatish",
  "viewer.fallback": "Faqat shu parchani koʻrsatish mumkin: server atrofdagi matnni qaytarmadi.",
  "viewer.start": "Hujjat boshi",
  "viewer.end": "Hujjat oxiri",
  "viewer.quoted": "Iqtibos keltirilgan parcha",

  "docs.heading": "Hujjatlar",
  "docs.subtitle": "Qidiruv olib boriladigan hujjatlar.",
  "docs.search": "Nomi boʻyicha qidirish",
  "docs.filterLang": "Til",
  "docs.filterKind": "Turi",
  "docs.all": "Barchasi",
  "docs.noMatch": "Bu filtrlarga mos hujjat yoʻq.",
  "docs.reset": "Filtrlarni tozalash",
  "docs.loading": "Hujjatlar yuklanmoqda…",
  "docs.empty": "Bu toʻplamda hali hujjat yoʻq. Hujjatlarni “documind ingest” buyrugʻi bilan yuklang.",
  "docs.chunks": "Parchalar: {n}",
  "docs.edition": "Tahrir: {edition}",
  "docs.source": "Manba",
  "docs.askHere": "Faqat shu yerda qidirish",
  "docs.selected": "Tanlangan",
  "docs.synthetic": "sintetik",
  "docs.structure": "Tuzilishi",
  "docs.back": "Kutubxonaga qaytish",
  "docs.outline": "Hujjat tuzilishi",
  "docs.outlineSearch": "Boʻlimni topish",
  "docs.outlineEmpty": "Mos boʻlim yoʻq.",
  "docs.outlineLoading": "Tuzilish yuklanmoqda…",
  "docs.sections": "Boʻlimlar: {n}",
  "docs.untitled": "Nomsiz boʻlim",

  "language.ru": "Rus tili",
  "language.uzLatn": "Oʻzbek tili (lotin)",
  "language.uzCyrl": "Oʻzbek tili (kirill)",
  "kind.law": "Qonun",
  "kind.upload": "Yuklangan fayl",

  "error.title": "Xatolik yuz berdi",
  "error.network": "API bilan bogʻlanib boʻlmadi. Server ishga tushirilganini tekshiring (documind serve).",
  "error.unavailable": "Bu toʻplamga hali hujjat yuklanmagan.",
  "error.not_found": "Bu hujjat tanlangan toʻplamda yoʻq.",
  "error.invalid": "Savol qabul qilinmadi. Uzunligini tekshirib, qayta urinib koʻring.",
  "error.server": "Server xato qaytardi. Keyinroq urinib koʻring.",
  "error.detail": "Tafsilotlar: {detail}",
  "error.retry": "Qayta urinish",

  "health.online": "API ishlayapti",
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

const LANGUAGE_KEYS: Record<string, MessageKey> = {
  ru: "language.ru",
  "uz-Latn": "language.uzLatn",
  "uz-Cyrl": "language.uzCyrl",
};

const KIND_KEYS: Record<string, MessageKey> = { law: "kind.law", upload: "kind.upload" };

/** Message key of a document language code; null for a code without a translation
 * (the UI then shows the code itself). */
export function languageKey(code: string): MessageKey | null {
  return LANGUAGE_KEYS[code] ?? null;
}

/** Message key of a document type; null for a type without a translation. */
export function kindKey(kind: string): MessageKey | null {
  return KIND_KEYS[kind] ?? null;
}
