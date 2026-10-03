import type { ChartFile } from "../types";

/**
 * Smart Money Concepts overlay: a port of the LuxAlgo Pine v5 indicator of that name
 * (CC BY-NC-SA 4.0), reduced to the six features the chart actually switches on —
 * swing structure, strong/weak high-low, internal order blocks, fair value gaps and
 * premium/discount zones. Everything else in the original (drawn internal structure,
 * swing order blocks, EQH/EQL, MTF levels, candle colouring, alerts) is left out.
 *
 * It is pure, so it is unit-tested: bars in, drawables out. `smcDraw.ts` renders them.
 *
 * Two deliberate divergences from the Pine, both noted at the site:
 *  - mitigated order blocks are filtered properly rather than through Pine's
 *    remove-while-iterating, which silently skips entries;
 *  - the fair-value-gap auto threshold is a mean over the bars we hold (500), not over
 *    all of a symbol's history, so it is a little more sensitive than TradingView's.
 */

type Bar = ChartFile["bars"][number]; // [time, open, high, low, close, volume]

const BULLISH = 1;
const BEARISH = -1;

/**
 * Order blocks fade slightly with age. LuxAlgo gives every block one colour per bias; this
 * is a deliberate divergence, kept narrow on purpose. Two blocks that overlap still composite
 * to something darker than either, and that overlap — a level reached twice — is the stronger
 * signal, so the age fade must not drown it out.
 */
const OB_ALPHA = { newest: 0.24, oldest: 0.18 };
const OB_RGB = { bull: "49,121,245", bear: "247,124,128" };

/** Fill for the block at `index` of `count`, newest first. */
export function orderBlockFill(bias: "bull" | "bear", index: number, count: number): string {
  const age = count < 2 ? 0 : index / (count - 1);
  const alpha = OB_ALPHA.newest + (OB_ALPHA.oldest - OB_ALPHA.newest) * age;
  return `rgba(${OB_RGB[bias]},${Number(alpha.toFixed(3))})`;
}

/** LuxAlgo's defaults for the settings this chart leaves at their factory values. */
export const SMC_COLORS = {
  bull: "#089981",
  bear: "#F23645",
  /** The freshest shade of each; older blocks are drawn lighter. See orderBlockFill. */
  internalBullOb: orderBlockFill("bull", 0, 1),
  internalBearOb: orderBlockFill("bear", 0, 1),
  bullFvg: "rgba(0,255,104,0.3)",
  bearFvg: "rgba(255,0,8,0.3)",
  premium: "rgba(242,54,69,0.2)",
  equilibrium: "rgba(135,139,148,0.2)",
  discount: "rgba(8,153,129,0.2)",
  premiumText: "#F23645",
  equilibriumText: "#878B94",
  discountText: "#089981",
};

export interface StructureLine {
  /** Bar indices of the pivot bar and of the bar whose close broke it. */
  from: number;
  to: number;
  price: number;
  tag: "BOS" | "CHoCH";
  /** A break upwards through a swing high; the label sits above the line, not below it. */
  bullish: boolean;
  color: string;
}

export interface SmcBox {
  /** Bar indices; they are also lightweight-charts logical coordinates, so a `to` past the
   *  last bar still resolves to an x position. */
  from: number;
  /** null means "extend to the right edge of the pane" (order blocks do). */
  to: number | null;
  top: number;
  bottom: number;
  fill: string;
}

export interface SmcZone extends SmcBox {
  label: string;
  labelPrice: number;
  labelAt: number;
  /** "mid" centres the text on labelAt; "right" ends it there. */
  labelAlign: "mid" | "right";
  labelColor: string;
}

export interface TrailingLine {
  side: "high" | "low";
  from: number;
  price: number;
  text: string;
  color: string;
}

export interface Smc {
  structure: StructureLine[];
  orderBlocks: SmcBox[];
  fvgs: SmcBox[];
  zones: SmcZone[];
  trailing: TrailingLine[];
}

