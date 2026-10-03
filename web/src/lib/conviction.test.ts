import { convictionLabel, convictionTitle, sparkColor } from "./conviction";

describe("convictionLabel", () => {
  it("badges only the tiers that need explaining", () => {
    expect(convictionLabel("high")).toBe("Strong");
    expect(convictionLabel("low")).toBe("Weaker");
    expect(convictionLabel("standard")).toBeNull();
  });
});

describe("convictionTitle", () => {
  it("explains a weak short in terms of the backtest", () => {
    expect(convictionTitle("low", "SELL")).toMatch(/did not beat holding cash/);
  });

  it("does not claim the short result for a weak long", () => {
    expect(convictionTitle("low", "BUY")).not.toMatch(/holding cash/);
  });

  it("says nothing for an ordinary signal", () => {
    expect(convictionTitle("standard", "BUY")).toBe("");
  });
});

describe("sparkColor", () => {
  it("keeps the buy/sell colours for signals that carry an edge", () => {
    expect(sparkColor("BUY", "standard")).toBe("#27694B");
    expect(sparkColor("SELL", "standard")).toBe("#9E2F45");
    expect(sparkColor("BUY", "high")).toBe("#27694B");
  });

  it("mutes low conviction regardless of side", () => {
    expect(sparkColor("BUY", "low")).toBe(sparkColor("SELL", "low"));
    expect(sparkColor("SELL", "low")).not.toBe("#9E2F45");
  });
});
