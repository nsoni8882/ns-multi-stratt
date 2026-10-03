import { useState } from "react";
import { asReport, clear, read, type LoggedError } from "../lib/errorLog";

/**
 * Shown only once something has actually gone wrong in this browser. It is the whole reporting
 * path for client-side errors on a static site: no server receives them, so the page has to
 * hand them back to the person looking at it.
 */
export function ErrorFooter({ errors: initial }: { errors?: LoggedError[] }) {
  const [errors, setErrors] = useState<LoggedError[]>(() => initial ?? read());
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  if (errors.length === 0) return null;

  const report = asReport(errors, navigator.userAgent);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(report);
      setCopied(true);
    } catch {
      setOpen(true); // clipboard blocked: show the text so it can be selected by hand
    }
  };

  return (
    <div className="errlog">
      <div className="row">
        <span>{errors.length} error{errors.length === 1 ? "" : "s"} happened in your browser.</span>
        <button type="button" onClick={copy}>{copied ? "Copied" : "Copy details"}</button>
        <button type="button" onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"}</button>
        <button type="button" onClick={() => { clear(); setErrors([]); }}>Clear</button>
      </div>
      {open && <pre>{report}</pre>}
    </div>
  );
}
