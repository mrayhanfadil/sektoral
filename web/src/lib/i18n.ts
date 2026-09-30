import { useCallback, useSyncExternalStore } from "react";

// Two languages, Bahasa Indonesia and English. Strings sit next to the code
// that shows them as a pair, `{ id: "…", en: "…" }`, so the type checker
// refuses a string that exists in one language only.

export type Lang = "id" | "en";
/** One value per language. */
export type Bi<T = string> = Record<Lang, T>;

export const LANGS: readonly Lang[] = ["id", "en"];
/** The Intl locale that formats dates and numbers for each language. */
export const LOCALE: Bi = { id: "id-ID", en: "en-US" };

const KEY = "sectoral-lang";

/**
 * The reader's language from their browser settings: the first Indonesian or
 * English entry in their preference list wins; neither means English.
 */
export function detectLang(languages: readonly string[]): Lang {
  for (const tag of languages) {
    const base = tag.toLowerCase().split(/[-_]/)[0];
    // "in" is the old ISO code for Indonesian that some systems still send.
    if (base === "id" || base === "in") return "id";
    if (base === "en") return "en";
  }
  return "en";
}

function browserLang(): Lang {
  if (typeof navigator === "undefined") return "en";
  return detectLang(navigator.languages?.length ? navigator.languages : [navigator.language ?? ""]);
}

function readSaved(): Lang | null {
  try {
    const value = localStorage.getItem(KEY);
    return value === "id" || value === "en" ? value : null;
  } catch {
    return null;
  }
}

let current: Lang = readSaved() ?? browserLang();
const listeners = new Set<() => void>();

function applyDocument(lang: Lang) {
  if (typeof document !== "undefined") document.documentElement.lang = lang;
}
applyDocument(current);

/** The active language, for code outside React components. */
export function getLang(): Lang {
  return current;
}

/** Switch language and keep the choice in this browser. */
export function setLang(lang: Lang) {
  try {
    localStorage.setItem(KEY, lang);
  } catch {
    /* storage unavailable: the choice lasts for this page only */
  }
  if (lang === current) return;
  current = lang;
  applyDocument(lang);
  listeners.forEach((fn) => fn());
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Pick the value for a language (the active one by default). */
export function pick<T>(bi: Bi<T>, lang: Lang = current): T {
  return bi[lang];
}

/**
 * Server text in the reader's language. Agents and host code write Indonesian
 * `<key>` and, where they have one, an English `<key>_en` beside it (a
 * parallel list for a list of strings, a parallel grid for table rows).
 * English readers get the twin where it is present and the Indonesian where
 * it is not, string by string; Indonesian readers always get `<key>`.
 */
export function twin<T extends object, K extends keyof T & string>(obj: T, key: K, lang: Lang = current): T[K] {
  const id = obj[key];
  if (lang !== "en") return id;
  return paired(id, (obj as Record<string, unknown>)[`${key}_en`]) as T[K];
}

function paired(id: unknown, en: unknown): unknown {
  if (Array.isArray(id)) return Array.isArray(en) ? id.map((v, i) => paired(v, en[i])) : id;
  return typeof en === "string" && en.trim() !== "" && (id == null || typeof id === "string") ? en : id;
}

/**
 * The active language in a component, re-rendering when it changes.
 * `t({ id, en })` picks the string; `locale` feeds Intl formatters.
 */
export function useLang() {
  const lang = useSyncExternalStore(subscribe, getLang, getLang);
  const t = useCallback(<T,>(bi: Bi<T>): T => bi[lang], [lang]);
  return { lang, t, locale: LOCALE[lang], setLang };
}
