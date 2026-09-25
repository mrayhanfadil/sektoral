// One drawn icon family (24px grid, 2px round stroke) instead of Unicode glyphs.
const PATHS = {
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  crosscheck: <><path d="M7 7h11l-3-3" /><path d="M17 17H6l3 3" /></>,
  skip: <><path d="M5 5v6a4 4 0 0 0 4 4h10" /><path d="m15 11 4 4-4 4" /></>,
  alert: <><path d="M12 8v5" /><path d="M12 16.5v.01" /></>,
  x: <path d="m7 7 10 10M17 7 7 17" />,
  dot: <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none" />,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" /></>,
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" />,
  system: <><rect x="3" y="4.5" width="18" height="12" rx="2" /><path d="M8.5 20h7M12 16.5V20" /></>,
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  split: <><path d="M4 6h16M4 12h10M4 18h7" /><path d="m17 15 3 3-3 3" /></>,
  ban: <><circle cx="12" cy="12" r="9" /><path d="m5.6 5.6 12.8 12.8" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.01" /></>,
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, className = "size-4" }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true" className={className}>
      {PATHS[name]}
    </svg>
  );
}
