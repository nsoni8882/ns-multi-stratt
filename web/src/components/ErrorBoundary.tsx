import { Component, type ErrorInfo, type ReactNode } from "react";
import { record } from "../lib/errorLog";

interface Props {
  children: ReactNode;
}

interface State {
  message: string | null;
}

/**
 * Stops a render error taking the whole page down to a blank white screen, and writes it to the
 * error log so the footer can offer it as copyable text. Still a class component: React has no
 * hook equivalent of componentDidCatch.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { message: null };

  static getDerivedStateFromError(error: Error): State {
    return { message: error.message || "Something went wrong" };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    record({
      source: "render",
      message: error.message,
      stack: `${error.stack ?? ""}${info.componentStack ?? ""}`,
    });
  }

  render(): ReactNode {
    if (this.state.message === null) return this.props.children;
    return (
      <div className="errorbox" role="alert">
        <p><strong>This page hit an error and stopped.</strong></p>
        <p className="tag">{this.state.message}</p>
        <p className="tag">
          The signal data itself is fine — it is published as static files. Reloading usually
          clears this. The details are saved at the bottom of the page.
        </p>
        <button type="button" className="histbtn" onClick={() => location.reload()}>Reload</button>
      </div>
    );
  }
}
