import { useEffect, useRef } from "react";
import type { Release } from "../types";

interface Props {
  strategyName: string;
  history: Release[];
  onClose: () => void;
}

/** Newest entry first, as the scanner declares it. The top one is what produced today's list. */
export function HistoryModal({ strategyName, history, onClose }: Props) {
  const closeBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    // Stop the page behind the overlay from scrolling (iOS Safari scrolls it otherwise).
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, [onClose]);

  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet narrow" role="dialog" aria-modal="true" aria-label={`${strategyName} change history`}>
        <div className="head">
          <div>
            <h2>Change history</h2>
            <div className="tag">{strategyName}</div>
          </div>
          <button ref={closeBtn} type="button" className="x" aria-label="Close change history" onClick={onClose}>×</button>
        </div>
        {history.length === 0 ? (
          <p className="muted">No recorded changes yet.</p>
        ) : (
          <ol className="history">
            {history.map((r, i) => (
              <li key={r.version}>
                <div className="row">
                  <span className="ver">v{r.version}</span>
                  {i === 0 && <span className="now">Current</span>}
                  <time dateTime={r.date}>{r.date}</time>
                </div>
                <p>{r.summary}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
