import { html, nothing } from "lit";
import { chart, controls, dailyTable, detailShell, endpoint, number, reasons, records, summaries } from "./sparse-view.js";

function recoveryDetail(c) {
  const d = c.detail;
  if (!d || d.status === "deleted") return nothing;
  return html`<dl><dt>Value</dt><dd>${number(d.value, d.unit)}</dd><dt>Metric</dt><dd>${d.metric.replaceAll("_", " ")}</dd><dt>Context</dt><dd>${d.context.replaceAll("_", " ")}</dd><dt>Algorithm</dt><dd>${d.algorithm_id || "Unknown"}</dd><dt>Algorithm version</dt><dd>${d.algorithm_version || "Unknown"}</dd></dl>`;
}

function baseline(c) {
  const value = c.series?.baseline;
  if (!value) return nothing;
  const point = c.series.points.at(-1);
  return html`<section aria-label="Personal baseline"><h3>Prior 28-day history</h3><p>${value.start_date} through ${value.end_date} (end date excluded). ${value.n}/${value.possible_days} days present (${Math.round(value.coverage * 100)}% coverage).</p>
    ${value.mean === null ? html`<p>${reasons[value.baseline_reason] || "Baseline unavailable."}</p>` : html`<p>Prior 28-day average: ${number(value.mean, point.unit)}</p>${value.deviation === null ? html`<p>${reasons.no_current_value}</p>` : html`<p>Difference from average: ${number(value.deviation, point.unit)}</p>`}`}
    <details><summary>Technical detail: standardized difference</summary><p>${value.z === null ? reasons[value.z_reason] || "Standardized difference unavailable." : number(value.z)}</p><p>Sample standard deviation: ${value.stddev === null ? "Unavailable" : number(value.stddev, point.unit)}. These values describe your own history. They aren't a readiness score or a clinical assessment.</p></details>
  </section>`;
}

export function renderRecovery(c) {
  const point = c.series?.points.at(-1);
  return html`<section class="card sparse-view" aria-label="Recovery history">${controls(c, "Recovery")}
    ${c.selected ? html`<p>Metric: ${c.selected.metric.replaceAll("_", " ")}. Context: ${c.selected.context.replaceAll("_", " ")}. Algorithm: ${c.selected.algorithm_id || "unknown"}, version ${c.selected.algorithm_version || "unknown"}.</p>
      ${point ? html`<h3>${point.date}: ${number(point.value, point.unit)}</h3>${!point.complete_day ? html`<p>Incomplete day. Historical rolling summaries exclude this date.</p>` : nothing}${point.alternative_count ? html`<p>Latest record selected from ${point.alternative_count + 1} same-day records. This is not a daily average.</p>` : nothing}${point.selected_record_id ? html`<p>Selected window: ${endpoint(point, "start", c.timezone)} to ${endpoint(point, "end", c.timezone)}.</p>` : nothing}` : nothing}
      ${chart(c)}${summaries(c)}${baseline(c)}${dailyTable(c)}${records(c)}${detailShell(c, recoveryDetail(c))}` : nothing}
  </section>`;
}
