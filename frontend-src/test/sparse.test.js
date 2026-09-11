import assert from "node:assert/strict";
import test from "node:test";
import { SparseController, addDays, dayStart, displayDate, keyString } from "../src/sparse-controller.js";
import { renderSleep, timelinePaths } from "../src/sleep-view.js";
import { renderRecovery } from "../src/recovery-view.js";

const sleepKey = { provider: "fixture", source_id: "watch" };
const recoveryKey = { ...sleepKey, metric: "hrv_sdnn", context: "sleep_summary", algorithm_id: null, algorithm_version: null };
const stamp = "2026-09-06T08:00:00Z";
const empty = (key) => ({ selected_series: key, timezone: "UTC", points: [{ date: "2026-09-06", value: null, unit: key.metric ? "ms" : "s", value_basis: "missing", null_reason: "no_observation", selection_rule: key.metric ? "latest_observation" : "longest_session", selected_record_id: null, alternative_count: 0, complete_day: true }], rolling: { "7": { mean: null, n: 0, possible_days: 7, trend_slope: null }, "28": { mean: null, n: 0, possible_days: 28, trend_slope: null }, "90": { mean: null, n: 0, possible_days: 90, trend_slope: null } }, baseline: { start_date: "2026-08-09", end_date: "2026-09-06", n: 0, possible_days: 28, coverage: 0, mean: null, stddev: null, deviation: null, z: null, baseline_reason: "insufficient_history", z_reason: "insufficient_history" } });
const source = (key, label = "Test watch") => ({ series_key: key, display_label: label, capture_state: "unknown", retained_history_available: true, active_count: 1, excluded_count: 0 });
const detail = () => ({ id: 5, source_revision: "1", payload_hash: "a".repeat(64), started_at: "2026-09-06T00:00:00Z", ended_at: stamp, status: "active", locally_excluded: false, start_zone: null, end_zone: null, start_offset_seconds: null, end_offset_seconds: null, reported_totals: { asleep: 23400000000 }, elapsed_us: 28800000000, asleep_duration_us: 23400000000, value_basis: "reported", stage_coverage_us: 0, unknown_stage_us: 0, uncovered_us: 28800000000, interval_totals: { asleep: 0 }, summary_interval_disagreement: false, context_disagreement: false, intervals: [], interval_kind: "stages", next_cursor: null });

function fixture(domain = "sleep", options = {}) {
  const calls = [], storage = options.storage || new Map();
  globalThis.window = { localStorage: { getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) } };
  const key = domain === "sleep" ? sleepKey : recoveryKey;
  const host = { _domain: "health_assistant", requestUpdate() {}, hass: { user: { id: "user", is_admin: true }, config: { time_zone: "UTC" }, callWS: async (request) => {
    calls.push(request);
    const name = request.type.split("/").at(-1);
    if (options[name]) return options[name](request);
    if (name === "derived_sources") return { sources: [source(key)], next_cursor: null };
    if (name === "derived_series") return empty(request.series_key);
    if (name === "sleep_sessions") return { sessions: [], next_cursor: null };
    if (name === "recovery_observations") return { observations: [], next_cursor: null };
    if (name === "sleep_session") return { ...detail(), interval_kind: request.kind || "stages" };
    if (name === "recovery_observation") return { ...detail(), metric: "hrv_sdnn", context: "sleep_summary", value: 50, unit: "ms", algorithm_id: null, algorithm_version: null };
    if (name.endsWith("_exclusion")) return {};
    throw new Error(`Unexpected command ${name}`);
  } } };
  const c = new SparseController(host);
  c.navigate(domain);
  c.endDate = "2026-09-06";
  c.autoEnd = false;
  return { c, host, calls, storage };
}

function text(value) {
  if (Array.isArray(value)) return value.map(text).join("");
  if (value?.strings) return value.strings.map((part, index) => part + text(value.values[index])).join("");
  return typeof value === "symbol" || typeof value === "function" || value === undefined || value === null ? "" : String(value);
}

function deferred() { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { resolve, reject, promise }; }

