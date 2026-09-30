import { useEffect, useState } from "react";
import { Icon, type IconName } from "./Icon";
import { useLang, type Bi } from "../lib/i18n";

export type ThemePref = "system" | "light" | "dark";
const KEY = "sectoral-theme";
const NEXT: Record<ThemePref, ThemePref> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<ThemePref, Bi> = {
  system: { id: "Tema mengikuti sistem", en: "Theme follows system" },
  light: { id: "Tema terang", en: "Light theme" },
  dark: { id: "Tema gelap", en: "Dark theme" },
};
const ICON: Record<ThemePref, IconName> = { system: "system", light: "sun", dark: "moon" };

function readPref(): ThemePref {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

function apply(pref: ThemePref) {
  const dark = pref === "dark" || (pref === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

/** Cycles system → light → dark; the choice is kept in this browser only. */
export function ThemeToggle() {
  const [pref, setPref] = useState<ThemePref>(readPref);
  const { t } = useLang();
  useEffect(() => {
    apply(pref);
    try {
      if (pref === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, pref);
    } catch {
      /* storage unavailable: the choice lasts for this page only */
    }
    if (pref !== "system") return;
    const media = matchMedia("(prefers-color-scheme: dark)");
    const follow = () => apply("system");
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, [pref]);
  return (
    <button type="button" onClick={() => setPref(NEXT[pref])} title={`${t(LABEL[pref])} ${t({ id: "(klik untuk ganti)", en: "(click to change)" })}`}
      aria-label={`${t(LABEL[pref])}. ${t({ id: "Ganti tema", en: "Change theme" })}`}
      className="grid size-9 cursor-pointer place-items-center rounded-md text-ink-soft transition-colors hover:bg-raised hover:text-ink-strong">
      <Icon name={ICON[pref]} className="size-[19px]" />
    </button>
  );
}
