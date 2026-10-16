import "@testing-library/jest-dom/vitest";

// jsdom has no matchMedia. lightweight-charts (via fancy-canvas) calls it from an async
// callback that can land after a test file's teardown, which vitest reports as an unhandled
// rejection and exits 1 despite every test passing (scan-failure #1, run 38858691089).
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
