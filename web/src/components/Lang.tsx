import { useLang } from "../lib/i18n";

/** Switches Bahasa Indonesia ↔ English; the choice is kept in this browser only. */
export function LangToggle() {
  const { lang, t, setLang } = useLang();
  const next = lang === "id" ? "en" : "id";
  const label = t({ id: "Bahasa Indonesia. Ganti ke English", en: "English. Switch to Bahasa Indonesia" });
  return (
    <button type="button" onClick={() => setLang(next)} title={label} aria-label={label}
      className="data grid h-9 min-w-9 cursor-pointer place-items-center rounded-md px-1.5 text-[13px] font-semibold text-ink-soft transition-colors hover:bg-raised hover:text-ink-strong">
      {lang.toUpperCase()}
    </button>
  );
}
