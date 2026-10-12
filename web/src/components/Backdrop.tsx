import { useEffect, useState } from "react";
import { wantsPrefetch } from "../lib/prefetch";

/**
 * The ambient layer behind everything. Three painted things, no images and no canvas:
 *
 *  - a hairline grid that drifts left at one cell per 22s, because that is what a chart's
 *    gridlines do as time passes — the one background metaphor a screener has earned;
 *  - two radial blooms on long, out-of-phase orbits, which is what keeps the cream from
 *    reading as paper;
 *  - a vignette under the sticky chrome, so the drift never competes with the nav.
 *
 * Fixed, pointer-events:none, aria-hidden, z-index -1: it sits above the body background and
 * below every bit of content, so it can neither be clicked, read out, nor shift a layout.
 * Only transform and opacity animate, so none of it touches layout or paint on the main thread.
 *
 * Save-Data and 2G opt out via wantsPrefetch(), the same gate the chart prefetch uses: a
 * visitor who asked for less data did not ask for decoration, and three compositor layers
 * cost battery on exactly the devices that report 2G. prefers-reduced-motion is handled in
 * theme.css, where one rule kills every animation on the page — the blooms then stay put,
 * which is still a warmer surface than flat cream.
 */
export function Backdrop() {
  // Rendered after mount, not during: the first paint belongs to the signal list, and the
  // backdrop has nothing in it a visitor is waiting for.
  const [show, setShow] = useState(false);
  useEffect(() => setShow(wantsPrefetch()), []);
  if (!show) return null;
  return (
    <div className="backdrop" aria-hidden="true" data-testid="backdrop">
      <div className="backdrop-grid" />
      <div className="backdrop-bloom one" />
      <div className="backdrop-bloom two" />
      <div className="backdrop-veil" />
    </div>
  );
}
