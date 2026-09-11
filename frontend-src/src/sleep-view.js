import { html, svg, nothing } from "lit";
import { chart, controls, dailyTable, detailShell, instant, number, records, summaries } from "./sparse-view.js";

const COLORS = { rem: "#9470cb", light: "#6495c5", deep: "#426c9e", asleep_unspecified: "#8195b4", awake: "#b78954", awake_in_bed: "#b4a270", out_of_bed: "#927d6b" };

export function timelinePaths(detail) {
  const start = Date.parse(detail.started_at), span = Date.parse(detail.ended_at) - start;
  const paths = new Map();
  if (!(span > 0)) return paths;
  for (const [kind, intervals] of [["stages", detail.stages], ["context", detail.in_bed_intervals]]) {
    for (const interval of intervals || []) {
      const stage = kind === "context" ? "in_bed" : interval.stage;
      if (stage === "unknown") continue;
      const x = (Date.parse(interval.start) - start) / span * 600;
      const width = (Date.parse(interval.end) - Date.parse(interval.start)) / span * 600;
      const y = kind === "context" ? 58 : 12;
      paths.set(stage, (paths.get(stage) || "") + `M${x},${y}h${width}v24h${-width}z`);
    }
  }
  return paths;
}

function sleepDetail(c) {
  const d = c.detail;
  if (!d || d.status === "deleted") return nothing;
  const kind = c.intervalKind || "stages";
  const intervals = d[kind] || [];
  const page = Math.min(c.intervalPage || 0, Math.max(0, Math.ceil(intervals.length / 128) - 1));
  const shown = intervals.slice(page * 128, (page + 1) * 128);
  return html`<dl><dt>Elapsed session envelope</dt><dd>${number(d.elapsed_us / 1000000, "s")}</dd><dt>Asleep duration</dt><dd>${d.asleep_duration_us === null ? "Unknown" : number(d.asleep_duration_us / 1000000, "s")} (${d.value_basis.replaceAll("_", " ")})</dd><dt>Stage coverage</dt><dd>${number(d.stage_coverage_us / 1000000, "s")}</dd><dt>Unknown stage time</dt><dd>${number(d.unknown_stage_us / 1000000, "s")}</dd><dt>Uncovered time</dt><dd>${number(d.uncovered_us / 1000000, "s")}</dd></dl>
    ${d.summary_interval_disagreement ? html`<p role="status">Reported totals and stage-derived totals disagree. Both are shown below.</p>` : nothing}
    ${d.context_disagreement ? html`<p role="status">The reported in-bed context overlaps an out-of-bed stage. These source records are shown separately.</p>` : nothing}
    <div class="sparse-table"><table><caption>Source totals and interval totals, kept separate</caption><thead><tr><th scope="col">Type</th><th scope="col">Reported</th><th scope="col">Known intervals</th></tr></thead><tbody>${Object.entries(d.reported_totals || {}).map(([key, value]) => html`<tr><th scope="row">${key.replaceAll("_", " ")}</th><td>${value === null ? "Not reported" : number(value / 1000000, "s")}</td><td>${d.interval_totals[key] === undefined ? "Not available" : number(d.interval_totals[key] / 1000000, "s")}</td></tr>`)}</tbody></table></div>
    <h4>Stages and in-bed context</h4><p>Stages are the upper lane. In-bed context is the lower lane. Gaps are unknown or uncovered, not awake or asleep.</p>
    ${d.completeTimeline ? html`<svg class="stage-timeline" viewBox="0 0 600 100" role="img" aria-label="Complete source interval timeline. Stage and in-bed lanes are separate; the interval table provides a text alternative.">${[...timelinePaths(d)].map(([stage, path]) => svg`<path d=${path} fill=${COLORS[stage] || "#8a9299"}><title>${stage.replaceAll("_", " ")}</title></path>`)}</svg><p>All interval pages loaded.</p>` : html`<p role="status">Partial detail: loading interval pages before showing the complete timeline.</p>`}
    <div class="stage-legend">${Object.entries({ ...COLORS, in_bed: "#8a9299" }).map(([stage, color]) => html`<span style=${`--stage-color:${color}`}>${stage.replaceAll("_", " ")}</span>`)}</div>
    <div class="sparse-controls"><label>Interval lane<select .value=${kind} @change=${(event) => { c.intervalKind = event.target.value; c.intervalPage = 0; c.update(); }}><option value="stages" ?selected=${kind === "stages"}>Stages</option><option value="in_bed_intervals" ?selected=${kind === "in_bed_intervals"}>In-bed context</option></select></label></div>
    <div class="sparse-table"><table><caption>${kind === "stages" ? "Stage" : "In-bed"} intervals in ${c.timezone} display time. ${intervals.length ? `${page * 128 + 1} to ${page * 128 + shown.length} of ${intervals.length} loaded intervals` : "No intervals reported"}.</caption><thead><tr><th scope="col">Type</th><th scope="col">Start</th><th scope="col">End</th></tr></thead><tbody>${shown.map((interval) => html`<tr><td>${(interval.stage || "in_bed").replaceAll("_", " ")}</td><td>${instant(interval.start, c.timezone)}<br><small>${interval.start}</small></td><td>${instant(interval.end, c.timezone)}<br><small>${interval.end}</small></td></tr>`)}</tbody></table></div>
    <div class="sparse-controls"><button ?disabled=${page === 0} @click=${() => { c.intervalPage = page - 1; c.update(); }}>Previous intervals</button><button ?disabled=${(page + 1) * 128 >= intervals.length} @click=${() => { c.intervalPage = page + 1; c.update(); }}>Next intervals</button></div>`;
}

export function renderSleep(c) {
  return html`<section class="card sparse-view" aria-label="Sleep history">${controls(c, "Sleep")}
    ${c.selected ? html`<p>Longest-session sleep duration by wake date. This isn't total daily sleep. Naps and overlapping sessions remain separate in the list.</p>${chart(c)}${summaries(c)}${dailyTable(c)}${records(c)}${detailShell(c, sleepDetail(c))}` : nothing}
  </section>`;
}