test("display-zone boundaries honor spring and fall DST days", () => {
  const spring = dayStart("2026-03-08", "America/Chicago"), next = dayStart("2026-03-09", "America/Chicago");
  assert.equal(spring, "2026-03-08T06:00:00.000Z");
  assert.equal(Date.parse(next) - Date.parse(spring), 23 * 3600000);
  assert.equal(Date.parse(dayStart("2026-11-02", "America/Chicago")) - Date.parse(dayStart("2026-11-01", "America/Chicago")), 25 * 3600000);
  assert.equal(displayDate("2026-09-06T01:00:00Z", "America/Chicago"), "2026-09-05");
  assert.equal(addDays("2026-03-08", 1), "2026-03-09");
});

test("multiple sources require explicit exact keys and never merge methods", async () => {
  const { c, calls, storage } = fixture("recovery", { derived_sources: () => ({ sources: [source(recoveryKey, "Same label"), source({ ...recoveryKey, metric: "hrv_rmssd" }, "Same label")], next_cursor: null }) });
  await c.refresh();
  assert.equal(c.selected, undefined);
  assert.equal(calls.some((request) => request.type.endsWith("derived_series")), false);
  assert.match(text(renderRecovery(c)), /Choose a source before viewing history/);
  await c.select(keyString(recoveryKey));
  assert.deepEqual(c.selected, recoveryKey);
  assert.equal(storage.get(c.preference), keyString(recoveryKey));
  assert.deepEqual(calls.find((request) => request.type.endsWith("derived_series")).series_key, recoveryKey);
  const view = text(renderRecovery(c));
  assert.match(view, /hrv sdnn/);
  assert.match(view, /sleep summary/);
  assert.match(view, /Baseline needs 14 days/);
});

test("saved unavailable and revoked sources stay selected without fallback", async () => {
  const storage = new Map([["health_assistant:user:sleep:source", keyString(sleepKey)]]);
  const { c, calls } = fixture("sleep", { storage, derived_sources: () => ({ sources: [source({ provider: "new", source_id: "other" })], next_cursor: null }) });
  await c.refresh();
  assert.deepEqual(c.selected, sleepKey);
  assert.equal(calls.find((request) => request.type.endsWith("derived_series")).series_key.source_id, "watch");
  assert.match(text(renderSleep(c)), /Retained history: unavailable/);
  c.sources = [{ ...source(sleepKey), capture_state: "revoked" }];
  assert.match(text(renderSleep(c)), /Capture: revoked/);
  assert.match(text(renderSleep(c)), /Retained history: available/);
});

test("a source page with one item never auto-selects while more pages exist", async () => {
  const { c } = fixture("sleep", { derived_sources: (request) => ({ sources: [source(request.cursor ? { ...sleepKey, source_id: "second" } : sleepKey)], next_cursor: request.cursor ? null : "next" }) });
  await c.refresh();
  assert.equal(c.selected, undefined);
  await c.moreSources();
  assert.equal(c.sources.length, 2);
  assert.equal(c.selected, undefined);
});

test("late source and range responses cannot overwrite newer navigation", async () => {
  const old = deferred();
  const { c } = fixture("sleep", { derived_series: (request) => request.days === 28 ? old.promise : empty(request.series_key) });
  const pending = c.refresh();
  await new Promise((resolve) => setImmediate(resolve));
  await c.setRange(7);
  const current = c.series;
  old.resolve({ ...empty(sleepKey), marker: "obsolete" });
  await pending;
  assert.equal(c.days, 7);
  assert.equal(c.series, current);
  const loading = deferred();
  c.host.hass.callWS = () => loading.promise;
  const refresh = c.refresh();
  c.navigate("recovery");
  loading.resolve({ sources: [source(sleepKey)], next_cursor: null });
  await refresh;
  assert.equal(c.domain, "recovery");
  assert.equal(c.series, undefined);
});