export interface SmcOptions {
  swingLength?: number;
  internalLength?: number;
  internalObCount?: number;
}

const EMPTY: Smc = { structure: [], orderBlocks: [], fvgs: [], zones: [], trailing: [] };

/** Wilder's ATR, seeded by a simple mean of the first `length` true ranges, as ta.atr does.
 *  Null until that seed exists — the volatility filter then simply does not fire. */
function atr(bars: Bar[], length: number): (number | null)[] {
  const out: (number | null)[] = [];
  let sum = 0;
  let prev: number | null = null;
  bars.forEach(([, , high, low], i) => {
    const pc = i === 0 ? null : bars[i - 1][4];
    const tr = pc === null ? high - low : Math.max(high - low, Math.abs(high - pc), Math.abs(low - pc));
    if (i < length) sum += tr;
    if (i < length - 1) out.push(null);
    else if (i === length - 1) {
      prev = sum / length;
      out.push(prev);
    } else {
      prev = ((prev as number) * (length - 1) + tr) / length;
      out.push(prev);
    }
  });
  return out;
}

/**
 * LuxAlgo's `leg()`: 0 once the bar `size` back is the highest of the window that followed
 * it (a pivot high has formed), 1 once it is the lowest (a pivot low). The value only
 * changes when a pivot is confirmed, so a change of +1 is a pivot low and -1 a pivot high.
 */
function legs(bars: Bar[], size: number): number[] {
  const out: number[] = [];
  let leg = 0;
  for (let i = 0; i < bars.length; i++) {
    if (i >= size) {
      let highest = -Infinity;
      let lowest = Infinity;
      for (let j = i - size + 1; j <= i; j++) {
        highest = Math.max(highest, bars[j][2]);
        lowest = Math.min(lowest, bars[j][3]);
      }
      if (bars[i - size][2] > highest) leg = 0;
      else if (bars[i - size][3] < lowest) leg = 1;
    }
    out.push(leg);
  }
  return out;
}

interface Pivot {
  level: number;
  crossed: boolean;
  time: number;
  index: number;
  /** The level as it stood when the previous bar's crossover test ran, which is what
   *  Pine's ta.crossover compares against. */
  seen: number;
}

const pivot = (): Pivot => ({ level: NaN, crossed: false, time: 0, index: 0, seen: NaN });

interface OrderBlock {
  high: number;
  low: number;
  index: number;
  bias: number;
}

interface Gap {
  /** Named as in the Pine: for a bearish gap these are inverted (top < bottom). */
  top: number;
  bottom: number;
  bias: number;
  from: number;
  to: number;
}

/** A pivot, an order block and a gap all carry the bar index they belong to, because the
 *  renderer works in logical coordinates rather than times. */

