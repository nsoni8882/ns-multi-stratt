import { clearCache, getChart, getStrategies, prefetchChart } from "./api";
import { chart, strategies, stubFetch } from "./test-fixtures";

beforeEach(() => stubFetch());
afterEach(() => {
  clearCache();
  vi.unstubAllGlobals();
});

it("fetches a file once and serves the rest of the session from memory", async () => {
  expect(await getStrategies()).toEqual(strategies);
  expect(await getStrategies()).toEqual(strategies);
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("shares one request between callers that ask at the same time", async () => {
  const [a, b] = await Promise.all([getChart("1d", "XOM"), getChart("1d", "XOM")]);
  expect(a).toEqual(chart);
  expect(b).toEqual(a);
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("does not cache a failure, so a retry really retries", async () => {
  stubFetch(["strategies.json"]);
  await expect(getStrategies()).rejects.toThrow("HTTP 500");
  stubFetch();
  expect(await getStrategies()).toEqual(strategies);
});

it("uses the request index.html started, instead of making its own", async () => {
  const early = Promise.resolve(new Response(JSON.stringify(strategies), { status: 200 }));
  (window as { __preload?: Record<string, Promise<Response>> }).__preload = { "strategies.json": early };
  expect(await getStrategies()).toEqual(strategies);
  expect(fetch).not.toHaveBeenCalled();
});

it("falls back to a normal fetch for paths index.html did not start", async () => {
  (window as { __preload?: Record<string, Promise<Response>> }).__preload = {};
  expect(await getStrategies()).toEqual(strategies);
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("reports which file failed and how", async () => {
  stubFetch(["charts/1d/XOM.json"]);
  await expect(getChart("1d", "XOM")).rejects.toThrow("Could not load charts/1d/XOM.json (HTTP 500)");
});

it("prefetching warms the cache and swallows its own failure", async () => {
  stubFetch(["charts/1d/XOM.json"]);
  expect(() => prefetchChart("1d", "XOM")).not.toThrow();
  await new Promise((r) => setTimeout(r, 0));
  stubFetch();
  expect(await getChart("1d", "XOM")).toEqual(chart); // the failed prefetch left nothing behind
});
