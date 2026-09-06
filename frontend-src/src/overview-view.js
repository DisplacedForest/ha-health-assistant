import { html, svg, css, nothing } from "lit";
import { renderDialog } from "./detail-dialog.js";

function sparkline(metric, large = false) {
  const points = metric.points;
  if (!points.length) return html`<div class="trend-empty">No readings in the last 14 days</div>`;
  const width = large ? 600 : 160;
  const height = large ? 150 : 48;
  const values = points.map((point) => point.v);
  const min = Math.min(...values);
  const span = Math.max(...values) - min || Math.abs(min) * 0.05 || 1;
  const times = points.map((point) => new Date(point.t).getTime());
  const elapsed = times[times.length - 1] - times[0] || 1;
  const x = (index) => 6 + (times[index] - times[0]) / elapsed * (width - 12);
  const y = (value) => height - 8 - (value - min) / span * (height - 16);
  const paths = [];
  let path = "";
  points.forEach((point, index) => {
    if (index && point.source_changed) {
      paths.push(path);
      path = "";
    }
    path += `${path ? " L" : "M"}${x(index)},${y(point.v)}`;
  });
  paths.push(path);
  return html`<svg class="sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="Recorded trend over 14 days. Lines break when the source changes.">
    ${paths.map((d) => svg`<path d=${d}></path>`)}
    ${points.map((point, index) => svg`<circle cx=${x(index)} cy=${y(point.v)} r=${large ? 2.5 : 1.8}><title>${point.v} ${metric.unit} · ${new Date(point.t).toLocaleString()}</title></circle>`)}
  </svg>`;
}

export function changeText(panel, metric) {
  if (metric.state === "source_changed") return "Source changed. Compare with care.";
  if (metric.state === "conflict") return "Sources disagree. Review readings.";
  if (metric.delta === null) return "More history needed for a comparison";
  const shown = panel._display(Math.abs(metric.delta), metric.unit);
  const digits = metric.unit === "count" ? 0 : 1;
  if (Number(shown.value.toFixed(digits)) === 0) return "No visible change at this precision";
  const unit = shown.unit === "count" ? "steps" : shown.unit === "%" ? "percentage points" : shown.unit;
  return `${metric.delta > 0 ? "+" : metric.delta < 0 ? "−" : ""}${panel._fmt(shown.value, digits)} ${unit} · ${metric.state === "steady" ? "little change" : metric.delta > 0 ? "up" : "down"}`;
}

function freshness(panel, metric) {
  const current = metric.current;
  if (!current) return "No readings yet";
  return `${metric.stale ? "Older reading · " : "Observed "}${panel._when(current.observed_at)}`;
}

function metricRow(panel, metric) {
  return html`<button class="metric-row ${metric.stale ? "stale" : ""}" @click=${(event) => panel._openDetail(metric.metric, event)}>
    <div><span class="metric-name">${panel._label(metric.metric)}</span><span class="metric-source">${metric.current ? panel._providerName(metric.current.provider) : "Connect a source or log a reading"}</span></div>
    <div class="row-trend">${sparkline(metric)}</div>
    <div class="metric-value">${panel._metricValue(metric.current, metric.unit === "count" ? 0 : 1)}<span class="metric-source">${freshness(panel, metric)}</span></div>
    <div class="row-change">${metric.current ? changeText(panel, metric) : "No comparison yet"}${metric.delta !== null ? html`<span class="metric-source">${metric.comparison_label}</span>` : nothing}</div>
    <span class="row-arrow" aria-hidden="true">›</span>
  </button>`;
}

