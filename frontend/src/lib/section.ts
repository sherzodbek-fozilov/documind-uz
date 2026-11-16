// The API joins the headings above a passage with " / " (e.g. "Chapter 29 / § 1 /
// Article 386"). The last part is the closest heading, usually the article.

const SEPARATOR = " / ";

export function sectionParts(title: string | null | undefined): string[] {
  if (!title) return [];
  return title.split(SEPARATOR).map((p) => p.trim()).filter(Boolean);
}

/** The closest heading of a passage (its article), or null when it has none. */
export function sectionLeaf(title: string | null | undefined): string | null {
  const parts = sectionParts(title);
  return parts.length ? parts[parts.length - 1] : null;
}

/** The headings above the closest one, outermost first. */
export function sectionParents(title: string | null | undefined): string[] {
  return sectionParts(title).slice(0, -1);
}