export function smc(bars: Bar[], options: SmcOptions = {}): Smc {
  const swingLength = options.swingLength ?? 50;
  const internalLength = options.internalLength ?? 5;
  const obCount = options.internalObCount ?? 5;
  if (bars.length <= swingLength + 1) return EMPTY;

  const atr200 = atr(bars, Math.min(200, bars.length));
  const swingLegs = legs(bars, swingLength);
  const internalLegs = legs(bars, internalLength);

  const swingHigh = pivot();
  const swingLow = pivot();
  const internalHigh = pivot();
  const internalLow = pivot();
  let swingTrend = 0;
  let internalTrend = 0;

  // Running extremes since the last swing pivot reset them.
  const trail = { top: NaN, bottom: NaN, barIndex: 0, lastTop: 0, lastBottom: 0 };

  const parsedHighs: number[] = [];
  const parsedLows: number[] = [];
  let orderBlocks: OrderBlock[] = [];
  let gaps: Gap[] = [];
  let cumDelta = 0;

  const structure: StructureLine[] = [];

  /** The pivot the leg change just confirmed, stored and (for swings) used to reset the trail. */
  const takePivot = (i: number, size: number, legSeries: number[], internal: boolean) => {
    if (i === 0) return;
    const change = legSeries[i] - legSeries[i - 1];
    if (change === 0) return;
    const at = i - size;
    if (at < 0) return;
    const low = change === 1;
    const p = internal ? (low ? internalLow : internalHigh) : low ? swingLow : swingHigh;
    p.level = low ? bars[at][3] : bars[at][2];
    p.crossed = false;
    p.time = bars[at][0];
    p.index = at;
    if (!internal) {
      trail.barIndex = at;
      if (low) {
        trail.bottom = p.level;
        trail.lastBottom = at;
      } else {
        trail.top = p.level;
        trail.lastTop = at;
      }
    }
  };

  /** The lowest (bullish) or highest (bearish) bar between the broken pivot and this bar. */
  const storeOrderBlock = (p: Pivot, i: number, bias: number) => {
    if (p.index >= i) return;
    let best = p.index;
    for (let j = p.index; j < i; j++) {
      if (bias === BEARISH ? parsedHighs[j] > parsedHighs[best] : parsedLows[j] < parsedLows[best]) best = j;
    }
    orderBlocks.unshift({ high: parsedHighs[best], low: parsedLows[best], index: best, bias });
    if (orderBlocks.length > 100) orderBlocks.pop();
  };

  const displayStructure = (i: number, internal: boolean) => {
    const [, open, high, low, close] = bars[i];
    const prevClose = bars[i - 1][4];
    // Confluence filter (on for internals): the break must come from a bar whose body sits
    // on the right side of its wicks. Transcribed from the Pine as written.
    const bullishBar = !internal || high - Math.max(close, open) > Math.min(close, open - low);
    const bearishBar = !internal || high - Math.max(close, open) < Math.min(close, open - low);

    const pHigh = internal ? internalHigh : swingHigh;
    const pLow = internal ? internalLow : swingLow;

    const upExtra = internal ? internalHigh.level !== swingHigh.level && bullishBar : true;
    if (close > pHigh.level && prevClose <= pHigh.seen && !pHigh.crossed && upExtra) {
      const tag = (internal ? internalTrend : swingTrend) === BEARISH ? "CHoCH" : "BOS";
      pHigh.crossed = true;
      if (internal) internalTrend = BULLISH;
      else {
        swingTrend = BULLISH;
        structure.push({ from: pHigh.index, to: i, price: pHigh.level, tag, bullish: true, color: SMC_COLORS.bull });
      }
      if (internal) storeOrderBlock(pHigh, i, BULLISH);
    }

    const downExtra = internal ? internalLow.level !== swingLow.level && bearishBar : true;
    if (close < pLow.level && prevClose >= pLow.seen && !pLow.crossed && downExtra) {
      const tag = (internal ? internalTrend : swingTrend) === BULLISH ? "CHoCH" : "BOS";
      pLow.crossed = true;
      if (internal) internalTrend = BEARISH;
      else {
        swingTrend = BEARISH;
        structure.push({ from: pLow.index, to: i, price: pLow.level, tag, bullish: false, color: SMC_COLORS.bear });
      }
      if (internal) storeOrderBlock(pLow, i, BEARISH);
    }
  };

  for (let i = 0; i < bars.length; i++) {
    const [, , high, low] = bars[i];

    // Wide bars get their high and low swapped, which keeps them from being chosen as an
    // order block: that is LuxAlgo's volatility filter, in ATR mode.
    const a = atr200[i];
    const wide = a !== null && high - low >= 2 * a;
    parsedHighs.push(wide ? low : high);
    parsedLows.push(wide ? high : low);

    trail.top = Math.max(high, trail.top);
    if (trail.top === high) trail.lastTop = i;
    trail.bottom = Math.min(low, trail.bottom);
    if (trail.bottom === low) trail.lastBottom = i;

    // A gap dies when price trades back through it. The bullish test wants a full pass
    // below the gap, the bearish one only a touch of its near edge — asymmetric in the
    // original, and kept that way so the picture matches TradingView.
    gaps = gaps.filter((g) => !((low < g.bottom && g.bias === BULLISH) || (high > g.top && g.bias === BEARISH)));

    takePivot(i, swingLength, swingLegs, false);
    takePivot(i, internalLength, internalLegs, true);

    if (i > 0) {
      displayStructure(i, true);
      displayStructure(i, false);
    }
    [swingHigh, swingLow, internalHigh, internalLow].forEach((p) => {
      p.seen = p.level;
    });

    orderBlocks = orderBlocks.filter(
      (ob) => !((ob.bias === BEARISH && high > ob.high) || (ob.bias === BULLISH && low < ob.low)),
    );

    if (i >= 2) {
      const [, lastOpen, , , lastClose] = bars[i - 1];
      const last2High = bars[i - 2][2];
      const last2Low = bars[i - 2][3];
      const delta = (lastClose - lastOpen) / (lastOpen * 100);
      cumDelta += Math.abs(delta);
      const threshold = (cumDelta / i) * 2;
      // The box spans the impulse bar and the one that confirmed it, plus one bar of extension.
      if (low > last2High && lastClose > last2High && delta > threshold) {
        gaps.unshift({ top: low, bottom: last2High, bias: BULLISH, from: i - 1, to: i + 1 });
      }
      if (high < last2Low && lastClose < last2Low && -delta > threshold) {
        gaps.unshift({ top: high, bottom: last2Low, bias: BEARISH, from: i - 1, to: i + 1 });
      }
    }
  }

  const blocks = orderBlocks.slice(0, obCount);
  const last = bars.length - 1;
  const zones: SmcZone[] = [];
  const trailing: TrailingLine[] = [];

  if (!Number.isNaN(trail.top) && !Number.isNaN(trail.bottom)) {
    const { top, bottom } = trail;
    const mid = Math.round(0.5 * (trail.barIndex + last));
    const zone = (zTop: number, zBottom: number, label: string, fill: string, labelColor: string,
                  labelPrice: number, labelAt: number, labelAlign: "mid" | "right"): SmcZone =>
      ({ from: trail.barIndex, to: last, top: zTop, bottom: zBottom, fill, label, labelPrice, labelAt, labelAlign, labelColor });

    zones.push(
      zone(top, 0.95 * top + 0.05 * bottom, "Premium", SMC_COLORS.premium, SMC_COLORS.premiumText, top, mid, "mid"),
      zone(0.525 * top + 0.475 * bottom, 0.525 * bottom + 0.475 * top, "Equilibrium", SMC_COLORS.equilibrium,
           SMC_COLORS.equilibriumText, (top + bottom) / 2, last, "right"),
      zone(0.95 * bottom + 0.05 * top, bottom, "Discount", SMC_COLORS.discount, SMC_COLORS.discountText, bottom, mid, "mid"),
    );

    trailing.push(
      { side: "high", from: trail.lastTop, price: top, text: swingTrend === BEARISH ? "Strong High" : "Weak High", color: SMC_COLORS.bear },
      { side: "low", from: trail.lastBottom, price: bottom, text: swingTrend === BULLISH ? "Strong Low" : "Weak Low", color: SMC_COLORS.bull },
    );
  }

  return {
    structure,
    orderBlocks: blocks.map((ob, i) => ({
      from: ob.index,
      to: null,
      top: ob.high,
      bottom: ob.low,
      fill: orderBlockFill(ob.bias === BULLISH ? "bull" : "bear", i, blocks.length),
    })),
    fvgs: gaps.map((g) => ({
      from: g.from,
      to: g.to,
      top: Math.max(g.top, g.bottom),
      bottom: Math.min(g.top, g.bottom),
      fill: g.bias === BULLISH ? SMC_COLORS.bullFvg : SMC_COLORS.bearFvg,
    })),
    zones,
    trailing,
  };
}