export function renderOverview(panel) {
  const data = panel._overview;
  if (!data) return html`<p role="status">${panel._loading ? "Loading your health record…" : "Health data is unavailable."}</p>`;
  const available = data.metrics.filter((metric) => metric.current);
  const leading = available[0];
  const remaining = available.filter((metric) => metric !== leading);
  const missing = data.metrics.filter((metric) => !metric.current);
  return html`
    <div class="overview-actions"><button @click=${() => panel._openForm("measure")}>Log a measurement</button><button @click=${() => panel._openForm("workout")}>Log a workout</button></div>
    ${panel._measurementForm()}${panel._workoutForm()}
    ${leading ? html`<section class="lead-change ${leading.stale ? "stale" : ""}">
      <div class="lead-copy"><p class="eyebrow">${leading.state === "changed" && !leading.stale ? "A change in your record" : leading.state === "conflict" ? "Worth a closer look" : "Your latest readings"}</p>
        <h2>${panel._label(leading.metric)}</h2><div class="lead-value">${panel._metricValue(leading.current, leading.unit === "count" ? 0 : 1)}</div>
        <p class="change-line">${changeText(panel, leading)}</p>
        ${leading.delta !== null ? html`<p class="sub">${leading.comparison_label}</p>` : nothing}
        <p class="sub">${panel._providerName(leading.current.provider)} · ${freshness(panel, leading)}</p>
        <button class="primary" @click=${(event) => panel._openDetail(leading.metric, event)}>Review ${panel._label(leading.metric).toLowerCase()}</button>
      </div><div class="lead-chart">${sparkline(leading, true)}<span class="sub">Last 14 days · recorded readings</span></div>
    </section>` : html`<section class="intro-empty"><p class="eyebrow">Start with one reading</p><h2>Your health record starts here.</h2><p>Connect your scale or activity tracker in Health Assistant’s integration settings, or log a measurement above. Your history stays on this Home Assistant instance.</p><a href="/config/integrations/integration/health_assistant">Open integration settings</a></section>`}
    ${remaining.length ? html`<section class="metric-section" aria-label="Health metrics"><div class="section-heading"><h2>The rest of your record</h2><span class="sub">Select a metric for readings and sources</span></div>${remaining.map((metric) => metricRow(panel, metric))}</section>` : nothing}
    ${missing.length ? html`<details class="missing-metrics"><summary>${missing.length} ${missing.length === 1 ? "metric" : "metrics"} without readings</summary><p class="sub">Connect a source, add a reading, or open a metric to restore an excluded record.</p>${missing.map((metric) => metricRow(panel, metric))}</details>` : nothing}
    <section class="workout-section"><div class="section-heading"><h2>This week’s training</h2><span class="sub">${data.workout_count} ${data.workout_count === 1 ? "workout" : "workouts"} in the last 7 days</span></div>
      ${data.workouts.length ? html`<div class="workout-strip">${data.workouts.map((workout) => html`<article class="workout-item"><span class="eyebrow">${panel._when(workout.started_at)}</span><h3>${workout.title}</h3><p>${panel._fmt(workout.duration_seconds / 60, 0)} min · ${workout.workout_type}</p><span class="sub">${panel._providerName(workout.provider)}</span></article>`)}</div>` : html`<p class="empty-note">No workouts recorded this week. Connected workout sources and manual entries will appear here.</p>`}
    </section>
    <details class="source-status"><summary>Sources <span>${data.providers.filter((provider) => provider.degraded).length ? "· needs attention" : "· status"}</span></summary><p class="sub">Successful source operations and measurement times are different. A source can be working while its latest reading is old.</p>${data.providers.map((provider) => html`<div class="source-row"><strong>${panel._providerName(provider.key)}</strong><span>${provider.degraded ? "Needs attention" : provider.had_error ? "Working again" : provider.last_success ? "Working" : "Waiting for data"}</span><span class="sub">${provider.last_success ? `Last successful operation ${panel._when(provider.last_success)}` : "No successful operation since reload"}</span></div>`)}<a href="/config/integrations/integration/health_assistant">Manage sources in integration settings</a></details>
  `;
}

