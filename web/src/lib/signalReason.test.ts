import { describe, expect, it } from "vitest";
import { signalReason } from "./signalReason";
import { row } from "../test-fixtures";

// The point of these is that two signals from the same strategy read differently, so the
// numbers below are the ones a scanner run actually records on a signal bar.
describe("signalReason", () => {
  it("describes a trend pullback BUY with this name's own dip", () => {
    const text = signalReason("trend-pullback", row({
      side: "BUY",
      details: { rsi: 42.93, rsi_level: 40, rsi_trough: 34.21, dip_bars: 6, above_ema50: 0.018, above_ema200: 0.094 },
    }));
    expect(text).toBe(
      "Pullback in an uptrend: price 1.8% above the 50 EMA, 9.4% above the 200 EMA. " +
        "RSI(14) spent 6 bars under 40, troughed at 34.2, and crossed back above 40 to 42.9.",
    );
  });

  it("gives a shallower pullback in the same strategy a different line", () => {
    const text = signalReason("trend-pullback", row({
      side: "BUY",
      details: { rsi: 41.1, rsi_level: 40, rsi_trough: 39.4, dip_bars: 1, above_ema50: -0.004, above_ema200: 0.031 },
    }));
    expect(text).toContain("0.4% below the 50 EMA");
    expect(text).toContain("spent 1 bar under 40, troughed at 39.4");
  });

  it("mirrors the wording for a SELL", () => {
    const text = signalReason("trend-pullback", row({
      side: "SELL",
      details: { rsi: 57.4, rsi_level: 60, rsi_trough: 61.8, dip_bars: 3 },
    }));
    expect(text).toContain("Bounce in a downtrend");
    expect(text).toContain("spent 3 bars over 60, peaked at 61.8");
    expect(text).toContain("crossed back below 60 to 57.4");
  });

  it("describes a reversal BUY with the size of the decline it is turning out of", () => {
    const text = signalReason("macd-rsi-reversal", row({
      side: "BUY",
      details: { rsi: 30.0, rsi_level: 25, macd_hist: -0.41, hist_trough: -1.2, recovery_bars: 3, rsi_trough: 18.4, off_high: -0.123 },
    }));
    expect(text).toBe(
      "Down 12.3% from its recent high, RSI(14) bottoming at 18.4. " +
        "Downside momentum fading: MACD histogram up 3 bars from a -1.20 low to -0.41, " +
        "and RSI crossed back above 25 to 30.0.",
    );
  });

  it("does not claim selling was exhausted, because nothing here reads volume", () => {
    const text = signalReason("macd-rsi-reversal", row({ side: "BUY", details: { rsi: 30, rsi_level: 25 } }));
    expect(text).not.toContain("exhaust");
  });

  it("reads without the threshold, for data cached before rsi_level shipped", () => {
    const text = signalReason("trend-pullback", row({ side: "BUY", details: { rsi: 42.93 } }));
    expect(text).toBe("Pullback in an uptrend. RSI(14) crossed back above its trigger level to 42.9.");
  });

  it("reads without any of the descriptive fields, for data cached before they shipped", () => {
    const text = signalReason("macd-rsi-reversal", row({ side: "BUY", details: { rsi: 23.4, rsi_level: 20, macd_hist: -1.2 } }));
    expect(text).toBe(
      "Downside momentum fading: MACD histogram up from a deep low to -1.20, " +
        "and RSI(14) crossed back above 20 to 23.4.",
    );
  });

  it("falls back to a generic line for an unknown strategy", () => {
    expect(signalReason("whatever", row({ side: "SELL", details: {} }))).toBe(
      "Every condition this strategy requires for a SELL was met on this candle.",
    );
  });
});
