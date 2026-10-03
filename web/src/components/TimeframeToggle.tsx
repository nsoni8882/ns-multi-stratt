import { useTimeframe } from "../hooks";

export function TimeframeToggle() {
  const [tf, setTf] = useTimeframe();
  return (
    <div className="seg" role="group" aria-label="Timeframe">
      <button type="button" aria-pressed={tf === "1d"} onClick={() => setTf("1d")}>1D</button>
      <button type="button" aria-pressed={tf === "4h"} onClick={() => setTf("4h")}>4H</button>
    </div>
  );
}