export function renderDetail(panel) {
  if (!panel._detailMetric) return nothing;
  const metric = panel._overview?.metrics.find((item) => item.metric === panel._detailMetric);
  const detail = panel._detail;
  const reading = detail?.observation;
  return renderDialog(panel, panel._label(panel._detailMetric), "Readings and sources", html`
    ${panel._detailError ? html`<p class="error" role="alert">${panel._detailError}<button @click=${() => panel._loadDetail()}>Try again</button></p>` : nothing}
    ${metric ? html`<div class="detail-trend">${sparkline(metric, true)}<p class="sub">${changeText(panel, metric)}${metric.delta !== null ? ` · ${metric.comparison_label}` : ""}</p></div>` : nothing}
    ${panel._detailLoading ? html`<p role="status">Loading readings…</p>` : nothing}
    ${reading ? html`<section class="reading-detail"><div class="section-heading"><h3>${reading.excluded ? "Excluded reading" : "Selected reading"}</h3><span class="reading-value">${panel._metricValue(reading)}</span></div><p>${new Date(reading.observed_at).toLocaleString()} · ${panel._providerName(reading.provider)}</p>
      ${reading.possible_duplicate ? html`<p class="notice">Nearby sources may disagree. Review the original claims and nearby readings before changing anything.</p>` : nothing}
      ${reading.excluded ? html`<p class="notice">Kept in your history, excluded from summaries and trends.</p>` : nothing}
      <h4>Source claims</h4><p class="sub">The selected claim supplies this record’s value. Source priority resolves equivalent claims; nearby records are shown separately.</p>
      ${detail.claims.map((claim) => html`<div class="claim-row"><div><strong>${panel._providerName(claim.provider)}</strong><span class="metric-source">${claim.selected ? "Selected claim" : "Retained claim"} · ${new Date(claim.observed_at).toLocaleString()}</span><span class="source-id">${claim.external_id}</span></div><span>${panel._metricValue(claim)}</span></div>`)}
      ${detail.claim_count > detail.claims.length ? html`<p class="sub">Showing ${detail.claims.length} of ${detail.claim_count} claims.</p>` : nothing}
      ${detail.nearby.length ? html`<h4>Nearby readings</h4>${detail.nearby.map((candidate) => html`<button class="record-button" ?disabled=${panel._detailLoading} @click=${() => panel._loadDetail(candidate.id)}><span>${panel._providerName(candidate.provider)} · ${panel._when(candidate.observed_at)}</span><span>${panel._metricValue(candidate)}</span></button>`)}` : nothing}
      ${panel.hass.user?.is_admin ? html`<div class="exclusion-control"><p class="sub">${reading.excluded ? "Restore this reading to summaries and trends." : "An incorrect reading can be excluded without deleting its source history. You can restore it later."}</p><button ?disabled=${Boolean(panel._busyId) || panel._detailLoading} @click=${() => panel._toggleExclusion()}>${panel._busyId ? "Saving…" : reading.excluded ? "Restore reading" : "Exclude reading"}</button></div>` : html`<p class="sub">An administrator can exclude or restore incorrect readings.</p>`}
    </section>` : !panel._detailLoading ? html`<p>No ${panel._showExcluded ? "excluded " : ""}readings to show.</p>` : nothing}
    <section class="record-history"><div class="section-heading"><h3>Browse readings</h3><label class="excluded-toggle"><input type="checkbox" .checked=${panel._showExcluded} @change=${(event) => {panel._showExcluded = event.target.checked; panel._detail = undefined; panel._loadDetail();}} /> Excluded only</label></div><p class="sub">Most recently added first</p>
    ${panel._records.map((record) => html`<button class="record-button ${reading?.id === record.id ? "selected" : ""}" ?disabled=${panel._detailLoading} @click=${() => panel._loadDetail(record.id)}><span>${new Date(record.observed_at).toLocaleString()}<span class="metric-source">${panel._providerName(record.provider)}</span></span><span>${panel._metricValue(record)}</span></button>`)}
    ${panel._nextRecord ? html`<button ?disabled=${panel._detailLoading} @click=${() => panel._loadDetail(reading?.id, true)}>Load older readings</button>` : nothing}</section>
  `);
}

