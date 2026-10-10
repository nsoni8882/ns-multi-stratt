/** Shared number formatting for the paper-trading panels.
 *
 *  Every nullable figure goes through <Figure>: a missing value is an em dash carrying a
 *  reason, never a blank and never a literal "--". A literal double hyphen once shipped in
 *  the history overlay and every test accepted it, which is why there is a test for it here.
 */
export const money = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumFractionDigits: 0,
});
export const signedMoney = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumFractionDigits: 0, signDisplay: "always",
});
export const price = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2,
});

export const pct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

/** buy/sell colouring for a signed number. Zero is neutral: it is not a gain. */
export const tone = (n: number) => (n === 0 ? "" : n > 0 ? " buy-text" : " sell-text");

export function Figure({ value, format, why }: {
  value: number | null | undefined;
  format: (n: number) => string;
  why: string;
}) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return <span className="muted" title={why}>&mdash;</span>;
  }
  return <>{format(value)}</>;
}