test("failed refresh keeps prior values marked stale with last success time", async () => {
  let fail = false;
  const { c } = fixture("sleep", { derived_series: () => { if (fail) throw { code: "connection_error" }; return empty(sleepKey); } });
  await c.refresh();
  const previous = c.series, last = c.lastSuccess;
  fail = true;
  await c.refresh();
  assert.equal(c.series, previous);
  assert.equal(c.lastSuccess, last);
  assert.equal(c.stale, true);
  assert.match(text(renderSleep(c)), /Displayed values are not current/);
});

test("wake-date drill-down uses the selected source, correct selector and local bounds", async () => {
  const { c, host, calls } = fixture();
  host.hass.config.time_zone = "America/Chicago";
  await c.refresh();
  await c.drill("2026-03-08");
  const call = calls.filter((request) => request.type.endsWith("sleep_sessions")).at(-1);
  assert.deepEqual(call.source, sleepKey);
  assert.equal(call.date_basis, "ended_at");
  assert.equal(call.start, "2026-03-08T06:00:00.000Z");
  assert.equal(call.end, "2026-03-09T05:00:00.000Z");
  await c.openDetail(5);
  const request = calls.find((item) => item.type.endsWith("sleep_session"));
  assert.equal(request.session_id, 5);
  assert.equal(Object.hasOwn(request, "id"), false);
});

test("maximum stage and context pagination completes with bounded render nodes and table rows", async () => {
  const base = Date.parse("2026-09-06T00:00:00Z");
  const { c, calls } = fixture("sleep", { sleep_session: (request) => {
    const offset = Number(request.cursor || 0);
    const kind = request.kind || "stages";
    const intervals = Array.from({ length: 128 }, (_, index) => ({ start: new Date(base + (offset + index) * 7000).toISOString(), end: new Date(base + (offset + index) * 7000 + 1000).toISOString(), ...(kind === "stages" ? { stage: "light" } : {}) }));
    return { ...detail(), interval_kind: kind, intervals, interval_count: 4096, next_cursor: offset + 128 < 4096 ? String(offset + 128) : null };
  } });
  await c.refresh();
  await c.openDetail(5);
  assert.equal(c.detail.stages.length, 4096);
  assert.equal(c.detail.in_bed_intervals.length, 4096);
  assert.equal(c.detail.completeTimeline, true);
  assert.equal(calls.filter((request) => request.type.endsWith("sleep_session")).length, 64);
  assert.equal(timelinePaths(c.detail).size, 2);
  const view = text(renderSleep(c));
  assert.match(view, /1 to 128 of 4096 loaded intervals/);
  assert.ok((view.match(/<tr>/g) || []).length < 150);
  assert.match(view, /All interval pages loaded/);
});

test("a corrected paginated detail restarts without old stages under new bounds", async () => {
  let changed = false;
  const { c } = fixture("sleep", { sleep_session: (request) => {
    if (request.cursor) { changed = true; throw { code: "stale_cursor" }; }
    if (changed) return { ...detail(), source_revision: "2", payload_hash: "b".repeat(64), ended_at: "2026-09-06T09:00:00Z" };
    return { ...detail(), intervals: [{ start: detail().started_at, end: stamp, stage: "light" }], next_cursor: "next" };
  } });
  await c.refresh();
  await c.openDetail(5);
  assert.equal(c.detail.source_revision, "2");
  assert.equal(c.detail.ended_at, "2026-09-06T09:00:00Z");
  assert.equal(c.detail.stages.length, 0);
  assert.match(c.detailNotice, /record changed/);
});

test("timer refresh does not strand an in-flight detail request", async () => {
  const pending = deferred();
  let first = true;
  const { c } = fixture("sleep", { sleep_session: () => { if (first) { first = false; return pending.promise; } return detail(); } });
  await c.refresh();
  const opening = c.openDetail(5);
  await c.refresh();
  pending.resolve(detail());
  await opening;
  assert.equal(c.detail.id, 5);
  assert.equal(c.detailLoading, false);
});

test("stale list cursors restart the list and preserve exclusion selection", async () => {
  let next = false;
  const { c } = fixture("sleep", { sleep_sessions: (request) => {
    if (request.cursor && !next) { next = true; throw { code: "stale_cursor" }; }
    return { sessions: [], next_cursor: next ? null : "next" };
  } });
  await c.refresh();
  await c.showExcluded(true);
  await c.loadRecords(true);
  assert.equal(c.excluded, true);
  assert.equal(c.listPage, 1);
  assert.match(c.listNotice, /list restarted/);
});

