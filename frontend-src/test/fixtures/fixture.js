import "/panel.js";
const fixture = await (await fetch("/sparse.json")).json();
const mount = document.querySelector("#mount");
const panel = document.createElement("health-assistant-panel");
const canonical = (key) => JSON.stringify(Object.fromEntries(Object.keys(key).sort().map((name) => [name, key[name]])));
let scenario = "normal";
const excluded = new Set();
const hash = "b".repeat(64);
const hass = {
  config: { time_zone: "UTC", unit_system: { length: "km" } },
  user: { id: "fixture", is_admin: true },
  callWS: async (request) => {
    await new Promise((resolve) => setTimeout(resolve, 8));
    if (scenario === "error") throw { code: "connection_error" };
    if (scenario === "permission") throw { code: "unauthorized" };
    const name = request.type.split("/").at(-1);
    if (name === "derived_sources") {
      const result = structuredClone(fixture.catalogs[request.domain]);
      if (scenario === "empty") result.sources = [];
      if (scenario === "long") for (const item of result.sources) item.display_label = "Example watch <b>literal source label</b> with a very long account and method description repeated for responsive testing ".repeat(3);
      return result;
    }
    if (name === "derived_series") return structuredClone(fixture.series[canonical(request.series_key)][request.days]);
    const sleep = name.startsWith("sleep_");
    const records = sleep ? fixture.sleep_records : fixture.recovery_records;
    if (name === "sleep_sessions" || name === "recovery_observations") {
      let values = Object.values(records).filter((record) => {
        const key = request.source || request.series;
        return Object.entries(key).every(([field, value]) => record[field] === value) && (request.date_basis === "overlap" ? record.started_at < request.end && record.ended_at > request.start : record.ended_at >= request.start && record.ended_at < request.end) && excluded.has(`${sleep}:${record.id}`) === request.excluded;
      }).sort((a,b) => b.ended_at.localeCompare(a.ended_at));
      const offset = Number(request.cursor || 0);
      return { [sleep ? "sessions" : "observations"]: values.slice(offset, offset + 50).map((value) => ({ ...value, locally_excluded: request.excluded, status: request.excluded ? "excluded" : "active" })), next_cursor: values.length > offset + 50 ? String(offset + 50) : null };
    }
    const id = request.session_id || request.record_id;
    if (name.endsWith("_exclusion")) {
      if (!hass.user.is_admin) throw { code: "unauthorized" };
      if (scenario === "conflict") throw { code: "revision_conflict" };
      if (request.excluded) excluded.add(`${sleep}:${id}`); else excluded.delete(`${sleep}:${id}`);
      return {};
    }
    if (name === "sleep_session" || name === "recovery_observation") {
      const result = structuredClone(records[id]);
      result.locally_excluded = excluded.has(`${sleep}:${id}`);
      result.status = result.locally_excluded ? "excluded" : "active";
      if (scenario === "conflict") { result.source_revision = "2"; result.payload_hash = hash; }
      if (sleep) {
        const kind = request.kind || "stages";
        const offset = Number(request.cursor || 0);
        let intervals = kind === "stages" ? result.intervals : result.context_intervals;
        if (scenario === "large") {
          const base = Date.parse(result.started_at);
          intervals = Array.from({ length:4096 }, (_, index) => ({ start:new Date(base + index * 7000).toISOString(), end:new Date(base + index * 7000 + 1000).toISOString(), ...(kind === "stages" ? { stage:index % 2 ? "light" : "deep", source_stage:"example" } : { source_label:"in bed" }) }));
        }
        result.interval_kind = kind;
        result.interval_count = intervals.length;
        result.intervals = intervals.slice(offset, offset + 128);
        result.next_cursor = intervals.length > offset + 128 ? String(offset + 128) : null;
      }
      return result;
    }
    if (name === "overview") return { metrics:[], providers:[], workouts:[], activity:[] };
    throw new Error("Unknown synthetic fixture request");
  },
};
localStorage.setItem("health_assistant:fixture:view", "sleep");
panel.hass = hass;
panel.panel = { config:{ domain:"health_assistant" } };
panel._tab = "sleep";
panel._sparse.navigate("sleep");
panel._sparse.endDate = fixture.end_date;
panel._sparse.autoEnd = false;
mount.append(panel);
function width() { mount.style.width = `${document.querySelector("#width").value}px`; panel.narrow = Number(document.querySelector("#width").value) < 600; }
width();
document.querySelector("#width").addEventListener("change", width);
document.querySelector("#theme").addEventListener("click", (event) => { const dark = document.body.classList.toggle("dark"); event.target.textContent = dark ? "Use light mode" : "Use dark mode"; });
document.querySelector("#scenario").addEventListener("change", async (event) => { scenario = event.target.value; hass.user.is_admin = scenario !== "readonly"; if (scenario === "empty") await panel._sparse.select(""); else await panel._refresh(); });
