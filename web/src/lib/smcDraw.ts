import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  Logical,
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from "lightweight-charts";
import type { Smc } from "./smc";

type DrawTarget = Parameters<IPrimitivePaneRenderer["draw"]>[0];

/** x2 of null means "run to the right edge of the pane". */
interface Rect {
  x1: number;
  x2: number | null;
  top: number;
  bottom: number;
  fill: string;
}
interface Seg {
  x1: number;
  x2: number | null;
  y: number;
  color: string;
}
interface Text {
  x: number;
  y: number;
  text: string;
  color: string;
  align: CanvasTextAlign;
  /** Where the text sits relative to y: above it, below it, or centred on it. */
  baseline: "above" | "below" | "middle";
  size: number;
}

const EDGE = 6; // keeps right-edge text off the price scale

/**
 * Draws one Smart Money Concepts overlay. Everything lives in a single primitive rather than
 * one per shape: the chart repaints them together, and it keeps the fills behind the candles
 * while the lines and labels stay in front.
 */
export class SmcOverlay implements ISeriesPrimitive<Time> {
  private param: SeriesAttachedParameter<Time, SeriesType> | null = null;
  private rects: Rect[] = [];
  private segs: Seg[] = [];
  private texts: Text[] = [];

  constructor(private readonly data: Smc) {}

  attached(param: SeriesAttachedParameter<Time, SeriesType>): void {
    this.param = param;
  }

  detached(): void {
    this.param = null;
  }

  updateAllViews(): void {
    this.rects = [];
    this.segs = [];
    this.texts = [];
    const param = this.param;
    if (!param) return;
    const scale = param.chart.timeScale();
    const x = (index: number) => scale.logicalToCoordinate(index as Logical);
    const y = (price: number) => param.series.priceToCoordinate(price);
    const { structure, orderBlocks, fvgs, zones, trailing } = this.data;

    const box = (from: number, to: number | null, top: number, bottom: number, fill: string) => {
      const x1 = x(from);
      const yTop = y(top);
      const yBottom = y(bottom);
      const x2 = to === null ? null : x(to);
      if (x1 === null || yTop === null || yBottom === null || (to !== null && x2 === null)) return;
      this.rects.push({ x1, x2: to === null ? null : (x2 as number), top: yTop, bottom: yBottom, fill });
    };

    zones.forEach((z) => {
      box(z.from, z.to, z.top, z.bottom, z.fill);
      const lx = x(z.labelAt);
      const ly = y(z.labelPrice);
      if (lx === null || ly === null) return;
      this.texts.push({
        x: z.labelAlign === "right" ? lx - EDGE : lx,
        y: ly,
        text: z.label,
        color: z.labelColor,
        align: z.labelAlign === "right" ? "right" : "center",
        baseline: z.labelAlign === "right" ? "middle" : z.label === "Premium" ? "above" : "below",
        size: 11,
      });
    });

    orderBlocks.forEach((b) => box(b.from, b.to, b.top, b.bottom, b.fill));
    fvgs.forEach((g) => box(g.from, g.to, g.top, g.bottom, g.fill));

    structure.forEach((s) => {
      const x1 = x(s.from);
      const x2 = x(s.to);
      const ly = y(s.price);
      if (x1 === null || x2 === null || ly === null) return;
      this.segs.push({ x1, x2, y: ly, color: s.color });
      this.texts.push({
        x: (x1 + x2) / 2,
        y: ly,
        text: s.tag,
        color: s.color,
        align: "center",
        baseline: s.bullish ? "above" : "below",
        size: 12,
      });
    });

    trailing.forEach((t) => {
      const x1 = x(t.from);
      const ly = y(t.price);
      if (x1 === null || ly === null) return;
      this.segs.push({ x1, x2: null, y: ly, color: t.color });
      this.texts.push({
        x: -EDGE, // resolved against the pane width at draw time
        y: ly,
        text: t.text,
        color: t.color,
        align: "right",
        baseline: t.side === "high" ? "above" : "below",
        size: 10,
      });
    });
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return [
      { zOrder: () => "bottom", renderer: () => this.fillsRenderer() },
      { zOrder: () => "top", renderer: () => this.linesRenderer() },
    ];
  }

  private fillsRenderer(): IPrimitivePaneRenderer {
    const rects = this.rects;
    return {
      draw: (target: DrawTarget) =>
        target.useBitmapCoordinateSpace(({ context: ctx, bitmapSize, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
          rects.forEach((r) => {
            const x1 = r.x1 * hr;
            const x2 = r.x2 === null ? bitmapSize.width : r.x2 * hr;
            ctx.fillStyle = r.fill;
            ctx.fillRect(x1, r.top * vr, Math.max(x2 - x1, hr), Math.max((r.bottom - r.top) * vr, vr));
          });
        }),
    };
  }

  private linesRenderer(): IPrimitivePaneRenderer {
    const { segs, texts } = this;
    return {
      draw: (target: DrawTarget) =>
        target.useBitmapCoordinateSpace(({ context: ctx, bitmapSize, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
          segs.forEach((s) => {
            ctx.strokeStyle = s.color;
            ctx.lineWidth = Math.max(1, Math.round(hr));
            ctx.beginPath();
            ctx.moveTo(s.x1 * hr, Math.round(s.y * vr) + 0.5);
            ctx.lineTo(s.x2 === null ? bitmapSize.width : s.x2 * hr, Math.round(s.y * vr) + 0.5);
            ctx.stroke();
          });
          texts.forEach((t) => {
            ctx.fillStyle = t.color;
            ctx.font = `600 ${t.size * vr}px Inter, system-ui, sans-serif`;
            ctx.textAlign = t.align;
            ctx.textBaseline = t.baseline === "middle" ? "middle" : t.baseline === "above" ? "bottom" : "top";
            const pad = t.baseline === "middle" ? 0 : (t.baseline === "above" ? -4 : 4) * vr;
            // A negative x is measured back from the right edge, for the labels that sit there.
            const x = t.x < 0 ? bitmapSize.width + t.x * hr : t.x * hr;
            ctx.fillText(t.text, x, t.y * vr + pad);
          });
        }),
    };
  }
}