test("read-only users and deleted records have no mutation controls", async () => {
  const { c, host, calls } = fixture("recovery");
  await c.refresh();
  await c.openDetail(5);
  host.hass.user.is_admin = false;
  await c.exclude();
  assert.equal(calls.some((request) => request.type.endsWith("_exclusion")), false);
  assert.doesNotMatch(text(renderRecovery(c)), /Exclude from summaries/);
  host.hass.user.is_admin = true;
  c.detail.status = "deleted";
  assert.doesNotMatch(text(renderRecovery(c)), /Restore to summaries|Exclude from summaries/);
  assert.match(text(renderRecovery(c)), /cannot be restored here/);
});

test("exclusion waits for success and conflicts require a refreshed deliberate action", async () => {
  let conflict = false;
  const pending = deferred();
  const { c, calls } = fixture("recovery", { recovery_observation_exclusion: () => conflict ? Promise.reject({ code: "revision_conflict" }) : pending.promise });
  await c.refresh();
  await c.openDetail(5);
  const before = c.series;
  const saving = c.exclude();
  assert.equal(c.series, before);
  const request = calls.at(-1);
  assert.equal(request.record_id, 5);
  assert.equal(request.expected_source_revision, "1");
  assert.equal(request.expected_payload_hash, "a".repeat(64));
  assert.equal(Object.hasOwn(request, "id"), false);
  pending.resolve({});
  await saving;
  conflict = true;
  const count = calls.filter((item) => item.type.endsWith("_exclusion")).length;
  await c.exclude();
  assert.equal(calls.filter((item) => item.type.endsWith("_exclusion")).length, count + 1);
  assert.match(c.detailNotice, /Review the refreshed details/);
});

test("disconnect and closed-detail results cannot repopulate obsolete views", async () => {
  const pending = deferred();
  const { c } = fixture("recovery", { recovery_observation: () => pending.promise });
  await c.refresh();
  const opening = c.openDetail(5);
  c.closeDetail();
  c.disconnect();
  pending.resolve({ ...detail(), metric: "hrv_sdnn" });
  await opening;
  assert.equal(c.detail, undefined);
  assert.equal(c.detailLoading, false);
});

test("sleep and recovery render backend values, gaps and distinct null reasons", async () => {
  const { c } = fixture("recovery");
  await c.refresh();
  c.series.baseline = { ...c.series.baseline, n: 14, coverage: 0.5, mean: 7.5, stddev: Math.sqrt(17.5), deviation: 7.5, z: 7.5 / Math.sqrt(17.5), baseline_reason: null, z_reason: null };
  c.series.points[0] = { ...c.series.points[0], value: 15, value_basis: "reported", null_reason: null, complete_day: false, alternative_count: 2 };
  const view = text(renderRecovery(c));
  assert.match(view, /Prior 28-day average: 7.5 ms/);
  assert.match(view, /Difference from average: 7.5 ms/);
  assert.match(view, /14\/28 days present \(50% coverage\)/);
  assert.match(view, /Latest record selected from 3 same-day records/);
  assert.match(view, /Incomplete day/);
  c.series.baseline.z = null;
  c.series.baseline.z_reason = "constant_baseline";
  assert.match(text(renderRecovery(c)), /Constant history has no standardized difference/);
  c.series.baseline.baseline_reason = "calculation_unavailable";
  c.series.baseline.mean = null;
  assert.match(text(renderRecovery(c)), /calculation is unavailable/);
  c.series.baseline.z_reason = "no_current_value";
  assert.match(text(renderRecovery(c)), /No observation for the selected date/);
});

test("permission errors and excluded-only records have distinct readable states", async () => {
  const { c } = fixture("sleep", { derived_sources: () => ({ sources: [{ ...source(sleepKey), active_count: 0, excluded_count: 2 }], next_cursor: null }) });
  await c.refresh();
  assert.match(text(renderSleep(c)), /only excluded records/);
  c.host.hass.callWS = async () => { throw { code: "unauthorized" }; };
  await c.refresh();
  assert.match(text(renderSleep(c)), /permission to read this history/);
});

