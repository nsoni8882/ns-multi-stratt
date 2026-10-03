import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { installGlobalHandlers } from "./lib/errorLog";
import "./theme.css";

// Nothing collects browser errors for a static site, so the page keeps its own record.
installGlobalHandlers();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
