/** The URL if it is an absolute http(s) URL, otherwise null; links are never built from
 * other schemes (javascript:, data:, a file path stored as the "source"). */
export function safeHttpUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}
