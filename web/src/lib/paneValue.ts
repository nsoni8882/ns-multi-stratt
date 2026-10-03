import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from "lightweight-charts";

type DrawTarget = Parameters<IPrimitivePaneRenderer["draw"]>[0];

export interface ValueChunk {
  text: string;
  color: string;
}

const PAD_X = 8;
const PAD_Y = 5;
const GAP = 12;
const SIZE = 12;

/**
 * A TradingView-style readout in the top-left corner of an oscillator pane.
 *
 * It exists because the price scale's own value badge cannot be made to behave: the scale
 * paints every gridline label and then paints badges over them with no collision check, so a
 * badge that lands near a gridline covers half of its number and leaves a sliver. Nothing in
 * the API suppresses the label underneath, so the readout moves off the scale instead — which
 * also says what the number is, rather than leaving a bare coloured pill to be guessed at.
 */
export class PaneValue implements ISeriesPrimitive<Time> {
  private param: SeriesAttachedParameter<Time, SeriesType> | null = null;

  /** `background` carves the text out of whatever line happens to run behind it. */
  constructor(private readonly read: () => ValueChunk[], private readonly background: string) {}

  attached(param: SeriesAttachedParameter<Time, SeriesType>): void {
    this.param = param;
  }

  detached(): void {
    this.param = null;
  }

  /** Repaint, after whatever `read` closes over has changed. */
  refresh(): void {
    this.param?.requestUpdate();
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return [{ zOrder: () => "top", renderer: () => ({ draw: (t: DrawTarget) => this.paint(t) }) }];
  }

  private paint(target: DrawTarget): void {
    const chunks = this.read();
    if (chunks.length === 0) return;
    target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
      ctx.font = `600 ${SIZE * vr}px Inter, system-ui, sans-serif`;
      ctx.textAlign = "left";
      ctx.textBaseline = "top";
      const widths = chunks.map((c) => ctx.measureText(c.text).width);
      const total = widths.reduce((a, w) => a + w, 0) + GAP * hr * (chunks.length - 1);
      ctx.fillStyle = this.background;
      ctx.fillRect(0, 0, PAD_X * 2 * hr + total, (PAD_Y * 2 + SIZE) * vr);
      let x = PAD_X * hr;
      chunks.forEach((chunk, i) => {
        ctx.fillStyle = chunk.color;
        ctx.fillText(chunk.text, x, PAD_Y * vr);
        x += widths[i] + GAP * hr;
      });
    });
  }
}
