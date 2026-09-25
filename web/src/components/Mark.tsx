// The E-mark's three bars (blue, teal, green) as the deck's status mark.
// Running, the bars breathe out of step; idle, they sit still and quiet.
import type { Status } from "../lib/agents";

const BARS = [
  { width: "100%", color: "var(--color-brand)", delay: "0s" },
  { width: "70%", color: "var(--color-teal)", delay: ".18s" },
  { width: "100%", color: "var(--color-green)", delay: ".36s" },
];

export function LiveMark({ status = "run", className = "h-3 w-3.5" }: { status?: Status; className?: string }) {
  const running = status === "run";
  const tone =
    status === "idle" ? "opacity-35 grayscale" : status === "warn" ? "[&>i]:!bg-warn-rule" : status === "error" ? "[&>i]:!bg-err-ink" : "";
  return (
    <span aria-hidden className={`inline-flex flex-col justify-between ${className} ${tone}`}>
      {BARS.map((b, i) => (
        <i key={i} className={`block h-[22%] origin-left rounded-full ${running ? "animate-bars" : ""}`}
          style={{ width: b.width, background: b.color, animationDelay: b.delay }} />
      ))}
    </span>
  );
}
