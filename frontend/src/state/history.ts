// Query history. There is no account or server-side storage: sessions are kept in this
// browser's localStorage only, and the UI says so. Storage can be missing, blocked or
// full; history is then simply not kept.
import type { AskResponse, Corpus } from "../api/types";

const STORAGE_KEY = "documind.history.v1";
export const MAX_SESSIONS = 30;

/** One answered question, with the response exactly as the API returned it. */
export interface StoredTurn {
  id: string;
  question: string;
  corpus: Corpus;
  documentId: string | null;
  response: AskResponse;
}

/** The questions asked between two clicks on "New query". */
export interface Session {
  id: string;
  /** the first question */
  title: string;
  updatedAt: number;
  turns: StoredTurn[];
}

export function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function isStoredTurn(v: unknown): v is StoredTurn {
  if (!isRecord(v) || !isRecord(v.response)) return false;
  return typeof v.id === "string" && typeof v.question === "string"
    && (v.corpus === "real" || v.corpus === "synthetic")
    && (v.documentId === null || typeof v.documentId === "string")
    && Array.isArray(v.response.passages) && isRecord(v.response.citation_check);
}

function isSession(v: unknown): v is Session {
  return isRecord(v) && typeof v.id === "string" && typeof v.title === "string"
    && typeof v.updatedAt === "number" && Array.isArray(v.turns) && v.turns.length > 0
    && v.turns.every(isStoredTurn);
}

/** Stored sessions, newest first; anything that is not a valid session is dropped. */
export function loadHistory(): Session[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter(isSession).slice(0, MAX_SESSIONS) : [];
  } catch {
    return [];
  }
}

/** Save the sessions; when the storage is full, the oldest ones are dropped until it fits. */
export function saveHistory(sessions: Session[]): void {
  let keep = sessions.slice(0, MAX_SESSIONS);
  for (;;) {
    try {
      if (keep.length) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(keep));
      else window.localStorage.removeItem(STORAGE_KEY);
      return;
    } catch {
      if (keep.length <= 1) return;
      keep = keep.slice(0, Math.ceil(keep.length / 2));
    }
  }
}

/** Put a session first, replacing an earlier version of it. */
export function upsertSession(sessions: Session[], session: Session): Session[] {
  return [session, ...sessions.filter((s) => s.id !== session.id)].slice(0, MAX_SESSIONS);
}
