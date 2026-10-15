/** Number formatting for the Lab tab, in one place so signs, bps and percentages agree.
 *  A missing figure is an em dash, never a blank and never "NaN". */
export const NA = "—";

const ok = (n: number | null | undefined): n is number => typeof n === "number" && Number.isFinite(n);

export const bps = (n: number | null | undefined, digits = 1) =>
  ok(n) ? `${n > 0 ? "+" : ""}${n.toFixed(digits)} bps` : NA;
export const signedPct = (n: number | null | undefined, digits = 2) =>
  ok(n) ? `${n > 0 ? "+" : ""}${n.toFixed(digits)}%` : NA;
export const pctPlain = (n: number | null | undefined, digits = 0) =>
  ok(n) ? `${(n * 100).toFixed(digits)}%` : NA;
export const ratio = (n: number | null | undefined, digits = 2) => (ok(n) ? n.toFixed(digits) : NA);
const usdFmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const usdSigned = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0, signDisplay: "exceptZero" });
export const usd = (n: number | null | undefined) => (ok(n) ? usdFmt.format(n) : NA);
export const signedUsd = (n: number | null | undefined) => (ok(n) ? usdSigned.format(n) : NA);
export const px = (n: number | null | undefined) => (ok(n) ? n.toFixed(2) : NA);

/** buy/sell colour class for a signed number; zero and missing are neutral. */
export const toneClass = (n: number | null | undefined) => (!ok(n) || n === 0 ? "" : n > 0 ? "buy-text" : "sell-text");

export const shortDay = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
export const stamp = (iso: string) =>
  new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" });
export const hourLabel = (h: string) => {
  const n = Number(h);
  return `${n % 12 === 0 ? 12 : n % 12}${n < 12 ? "a" : "p"}`;
};
