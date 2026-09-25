// Numbers read the same as in the reports (app/fmt.py): Indonesian
// separators, "n.a." when missing, and a true minus sign for negatives.

const whole = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function rp(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? whole.format(value) : "n.a.";
}

/** ``value`` is already in percent (e.g. -20.9 for -20,9%). */
export function pct(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return oneDecimal.format(value).replace("-", "−") + "%";
}
