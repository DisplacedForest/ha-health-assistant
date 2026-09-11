import { html, svg, css, nothing } from "lit";
import { displayDate, keyString } from "./sparse-controller.js";

export const reasons = {
  no_observation: "No observation",
  incomplete_sleep: "Sleep duration is unknown because coverage is incomplete.",
  insufficient_history: "Baseline needs 14 days of data.",
  no_current_value: "No observation for the selected date.",
  constant_baseline: "Constant history has no standardized difference.",
  calculation_unavailable: "This calculation is unavailable.",
};

export function number(value, unit = "") {
  if (value === null || value === undefined) return "No observation";
  if (unit === "s") return `${(value / 3600).toLocaleString(undefined, { maximumFractionDigits: 2 })} h`;
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 3 })}${unit ? ` ${unit}` : ""}`;
}

export function instant(value, zone) {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat(undefined, { timeZone: zone, dateStyle: "medium", timeStyle: "medium" }).format(new Date(value));
}

export function endpoint(record, side, displayZone) {
  const value = record[`${side === "start" ? "started" : "ended"}_at`];
  const zone = record[`${side}_zone`];
  if (zone) return `${instant(value, zone)} (${zone})`;
  const offset = record[`${side}_offset_seconds`];
  if (offset !== null && offset !== undefined) {
    const shifted = new Date(Date.parse(value) + offset * 1000).toISOString();
    const minutes = Math.abs(offset) / 60;
    const label = `UTC${offset < 0 ? "-" : "+"}${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
    return `${instant(shifted, "UTC")} (${label}, reported offset)`;
  }
  return `${instant(value, displayZone)} (${displayZone} display time; source timezone unknown)`;
}

export function chart(controller) {
  const points = controller.series?.points || [];
  const values = points.filter((point) => point.value !== null).map((point) => point.value);
  if (!values.length) return html`<p>No values in this range. Missing days stay empty.</p>`;
  const min = Math.min(...values), span = Math.max(...values) - min || 1;
  const x = (index) => 10 + index / Math.max(1, points.length - 1) * 580;
  const y = (value) => 130 - (value - min) / span * 115;
  const paths = [];
  let path = "";
  for (const [index, point] of points.entries()) {
    if (point.value === null) { if (path) paths.push(path); path = ""; }
    else path += `${path ? " L" : "M"}${x(index)},${y(point.value)}`;
  }
  if (path) paths.push(path);
  return html`<svg class="sparse-chart" viewBox="0 0 600 150" role="img" aria-label="Daily history. Gaps mean no known value. The table below contains each date and value.">
    ${paths.map((d) => svg`<path d=${d}></path>`)}
    ${points.map((point, index) => point.value === null ? nothing : svg`<circle cx=${x(index)} cy=${y(point.value)} r="3"><title>${point.date}: ${number(point.value, point.unit)}; ${controller.descriptor?.display_label || keyString(controller.selected)}; ${point.started_at || point.observed_at || ""} to ${point.ended_at || point.observed_at || ""}; ${point.selection_rule}; ${point.value_basis}</title></circle>`)}
  </svg>`;
}

