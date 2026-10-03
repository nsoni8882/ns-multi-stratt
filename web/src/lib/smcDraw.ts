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
type Scope = Parameters<Parameters<DrawTarget["useBitmapCoordinateSpace"]>[0]>[0];

const EDGE = 6; // keeps right-edge text clear of the price scale
const TEXT_GAP = 4; // between a label and the line it belongs to

/**
 * Draws one Smart Money Concepts overlay. Everything lives in a single primitive rather than
 * one per shape: the chart repaints them together, the translucent fills stay behind the
 * candles, and the lines and labels stay in front.
 *
 * Coordinates are resolved inside `draw`, not cached in `updateAllViews`. A programmatic
 * `setVisibleLogicalRange` repaints the chart without calling `updateAllViews`, so anything
 * cached there is drawn against the range the chart had before it scrolled.
 */
export class SmcOverlay implements ISeriesPrimitive<Time> {
  private param: SeriesAttachedParameter<Time, SeriesType> | null = null;

  constructor(private readonly data: Smc) {}

  attached(param: SeriesAttachedParameter<Time, SeriesType>): void {
    this.param = param;
  }

  detached(): void {
    this.param = null;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return [
      { zOrder: () => "bottom", renderer: () => ({ draw: (t: DrawTarget) => this.paint(t, "fills") }) },
      { zOrder: () => "top", renderer: () => ({ draw: (t: DrawTarget) => this.paint(t, "lines") }) },
    ];
  }

  private paint(target: DrawTarget, layer: "fills" | "lines"): void {
    const param = this.param;
    if (!param) return;
    const scale = param.chart.timeScale();
    target.useBitmapCoordinateSpace((scope) => {
      const { horizontalPixelRatio: hr, verticalPixelRatio: vr } = scope;
      /** Bar index to bitmap x. Values outside the visible range are fine: the canvas clips. */
      const x = (index: number) => {
        const c = scale.logicalToCoordinate(index as Logical);
        return c === null ? null : c * hr;
      };
      const y = (price: number) => {
        const c = param.series.priceToCoordinate(price);
        return c === null ? null : c * vr;
      };
      if (layer === "fills") this.paintFills(scope, x, y);
      else this.paintLines(scope, x, y);
    });
  }

  private paintFills(scope: Scope, x: (i: number) => number | null, y: (p: number) => number | null): void {
    const { context: ctx, bitmapSize, horizontalPixelRatio: hr, verticalPixelRatio: vr } = scope;
    const { orderBlocks, fvgs, zones } = this.data;
    for (const b of [...zones, ...orderBlocks, ...fvgs]) {
      const x1 = x(b.from);
      const x2 = b.to === null ? bitmapSize.width : x(b.to);
      const top = y(b.top);
      const bottom = y(b.bottom);
      if (x1 === null || x2 === null || top === null || bottom === null) continue;
      ctx.fillStyle = b.fill;
      ctx.fillRect(x1, top, Math.max(x2 - x1, hr), Math.max(bottom - top, vr));
    }
  }

  private paintLines(scope: Scope, x: (i: number) => number | null, y: (p: number) => number | null): void {
    const { context: ctx, bitmapSize, horizontalPixelRatio: hr, verticalPixelRatio: vr } = scope;
    const { structure, zones, trailing } = this.data;

    const label = (text: string, px: number, py: number, color: string, size: number,
                   align: CanvasTextAlign, place: "above" | "below" | "middle") => {
      ctx.fillStyle = color;
      ctx.font = `600 ${size * vr}px Inter, system-ui, sans-serif`;
      ctx.textAlign = align;
      ctx.textBaseline = place === "middle" ? "middle" : place === "above" ? "bottom" : "top";
      const pad = place === "middle" ? 0 : (place === "above" ? -TEXT_GAP : TEXT_GAP) * vr;
      ctx.fillText(text, px, py + pad);
    };

    const rule = (x1: number, x2: number, py: number, color: string) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(1, Math.round(hr));
      ctx.beginPath();
      ctx.moveTo(x1, Math.round(py) + 0.5);
      ctx.lineTo(x2, Math.round(py) + 0.5);
      ctx.stroke();
    };

    structure.forEach((s) => {
      const x1 = x(s.from);
      const x2 = x(s.to);
      const py = y(s.price);
      if (x1 === null || x2 === null || py === null) return;
      rule(x1, x2, py, s.color);
      label(s.tag, (x1 + x2) / 2, py, s.color, 12, "center", s.bullish ? "above" : "below");
    });

    zones.forEach((z) => {
      const px = x(z.labelAt);
      const py = y(z.labelPrice);
      if (px === null || py === null) return;
      const right = z.labelAlign === "right";
      label(z.label, right ? px - EDGE * hr : px, py, z.labelColor, 11, right ? "right" : "center",
            right ? "middle" : z.label === "Premium" ? "above" : "below");
    });

    trailing.forEach((t) => {
      const x1 = x(t.from);
      const py = y(t.price);
      if (x1 === null || py === null) return;
      rule(x1, bitmapSize.width, py, t.color);
      label(t.text, bitmapSize.width - EDGE * hr, py, t.color, 10, "right", t.side === "high" ? "above" : "below");
    });
  }
}
