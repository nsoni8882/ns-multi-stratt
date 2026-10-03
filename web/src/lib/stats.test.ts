import { quantile } from "./stats";

it("interpolates linearly like pandas", () => {
  expect(quantile([1, 2, 3, 4, 5], 0.5)).toBe(3);
  expect(quantile([1, 2, 3, 4], 0.5)).toBe(2.5);
  expect(quantile([0, 10], 0.1)).toBeCloseTo(1);
  expect(quantile([5], 0.9)).toBe(5);
});