export function controls(c, title) {
  const selected = c.selected ? keyString(c.selected) : "";
  return html`<div class="sparse-heading"><h2>${title}</h2><p>Display timezone: ${c.timezone}${c.host.hass?.config?.time_zone ? "" : " (Home Assistant timezone unavailable; using UTC)"}</p></div>
    <div class="sparse-controls">
      <label>Source and method<select aria-label="Source and method" .value=${selected} @change=${(event) => c.select(event.target.value)}>
        <option value="" ?selected=${!selected}>Choose a source</option>
        ${selected && !c.descriptor ? html`<option value=${selected} selected>Saved selection: ${selected}</option>` : nothing}
        ${c.sources.map((source) => html`<option value=${keyString(source.series_key)} ?selected=${selected === keyString(source.series_key)}>${source.display_label}</option>`)}
      </select></label>
      <label>History<select aria-label="History range" .value=${String(c.days)} @change=${(event) => c.setRange(Number(event.target.value))}>${[7, 28, 90].map((days) => html`<option value=${days} ?selected=${c.days === days}>${days} days</option>`)}</select></label>
      <label>End date<input type="date" aria-label="History end date" .value=${c.endDate || ""} max=${displayDate(Date.now(), c.timezone)} @change=${(event) => event.target.value && c.setRange(c.days, event.target.value)}></label>
    </div>
    ${c.sourceCursor ? html`<button @click=${() => c.moreSources()} ?disabled=${c.sourceLoading}>${c.sourceLoading ? "Loading sources" : "More sources"}</button>` : nothing}
    ${c.loading ? html`<p role="status">Loading ${title.toLowerCase()} history.</p>` : nothing}
    ${c.error ? html`<p class="sparse-notice" role="alert">${c.error} ${c.stale ? "Displayed values are not current." : ""}</p>` : nothing}
    ${c.lastSuccess ? html`<p class="sparse-muted">Last successful refresh: ${instant(c.lastSuccess, c.timezone)}</p>` : nothing}
    ${!c.loading && !c.sources.length && !c.selected && !c.error ? html`<p>No ${title.toLowerCase()} source yet. These views don't connect to your phone or create records. A compatible provider must supply this history first.</p>` : nothing}
    ${!c.selected && c.sources.length ? html`<p>Choose a source before viewing history. Accounts and methods are kept separate.</p>` : nothing}
    ${c.selected ? html`<p class="sparse-source">${c.descriptor?.display_label || "Saved source selection"}<br>Capture: ${c.descriptor?.capture_state || "unknown"}. Retained history: ${c.descriptor ? c.descriptor.retained_history_available ? "available" : "unavailable" : c.sourceCursor ? "not established on this source page" : "unavailable"}.</p>` : nothing}`;
}

export function summaries(c) {
  if (!c.series) return nothing;
  return html`<div class="sparse-summary">${Object.entries(c.series.rolling).map(([window, value]) => html`<div><h3>${window}-day history</h3><p>${number(value.mean, c.series.points[0]?.unit)}</p><p>${value.n}/${value.possible_days} days present. Complete days only.</p><p>Trend: ${value.trend_slope === null ? value.trend_reason === "calculation_unavailable" ? reasons.calculation_unavailable : "Needs at least 3 days of data" : number(value.trend_slope, `${c.series.points[0]?.unit}/day`)}</p>${value.mean_reason === "calculation_unavailable" || value.trend_reason === "calculation_unavailable" ? html`<p>${reasons.calculation_unavailable}</p>` : nothing}</div>`)}</div>`;
}

export function dailyTable(c) {
  if (!c.series) return nothing;
  return html`<details class="sparse-daily"><summary>Daily values and record choices</summary><div class="sparse-table"><table><caption>Daily history in ${c.timezone}</caption><thead><tr><th scope="col">Date</th><th scope="col">Value</th><th scope="col">Record choice</th><th scope="col">Inspect</th></tr></thead><tbody>${c.series.points.map((point) => html`<tr><td>${point.date}${!point.complete_day ? html`<br>Incomplete day` : nothing}</td><td>${point.value === null ? reasons[point.null_reason] || reasons.no_observation : number(point.value, point.unit)}<br>${point.value_basis.replaceAll("_", " ")}</td><td>${point.selection_rule.replaceAll("_", " ")}${point.alternative_count ? html`<br>${point.alternative_count} other record${point.alternative_count === 1 ? "" : "s"}` : nothing}</td><td><button @click=${() => c.drill(point.date)} aria-label=${`List records ending on ${point.date}`}>List</button>${point.selected_record_id ? html`<button @click=${(event) => c.openDetail(point.selected_record_id, event)} aria-label=${`Inspect selected record on ${point.date}`}>Detail</button>` : nothing}</td></tr>`)}</tbody></table></div></details>`;
}

export function records(c) {
  if (!c.selected) return nothing;
  return html`<section class="sparse-records" aria-label="Underlying source records"><h3>${c.listDay ? `Records ending on ${c.listDay}` : "Underlying records in this range"}</h3>
    <p>${c.domain === "sleep" ? c.listDay ? "Wake-date list. Naps and overlapping sessions are separate records." : "Sessions overlapping this display range, including naps." : "Individual records. Daily charts select the latest record, not an average."}</p>
    <label class="sparse-check"><input type="checkbox" .checked=${Boolean(c.excluded)} @change=${(event) => c.showExcluded(event.target.checked)}> Show locally excluded records</label>
    ${c.listDay ? html`<button @click=${() => { c.listDay = undefined; c.loadRecords(); }}>Show whole range</button>` : nothing}
    ${c.listNotice ? html`<p role="status">${c.listNotice}</p>` : nothing}
    ${c.listLoading ? html`<p role="status">Loading records.</p>` : nothing}
    ${c.listError ? html`<p role="alert">${c.listError} Previously listed records may be stale.</p>` : nothing}
    ${!c.listLoading && !c.records.length ? html`<p>${c.excluded ? "No locally excluded records in this range." : c.descriptor?.excluded_count && !c.descriptor.active_count ? "This source has only excluded records. Choose Show locally excluded records to inspect them." : "No records in this range."}</p>` : nothing}
    <ul class="sparse-record-list">${c.records.map((record) => html`<li><div>${instant(record.ended_at, c.timezone)}<br>${c.domain === "recovery" ? `${number(record.value, record.unit)} · ${record.context?.replaceAll("_", " ")}` : `Asleep: ${record.asleep_duration_us === null ? "Unknown" : number(record.asleep_duration_us / 1000000, "s")}`}<br>${record.status}</div><button @click=${(event) => c.openDetail(record.id, event)} aria-label=${`Inspect record ending ${instant(record.ended_at, c.timezone)}`}>Inspect</button></li>`)}</ul>
    <div class="sparse-controls">${c.listPage > 1 ? html`<button @click=${() => c.loadRecords()}>First page</button>` : nothing}${c.recordCursor ? html`<button ?disabled=${c.listLoading} @click=${() => c.loadRecords(true)}>Next 50 records</button>` : nothing}</div>
  </section>`;
}

export function detailShell(c, content) {
  if (!c.detail && !c.detailLoading && !c.detailError) return nothing;
  const record = c.detail;
  return html`<section class="sparse-detail" role="region" aria-label="Selected record detail"><div class="sparse-controls"><h3 tabindex="-1">Record detail</h3><button @click=${() => c.closeDetail()}>Close detail</button></div>
    ${c.detailLoading ? html`<p role="status">Loading detail${record && !record.completeTimeline ? "; timeline is partial" : ""}.</p>` : nothing}
    ${c.detailNotice ? html`<p role="status">${c.detailNotice}</p>` : nothing}${c.detailError ? html`<p role="alert">${c.detailError}</p><button @click=${() => c.openDetail(c.detailId)}>Refresh detail</button>` : nothing}
    ${record ? html`<p>Status: ${record.status}. Revision: ${record.source_revision}.</p><dl><dt>Start</dt><dd>${endpoint(record, "start", c.timezone)}</dd><dt>End</dt><dd>${endpoint(record, "end", c.timezone)}</dd></dl>${record.status === "deleted" ? html`<p>This record was deleted upstream and cannot be restored here.</p>` : content}
      ${c.admin && record.status !== "deleted" ? html`<div class="sparse-exclusion"><p>Local exclusion hides this source record from summaries. It does not delete upstream data. Restore clears local exclusion only.</p><button ?disabled=${Boolean(c.mutation) || c.detailLoading} @click=${() => c.exclude()}>${c.mutation ? "Saving exclusion" : record.locally_excluded ? "Restore to summaries" : "Exclude from summaries"}</button></div>` : nothing}` : nothing}
  </section>`;
}

export const sparseStyles = css`
  .sparse-view { min-width:0; overflow-wrap:anywhere; }
  .sparse-heading h2 { margin-bottom:6px; }
  .sparse-muted,.sparse-source,.sparse-heading p { color:var(--secondary-text-color); font-size:.9rem; }
  .sparse-controls { display:flex; flex-wrap:wrap; gap:12px; align-items:end; margin:12px 0; }
  .sparse-controls label { display:flex; flex-direction:column; gap:6px; min-width:0; flex:1 1 140px; }
  .sparse-controls label:first-child { flex:3 1 240px; }
  .sparse-controls select,.sparse-controls input { box-sizing:border-box; width:100%; min-width:0; padding:10px; color:var(--primary-text-color); background:var(--card-background-color); border:1px solid var(--divider-color); border-radius:8px; }
  .sparse-view button:focus-visible,.sparse-view input:focus-visible,.sparse-view select:focus-visible,.sparse-view summary:focus-visible { outline:3px solid var(--primary-color); outline-offset:3px; }
  .sparse-summary { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr)); gap:16px; margin:18px 0; }
  .sparse-summary > div { border-top:1px solid var(--divider-color); padding-top:12px; }
  .sparse-summary h3 { margin:0; font-size:1rem; }
  .sparse-summary p { margin:8px 0; }
  .sparse-notice { border-left:3px solid var(--primary-color); padding:10px; }
  .sparse-chart { display:block; width:100%; height:auto; max-height:180px; }
  .sparse-chart path { fill:none; stroke:var(--primary-color,#03a9f4); stroke-width:2; }
  .sparse-chart circle { fill:var(--primary-color,#03a9f4); }
  .sparse-table { overflow-x:auto; max-width:100%; margin:12px 0; }
  .sparse-view table { width:100%; border-collapse:collapse; font-size:.88rem; }
  .sparse-view th,.sparse-view td { text-align:left; padding:10px 6px; border-bottom:1px solid var(--divider-color); vertical-align:top; }
  .sparse-view caption { text-align:left; margin:10px 0; }
  .sparse-view summary { cursor:pointer; padding:12px 0; }
  .sparse-records,.sparse-detail { border-top:1px solid var(--divider-color); margin-top:22px; padding-top:16px; }
  .sparse-record-list { list-style:none; margin:12px 0; padding:0; }
  .sparse-record-list li { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:12px 0; border-bottom:1px solid var(--divider-color); }
  .sparse-record-list li > div { min-width:0; }
  .sparse-check { display:inline-flex; gap:8px; align-items:center; margin:8px 0; }
  .sparse-view dl { display:grid; grid-template-columns:auto minmax(0,1fr); gap:10px; }
  .sparse-view dd { margin:0; }
  .sparse-exclusion { margin-top:16px; padding-top:8px; border-top:1px solid var(--divider-color); }
  .stage-timeline { width:100%; height:100px; display:block; }
  .stage-legend { display:flex; flex-wrap:wrap; gap:12px; font-size:.85rem; }
  .stage-legend span { border-left:5px solid var(--stage-color); padding-left:6px; }
  @media(prefers-reduced-motion:reduce) { .sparse-view * { animation:none!important; transition:none!important; scroll-behavior:auto!important; } }
`;
