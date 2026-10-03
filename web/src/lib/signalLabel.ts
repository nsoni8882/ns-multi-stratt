import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from "lightweight-charts";
import type { Side } from "../types";

export interface SignalLabelData {
  time: number; // unix seconds of the signal candle
  price: number; // candle low (BUY) or high (SELL): the label hangs off this price
  side: Side;
  color: string; // box fill; text is white
}

type DrawTarget = Parameters<IPrimitivePaneRenderer["draw"]>[0];

const BOX_W = 46;
const BOX_H = 20;
const GAP = 6; // between the candle and the notch tip
const NOTCH = 6;

/** ctx.roundRect is missing before Safari 16, so build the rounded rectangle from arcs. */
function roundedRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/** Draws a filled "BUY" / "SELL" box with a small pointer, anchored to a candle on the price pane. */
export class SignalLabelPrimitive implements ISeriesPrimitive<Time> {
  private param: SeriesAttachedParameter<Time, SeriesType> | null = null;
  private pos: { x: number; y: number } | null = null;

  constructor(private readonly data: SignalLabelData) {}

  attached(param: SeriesAttachedParameter<Time, SeriesType>): void {
    this.param = param;
  }

  detached(): void {
    this.param = null;
  }

  updateAllViews(): void {
    if (!this.param) return;
    const x = this.param.chart.timeScale().timeToCoordinate(this.data.time as unknown as Time);
    const y = this.param.series.priceToCoordinate(this.data.price);
    this.pos = x === null || y === null ? null : { x, y };
  }

  paneViews(): readonly IPrimitivePaneView[] {
    const { data } = this;
    const pos = this.pos;
    const renderer: IPrimitivePaneRenderer = {
      draw: (target: DrawTarget) => {
        if (!pos) return;
        target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
          const buy = data.side === "BUY";
          const x = pos.x * hr;
          const tipY = (buy ? pos.y + GAP : pos.y - GAP) * vr;
          const boxTop = buy ? tipY + NOTCH * vr : tipY - (NOTCH + BOX_H) * vr;
          const w = BOX_W * hr;
          const h = BOX_H * vr;
          ctx.fillStyle = data.color;
          ctx.beginPath();
          roundedRect(ctx, x - w / 2, boxTop, w, h, 4 * hr);
          ctx.fill();
          ctx.beginPath(); // pointer towards the candle
          ctx.moveTo(x, tipY);
          ctx.lineTo(x - (NOTCH * hr) / 1.2, buy ? boxTop : boxTop + h);
          ctx.lineTo(x + (NOTCH * hr) / 1.2, buy ? boxTop : boxTop + h);
          ctx.closePath();
          ctx.fill();
          ctx.fillStyle = "#FFFFFF";
          ctx.font = `700 ${12 * vr}px Inter, system-ui, sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(data.side, x, boxTop + h / 2 + vr);
        });
      },
    };
    return [{ zOrder: () => "top", renderer: () => renderer }];
  }
}