test("malformed saved keys cannot reach the API or break recovery rendering", async () => {
  for (const key of [{ ...recoveryKey, context:null }, { ...recoveryKey, algorithm_id:0 }, { ...recoveryKey, extra:true }, ["fixture"]]) {
    const storage = new Map([["health_assistant:user:recovery:source", JSON.stringify(key)]]);
    const { c, calls } = fixture("recovery", { storage, derived_sources: () => ({ sources:[], next_cursor:null }) });
    await c.refresh();
    assert.equal(c.selected, undefined);
    assert.equal(calls.some((request) => request.type.endsWith("derived_series")), false);
    assert.match(text(renderRecovery(c)), /No recovery source yet/);
  }
  const { c, storage } = fixture();
  await c.refresh();
  assert.equal(storage.get(c.preference), keyString(sleepKey));
  c.detailError = "Old failure";
  c.closeDetail();
  assert.doesNotMatch(text(renderSleep(c)), /Old failure|Selected record detail/);
});

test("late exclusion success and failure cannot reopen detail after navigation", async () => {
  for (const failure of [false, true]) {
    const pending = deferred();
    const { c, calls } = fixture("recovery", { recovery_observation_exclusion: () => pending.promise });
    await c.refresh();
    await c.openDetail(5);
    const mutation = c.exclude();
    c.navigate("sleep");
    await c.refresh();
    const count = calls.length;
    if (failure) pending.reject({code:"revision_conflict"}); else pending.resolve({});
    await mutation;
    assert.equal(calls.length, count);
    assert.equal(c.detail, undefined);
    assert.equal(c.detailError, undefined);
    assert.equal(c.mutation, undefined);
  }
});

test("sleep renders supplied summary, partial coverage and disagreement independently", async () => {
  const { c } = fixture();
  await c.refresh();
  await c.openDetail(5);
  c.detail = { ...c.detail, completeTimeline:false, asleep_duration_us:null, value_basis:"incomplete", unknown_stage_us:1000000, uncovered_us:9000000000, summary_interval_disagreement:true, context_disagreement:true };
  const view = text(renderSleep(c));
  assert.match(view, /Unknown \(incomplete\)/);
  assert.match(view, /Partial detail: loading interval pages/);
  assert.doesNotMatch(view, /aria-label="Complete source interval timeline/);
  assert.match(view, /Reported totals and stage-derived totals disagree/);
  assert.match(view, /reported in-bed context overlaps an out-of-bed stage/);
  assert.match(view, /Uncovered time/);
});

test("timer refresh updates corrected open detail without stealing focus", async () => {
  let revision = "1", focus = 0;
  const { c, host } = fixture("sleep", { sleep_session: (request) => ({ ...detail(), source_revision:revision, interval_kind:request.kind || "stages" }) });
  host.shadowRoot = { querySelector: () => ({ focus: () => focus++ }) };
  await c.refresh();
  await c.openDetail(5);
  revision = "2";
  await c.refresh();
  assert.equal(c.detail.source_revision, "2");
  assert.equal(focus, 1);
  await c.drill("2026-09-04");
  c.navigate("recovery");
  assert.equal(c.listDay, undefined);
  assert.equal(c.listLoading, false);
});

test("identical mutable labels expose the distinct source and algorithm keys", async () => {
  const second = { ...recoveryKey, source_id:"second watch", algorithm_id:"nightly", algorithm_version:"2" };
  const { c } = fixture("recovery", { derived_sources: () => ({ sources:[source(recoveryKey,"Watch"),source(second,"Watch")], next_cursor:null }) });
  await c.refresh();
  const view = text(renderRecovery(c));
  assert.match(view, /Watch \(fixture\/watch; hrv_sdnn; sleep_summary; unknown algorithm; unknown version\)/);
  assert.match(view, /Watch \(fixture\/second watch; hrv_sdnn; sleep_summary; nightly; 2\)/);
});
