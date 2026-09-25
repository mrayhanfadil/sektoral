// One Method Gate as a fixed instrument: a thin meter that settles, damped,
// into the colour of its verdict. Used by the landing reel and the framework
// section so both read the same way.
import { motion, useReducedMotion } from "motion/react";
import type { GateState } from "../../lib/agents";

type GateStatus = GateState["status"];

export const GATE_TONE: Record<GateStatus, { bar: string; text: string }> = {
  idle: { bar: "transparent", text: "text-ink-faint" },
  ok: { bar: "var(--color-teal)", text: "text-done" },
  warn: { bar: "var(--color-warn-rule)", text: "text-warn-ink" },
  skip: { bar: "var(--color-rule-strong)", text: "text-ink-soft" },
};

/** Settles slowly and never overshoots (high damping, no bounce). */
export const SETTLE = { type: "spring", stiffness: 70, damping: 30, mass: 1 } as const;

export function GateMeter({ status, className = "h-[3px]" }: { status: GateStatus; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <span aria-hidden className={`block overflow-hidden rounded-full bg-rule-soft ${className}`}>
      <motion.span className="block h-full origin-left rounded-full" style={{ background: GATE_TONE[status].bar }}
        initial={false} animate={{ scaleX: status === "idle" ? 0 : 1 }}
        transition={reduce ? { duration: 0 } : SETTLE} />
    </span>
  );
}