export const overviewStyles = css`
  :host { --health-line: var(--divider-color, #8885); --health-accent: var(--primary-color, #168c9e); }
  .page-subtitle { margin: 6px 0 0; color: var(--secondary-text-color); font-size: 14px; }
  .header-identity { display: flex; align-items: center; gap: 16px; }
  .overview-actions { display: flex; gap: 8px; margin: 20px 0; flex-wrap: wrap; }
  .lead-change { display: grid; grid-template-columns: minmax(240px, 0.9fr) minmax(0, 1.1fr); gap: 40px; padding: 36px 0 40px; border-top: 1px solid var(--health-line); border-bottom: 1px solid var(--health-line); }
  .lead-copy h2 { font-size: 23px; margin: 12px 0; color: var(--primary-text-color); }
  .eyebrow { font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--secondary-text-color); margin: 0; }
  .lead-value .value { font-size: clamp(42px, 5vw, 64px); line-height: 1.1; font-weight: 500; font-variant-numeric: tabular-nums; }
  .lead-value .unit { font-size: 22px; margin-left: 5px; }
  .change-line { font-size: 16px; margin: 16px 0 4px; }
  .lead-chart { align-self: center; min-width: 0; text-align: right; }
  .lead-copy .sub { text-align: left; font-size: 13px; }
  .sparkline { display: block; width: 100%; overflow: visible; color: var(--health-accent); }
  .sparkline path { fill: none; stroke: currentColor; stroke-width: 2; vector-effect: non-scaling-stroke; }
  .sparkline circle { fill: currentColor; }
  .stale .sparkline { color: var(--secondary-text-color); opacity: 0.65; }
  .stale .metric-value, .stale .lead-value { color: var(--secondary-text-color); }
  .trend-empty { color: var(--secondary-text-color); font-size: 12px; padding: 14px 0; }
  .section-heading { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 16px; flex-wrap: wrap; }
  .section-heading h2 { font-size: 19px; color: var(--primary-text-color); margin: 0; }
  .section-heading h3 { margin: 0; }
  .metric-section, .workout-section { margin-top: 32px; }
  .missing-metrics { margin-top: 24px; color: var(--secondary-text-color); }
  .missing-metrics summary { cursor: pointer; padding: 10px 0; font-size: 14px; }
  button.metric-row { width: 100%; display: grid; grid-template-columns: 1.1fr 0.75fr 1fr 1.2fr 12px; align-items: center; gap: 20px; padding: 20px 2px; border: 0; border-bottom: 1px solid var(--health-line); border-radius: 0; background: transparent; color: var(--primary-text-color); text-align: left; }
  .metric-name { display: block; font-size: 16px; }
  .metric-source { display: block; margin-top: 5px; font-size: 12px; line-height: 1.5; color: var(--secondary-text-color); }
  .metric-value { text-align: right; font-variant-numeric: tabular-nums; }
  .metric-value .value { font-size: 23px; }
  .row-change { font-size: 12px; line-height: 1.5; }
  .row-arrow { font-size: 24px; color: var(--secondary-text-color); }
  .workout-strip { display: flex; gap: 28px; overflow-x: auto; padding: 4px 0 16px; }
  .workout-item { min-width: 180px; flex: 1; border-left: 2px solid var(--health-accent); padding-left: 16px; }
  .workout-item h3 { font-size: 17px; line-height: 1.4; margin: 12px 0 8px; overflow-wrap: anywhere; }
  .workout-item p { font-size: 14px; margin: 0 0 8px; }
  .source-status { border-top: 1px solid var(--health-line); padding: 22px 0; margin-top: 24px; }
  .source-status summary { cursor: pointer; padding: 8px 0; font-size: 15px; }
  .source-status summary span { color: var(--secondary-text-color); }
  .source-row { display: grid; grid-template-columns: 1fr 1fr 2fr; gap: 16px; padding: 14px 0; font-size: 13px; }
  a { color: var(--health-accent); }
  .intro-empty { max-width: 650px; padding: 40px 0; }
  .intro-empty h2 { font-size: 32px; color: var(--primary-text-color); line-height: 1.2; }
  .intro-empty p:not(.eyebrow), .empty-note { line-height: 1.6; color: var(--secondary-text-color); }
  dialog { box-sizing: border-box; width: min(720px, calc(100vw - 32px)); max-height: calc(100dvh - 40px); border: 1px solid var(--health-line); border-radius: 16px; padding: 28px; color: var(--primary-text-color); background: var(--card-background-color, var(--primary-background-color)); }
  dialog::backdrop { background: #0009; }
  .detail-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; position: sticky; top: -28px; padding: 16px 0; background: var(--card-background-color, var(--primary-background-color)); z-index: 2; }
  dialog .sub { text-align: left; font-size: 13px; }
  .detail-header h2 { margin: 8px 0 20px; color: var(--primary-text-color); font-size: 26px; }
  .detail-trend { margin: 0 0 24px; }
  .detail-trend .sparkline { max-height: 130px; }
  .reading-detail { border-top: 1px solid var(--health-line); padding-top: 24px; }
  .reading-value .value { font-size: 28px; }
  .notice { padding: 14px; border-left: 3px solid var(--health-accent); background: var(--secondary-background-color); line-height: 1.5; }
  .claim-row { display: flex; justify-content: space-between; gap: 16px; padding: 15px 0; border-bottom: 1px solid var(--health-line); }
  .source-id { display: block; font-size: 11px; overflow-wrap: anywhere; color: var(--secondary-text-color); margin-top: 5px; }
  button.record-button { width: 100%; border: 0; border-bottom: 1px solid var(--health-line); background: transparent; padding: 14px 8px; display: flex; justify-content: space-between; gap: 16px; text-align: left; border-radius: 0; }
  button.record-button.selected { background: var(--secondary-background-color); }
  .exclusion-control, .record-history { margin-top: 24px; }
  .excluded-toggle { display: flex; flex-direction: row; gap: 8px; align-items: center; font-size: 13px; }
  .excluded-toggle input { width: auto; }
  button:focus-visible, a:focus-visible, summary:focus-visible { outline: 2px solid var(--health-accent); outline-offset: 4px; }
  @media (max-width: 900px) { button.metric-row { grid-template-columns: 1fr 1fr 12px; gap: 14px; } .row-trend { grid-column: 1; grid-row: 2; max-width: 140px; } .row-change { grid-column: 2; grid-row: 2; } .row-arrow { grid-column: 3; grid-row: 1; } .lead-change { gap: 24px; } }
  @media (max-width: 600px) { .lead-change { grid-template-columns: 1fr; gap: 24px; padding: 24px 0; } .lead-chart { width: 100%; } .source-row { grid-template-columns: 1fr 1fr; } .source-row .sub { grid-column: 1 / -1; } dialog { padding: 20px; } .detail-header { top: -20px; } }
  @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; } }
`;
