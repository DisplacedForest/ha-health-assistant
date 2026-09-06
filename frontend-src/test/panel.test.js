import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = (await readFile(new URL("../src/panel.js", import.meta.url), "utf8"))
  .replace(/^import .*;\n/gm, "");

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function fixture(storage = new Map()) {
  let Panel;
  vm.runInNewContext(source, {
    LitElement: class {},
    html: () => "",
    css: () => "",
    svg: () => "",
    nothing: undefined,
    overviewStyles: "",
    bodyStyles: "",
    window: { localStorage: { getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value) } },
    customElements: { get: () => undefined, define: (_, constructor) => { Panel = constructor; } },
  });
  const panel = new Panel();
  const mutation = deferred();
  const focus = [];
  const detailRequests = [];
  const readings = {
    weight: { id: 1, metric: "weight", excluded: false },
    steps: { id: 2, metric: "steps", excluded: false },
  };
  panel.updateComplete = Promise.resolve();
  panel.shadowRoot = {
    querySelector: (selector) => selector === "dialog"
      ? { showModal() {}, close() {} }
      : { focus: () => focus.push(panel._detail?.observation.id) },
  };
  panel._overview = { metrics: Object.entries(readings).map(([metric, current]) => ({ metric, current })) };
  let refreshes = 0;
  panel._refresh = async () => { refreshes++; };
  panel.hass = {
    user: { id: "test-user" },
    callWS: async (message) => {
      if (message.type.endsWith("/observation_exclusion")) return mutation.promise;
      if (message.type.endsWith("/observations")) return { observations: [readings[message.metric]] };
      if (message.type.endsWith("/observation_detail")) {
        detailRequests.push(message.observation_id);
        return { observation: Object.values(readings).find((reading) => reading.id === message.observation_id) };
      }
      throw new Error(`Unexpected request: ${message.type}`);
    },
  };
  return { panel, mutation, focus, detailRequests, refreshes: () => refreshes };
}

for (const metric of ["steps", "weight"]) {
  for (const outcome of ["success", "failure"]) {
    test(`delayed exclusion ${outcome} leaves a reopened ${metric} dialog alone`, async () => {
      const { panel, mutation, focus, detailRequests, refreshes } = fixture();
      await panel._openDetail("weight");
      const pending = panel._toggleExclusion();
      panel._closeDetail();
      await panel._openDetail(metric);
      const openedDetail = panel._detail;
      const requestCount = detailRequests.length;
      if (outcome === "success") mutation.resolve({});
      else mutation.reject(new Error("Disconnected"));
      await pending;
      assert.equal(panel._detailMetric, metric);
      assert.equal(panel._detail, openedDetail);
      assert.equal(detailRequests.length, requestCount);
      assert.equal(panel._detailError, undefined);
      assert.equal(panel._busyId, undefined);
      assert.deepEqual(focus, []);
      assert.equal(refreshes(), outcome === "success" ? 1 : 0);
    });
  }
}

test("exclusion refresh cannot replace a reading selected while the mutation was pending", async () => {
  const { panel, mutation, focus, detailRequests } = fixture();
  await panel._openDetail("weight");
  const pending = panel._toggleExclusion();
  await panel._loadDetail(2);
  mutation.resolve({});
  await pending;
  assert.equal(panel._detail.observation.id, 2);
  assert.deepEqual(detailRequests, [1, 2]);
  assert.deepEqual(focus, []);
});

test("closing during the overview refresh prevents a detail reload and focus change", async () => {
  const { panel, mutation, focus, detailRequests } = fixture();
  const refresh = deferred();
  const started = deferred();
  panel._refresh = async () => { started.resolve(); await refresh.promise; };
  await panel._openDetail("weight");
  const pending = panel._toggleExclusion();
  mutation.resolve({});
  await started.promise;
  panel._closeDetail();
  refresh.resolve();
  await pending;
  assert.equal(panel._detailMetric, undefined);
  assert.deepEqual(detailRequests, [1]);
  assert.deepEqual(focus, []);
});

test("a current dialog reloads its changed reading and restores action focus", async () => {
  const { panel, mutation, focus, detailRequests, refreshes } = fixture();
  await panel._openDetail("weight");
  const pending = panel._toggleExclusion();
  mutation.resolve({});
  await pending;
  assert.deepEqual(detailRequests, [1, 1]);
  assert.deepEqual(focus, [1]);
  assert.equal(refreshes(), 1);
  assert.equal(panel._busyId, undefined);
});

test("a current dialog shows a failed mutation and restores action focus", async () => {
  const { panel, mutation, focus } = fixture();
  await panel._openDetail("weight");
  const pending = panel._toggleExclusion();
  mutation.reject(new Error("Disconnected"));
  await pending;
  assert.equal(panel._detailError, "The reading could not be changed. Refresh and try again.");
  assert.deepEqual(focus, [1]);
  assert.equal(panel._busyId, undefined);
});

test("Body is opt-in and an explicit view preference survives a new panel", () => {
  const storage = new Map();
  const first = fixture(storage).panel;
  assert.equal(first._tab, "overview");
  first._setTab("body");
  const next = fixture(storage).panel;
  next.updated(new Set(["hass"]));
  assert.equal(next._tab, "body");
  const otherUser = fixture(storage).panel;
  otherUser.hass.user.id = "someone-else";
  otherUser.updated(new Set(["hass"]));
  assert.equal(otherUser._tab, "overview");
});

for (const outcome of ["success", "failure"]) {
  test(`a delayed workout ${outcome} cannot alter a newly opened metric dialog`, async () => {
    const { panel, focus } = fixture();
    const response = deferred();
    const requested = deferred();
    const original = panel.hass.callWS;
    panel.hass.callWS = (message) => {
      if (message.type.endsWith("/workout_detail")) { requested.resolve(); return response.promise; }
      return original(message);
    };
    const pending = panel._openWorkout(8);
    await requested.promise;
    panel._closeDetail();
    await panel._openDetail("steps");
    if (outcome === "success") response.resolve({ title: "Old workout" });
    else response.reject(new Error("Disconnected"));
    await pending;
    assert.equal(panel._detailMetric, "steps");
    assert.equal(panel._bodyRegion, undefined);
    assert.equal(panel._workoutDetail, undefined);
    assert.equal(panel._workoutError, undefined);
    assert.equal(panel._detail.observation.id, 2);
    assert.deepEqual(focus, []);
  });
}
