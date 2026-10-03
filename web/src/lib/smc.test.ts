import { SMC_COLORS, smc } from "./smc";
import type { ChartFile } from "../types";

type Bar = ChartFile["bars"][number];

/**
 * Bars from a close path, opening at the previous close and wicking in the direction they
 * came from. The asymmetry matters: the confluence filter compares the upper wick against
 * `open - low`, so bars with symmetric wicks never pass it and no internal structure forms.
 */
function path(closes: number[]): Bar[] {
  return closes.map((c, i) => {
    const o = i === 0 ? c : closes[i - 1];
    const up = c >= o;
    return [i + 1, o, Math.max(o, c) + (up ? 1.5 : 0.05), Math.min(o, c) - (up ? 0.05 : 1.5), c, 1000] as Bar;
  });
}

/** `n` bars drifting a cent either way, so no pivot can form inside them. */
const flat = (n: number, at: number) => Array.from({ length: n }, (_, i) => at + (i % 2) * 0.01);

const opts = { swingLength: 5, internalLength: 3, internalObCount: 5 };

/** Rally to 120, pull back to 110, break out to 130. */
const rally = path([...flat(8, 100), 120, ...flat(8, 110), 130, ...flat(8, 130)]);
/** The same, then a collapse through the swing low to 60. */
const reversal = path([...flat(8, 100), 120, ...flat(8, 110), 130, ...flat(8, 130), 80, ...flat(8, 85), 60, ...flat(8, 60)]);

describe("swing structure", () => {
  it("marks a BOS when price closes back above a confirmed swing high", () => {
    const bos = smc(rally, opts).structure;
    expect(bos).toHaveLength(1);
    expect(bos[0].tag).toBe("BOS");
    expect(bos[0].price).toBe(121.5); // the pivot bar's high, not its close
    expect(bos[0].color).toBe(SMC_COLORS.bull);
  });

  it("calls the first break against an established trend a CHoCH, then BOS again", () => {
    const s = smc(reversal, opts).structure;
    expect(s.map((x) => x.tag)).toEqual(["BOS", "CHoCH", "BOS"]);
    expect(s[1].color).toBe(SMC_COLORS.bear);
    expect(s[2].color).toBe(SMC_COLORS.bear); // trend already bearish, so the next break continues it
  });

  it("draws each structure line from its pivot bar to the bar whose close broke it", () => {
    const [line] = smc(rally, opts).structure;
    expect(line.from).toBe(8); // the bar that closed at 120
    expect(line.to).toBe(17); // the bar that closed at 130
  });

  it("returns nothing at all for a chart with no confirmed pivots", () => {
    expect(smc(path(flat(20, 100)), opts)).toEqual({ structure: [], orderBlocks: [], fvgs: [], zones: [], trailing: [] });
  });

  it("returns nothing when there are too few bars to confirm one swing", () => {
    expect(smc(path(flat(4, 100)), opts).structure).toEqual([]);
  });
});

describe("fair value gaps", () => {
  const atGap = (f: { from: number }[]) => f.some((x) => x.from === 8);

  it("finds the gap an impulse bar leaves behind", () => {
    const [recent] = smc(rally, opts).fvgs;
    expect(atGap(smc(rally, opts).fvgs)).toBe(true);
    expect(recent.bottom).toBeLessThan(recent.top);
    expect(recent.fill).toBe(SMC_COLORS.bullFvg);
  });

  it("extends a gap one bar past the candle that completed it", () => {
    const g = smc(rally, opts).fvgs.find((x) => x.from === 8)!;
    expect(g.to).toBe(10); // confirmed on bar 9, extended by one bar
  });

  it("drops a bullish gap once price trades back below it", () => {
    const filled = smc(path([...flat(8, 100), 120, ...flat(3, 120), 99, ...flat(4, 99)]), opts).fvgs;
    expect(atGap(filled)).toBe(false);
  });
});

describe("internal order blocks", () => {
  // 120, a dip to 95, back to 110, then a break to 130: the 95 bar is the block.
  const dip = [...flat(8, 100), 120, 110, 95, 110, ...flat(5, 110), 130, ...flat(8, 130)];

  it("places the block on the lowest bar between the broken pivot and the break", () => {
    const obs = smc(path(dip), opts).orderBlocks;
    expect(obs).toHaveLength(1);
    expect(obs[0].from).toBe(10); // the bar that closed at 95
    expect(obs[0].bottom).toBe(93.5);
    expect(obs[0].top).toBe(110.05);
    expect(obs[0].fill).toBe(SMC_COLORS.internalBullOb);
  });

  it("extends blocks to the right edge rather than ending them", () => {
    expect(smc(path(dip), opts).orderBlocks.every((b) => b.to === null)).toBe(true);
  });

  it("drops a bullish block once price trades below its low", () => {
    expect(smc(path([...dip, 90, ...flat(4, 90)]), opts).orderBlocks).toEqual([]);
  });

  it("keeps no more blocks than asked for", () => {
    expect(smc(path(dip), { ...opts, internalObCount: 0 }).orderBlocks).toEqual([]);
  });
});

describe("premium / discount zones and trailing extremes", () => {
  it("splits the trailing range into premium, equilibrium and discount", () => {
    const [prem, eq, disc] = smc(rally, opts).zones;
    expect([prem.label, eq.label, disc.label]).toEqual(["Premium", "Equilibrium", "Discount"]);
    expect(prem.bottom).toBeCloseTo(0.95 * prem.top + 0.05 * disc.bottom, 6);
    expect(disc.top).toBeCloseTo(0.95 * disc.bottom + 0.05 * prem.top, 6);
    expect(eq.labelPrice).toBeCloseTo((prem.top + disc.bottom) / 2, 6);
  });

  it("labels the trailing extremes strong or weak according to the swing trend", () => {
    expect(smc(rally, opts).trailing.map((x) => x.text)).toEqual(["Weak High", "Strong Low"]);
    expect(smc(reversal, opts).trailing.map((x) => x.text)).toEqual(["Strong High", "Weak Low"]);
  });

  it("colours the trailing high red and the trailing low green", () => {
    const [high, low] = smc(rally, opts).trailing;
    expect(high.color).toBe(SMC_COLORS.bear);
    expect(low.color).toBe(SMC_COLORS.bull);
  });
});
