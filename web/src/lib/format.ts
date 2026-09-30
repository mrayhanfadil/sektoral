import { getLang, LOCALE, type Lang } from "./i18n";

// Numbers read the same as in the reports (app/fmt.py): the language's
// separators, "n.a." when missing, and a true minus sign for negatives.

const whole = {
  id: new Intl.NumberFormat(LOCALE.id, { maximumFractionDigits: 0 }),
  en: new Intl.NumberFormat(LOCALE.en, { maximumFractionDigits: 0 }),
};
const oneDecimal = {
  id: new Intl.NumberFormat(LOCALE.id, { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
  en: new Intl.NumberFormat(LOCALE.en, { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
};

export function rp(value: number | null | undefined, lang: Lang = getLang()): string {
  return typeof value === "number" && Number.isFinite(value) ? whole[lang].format(value) : "n.a.";
}

/** ``value`` is already in percent (e.g. -20.9 for -20,9%). */
export function pct(value: number | null | undefined, lang: Lang = getLang()): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return oneDecimal[lang].format(value).replace("-", "−") + "%";
}
