// Issuer logos, saved from each company's own website into web/public/logos.
// They sit on a small white plate so every mark reads in light and dark mode;
// an issuer without a logo gets nothing (the ticker beside it already names it).
const FILES: Record<string, string> = {
  AMMN: "AMMN.png", BBCA: "BBCA.svg", BBRI: "BBRI.webp", GMFI: "GMFI.png", INET: "INET.png",
  JPFA: "JPFA.svg", POWR: "POWR.png", SIDO: "SIDO.png", SSIA: "SSIA.webp",
};

export function hasLogo(ticker: string) {
  return ticker.toUpperCase() in FILES;
}

/** The issuer's logo on a white plate; `size` sets the plate height. */
export function IssuerLogo({ ticker, size = "md", className = "" }:
  { ticker: string; size?: "sm" | "md" | "lg"; className?: string }) {
  const file = FILES[ticker.toUpperCase()];
  if (!file) return null;
  const plate = { sm: "h-7 w-[64px] px-1.5", md: "h-9 w-[88px] px-2", lg: "h-12 w-[120px] px-2.5" }[size];
  return (
    <span className={`inline-flex flex-none items-center justify-center rounded-md bg-white ring-1 ring-rule ${plate} ${className}`}>
      <img src={`/logos/${file}`} alt="" aria-hidden loading="lazy" decoding="async"
        className="max-h-[70%] max-w-full object-contain" />
    </span>
  );
}
