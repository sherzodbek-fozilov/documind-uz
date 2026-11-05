/**
 * Split a passage into the text before the quote, the quote and the text after it.
 *
 * The API guarantees quote == text[quote_start:quote_end]. The UI still checks it and
 * never highlights text that is not the exact quote:
 * 1. offsets match -> use them;
 * 2. otherwise, if the quote occurs verbatim in the text -> use its first occurrence;
 * 3. otherwise -> no highlight (`exact: false`), the UI shows the quote separately.
 */
export interface Highlight {
  before: string;
  quote: string;
  after: string;
  exact: boolean;
}

export function splitAroundQuote(
  text: string,
  quote: string,
  start: number,
  end: number,
): Highlight {
  if (quote && Number.isInteger(start) && Number.isInteger(end) && 0 <= start && start < end
      && end <= text.length && text.slice(start, end) === quote) {
    return { before: text.slice(0, start), quote, after: text.slice(end), exact: true };
  }
  const i = quote ? text.indexOf(quote) : -1;
  if (i >= 0) {
    return {
      before: text.slice(0, i),
      quote,
      after: text.slice(i + quote.length),
      exact: true,
    };
  }
  return { before: text, quote: "", after: "", exact: false };
}

/**
 * Shorten long context around the quote so a result card stays readable; the quote
 * itself is never cut. `max` is the number of characters kept on each side.
 */
export function trimContext(h: Highlight, max = 300): Highlight {
  if (!h.exact) return h;
  const cutBefore = h.before.length > max;
  const cutAfter = h.after.length > max;
  return {
    ...h,
    before: cutBefore ? `…${h.before.slice(h.before.length - max).replace(/^\S*\s/, "")}` : h.before,
    after: cutAfter ? `${h.after.slice(0, max).replace(/\s\S*$/, "")}…` : h.after,
  };
}
