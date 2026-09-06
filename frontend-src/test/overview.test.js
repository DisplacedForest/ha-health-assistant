import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = (await readFile(new URL("../src/overview-view.js", import.meta.url), "utf8"))
  .replace(/^import .*;\n/gm, "")
  .replace(/^export /gm, "");
const tag = (strings, ...values) => strings.reduce((result, text, index) =>
  result + text + (Array.isArray(values[index]) ? values[index].join("") : values[index] ?? ""), "");
const sparkline = vm.runInNewContext(`${source}\nsparkline`, {
  html: tag, svg: tag, css: tag, nothing: "",
});

test("trend paths honor source boundaries even when display labels are identical", () => {
  const points = [false, true, true].map((source_changed, index) => ({
    v: 80 + index,
    t: `2026-09-0${index + 1}T12:00:00Z`,
    provider: "same clipped label",
    source_changed,
  }));
  assert.equal(sparkline({ points, unit: "kg" }).match(/<path /g).length, 3);
  for (const point of points) point.source_changed = false;
  assert.equal(sparkline({ points, unit: "kg" }).match(/<path /g).length, 1);
});
