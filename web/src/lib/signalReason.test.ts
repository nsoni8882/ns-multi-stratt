import { describe, expect, it } from "vitest";
import { signalReason } from "./signalReason";
import { row } from "../test-fixtures";

describe("signalReason", () => {
  it("describes a trend pullback BUY with the level that fired it", () => {
    const text = signalReason("trend-pullback", row({ side: "BUY", details: { rsi: 42.93, rsi_level: 40 } }));
    expect(text).toBe(
      "Pullback in an uptrend: price and the 50 EMA above the 200 EMA, " +
        "RSI(14) crossed back above 40 to 42.9.",
    );
  });

  it("mirrors the wording for a SELL", () => {
    const text = signalReason("trend-pullback", row({ side: "SELL", details: { rsi: 57.4, rsi_level: 60 } }));
    expect(text).toContain("Bounce in a downtrend");
    expect(text).toContain("crossed back below 60 to 57.4");
  });

  it("names the MACD histogram for the reversal strategy", () => {
    const text = signalReason("macd-rsi-reversal", row({ side: "BUY", details: { rsi: 23.4, rsi_level: 20, macd_hist: -1.2 } }));
    expect(text).toBe(
      "Selling exhausted: MACD histogram turning up from a deep low, " +
        "RSI(14) crossed back above 20 to 23.4.",
    );
  });

  it("reads without the threshold, for data cached before rsi_level shipped", () => {
    const text = signalReason("trend-pullback", row({ side: "BUY", details: { rsi: 42.93 } }));
    expect(text).toContain("crossed back above its trigger level to 42.9");
  });

  it("falls back to a generic line for an unknown strategy", () => {
    expect(signalReason("whatever", row({ side: "SELL", details: {} }))).toBe(
      "Every condition this strategy requires for a SELL was met on this candle.",
    );
  });
});
