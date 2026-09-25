import { useEffect, useState } from "react";
import { Icon, type IconName } from "./Icon";

export type ThemePref = "system" | "light" | "dark";
const KEY = "sectoral-theme";
const NEXT: Record<ThemePref, ThemePref> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<ThemePref, string> = {
  system: "Tema mengikuti sistem", light: "Tema terang", dark: "Tema gelap",
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
    <button type="button" onClick={() => setPref(NEXT[pref])} title={`${LABEL[pref]} (klik untuk ganti)`}
      aria-label={`${LABEL[pref]}. Ganti tema`}
      className="grid size-10 cursor-pointer place-items-center rounded-lg text-ink-soft transition-colors hover:bg-canvas hover:text-ink">
      <Icon name={ICON[pref]} className="size-[19px]" />
    </button>
  );
}
