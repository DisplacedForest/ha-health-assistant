import { html, svg, css, nothing } from "lit";
import { BODY_OUTLINE, BODY_REGIONS } from "./body-figure.js";
import { renderDialog } from "./detail-dialog.js";
import { changeText } from "./overview-view.js";

function activate(event, action) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action(event);
  }
}

function figure(panel) {
  const regions = panel._body.regions;
  return html`<svg class="body-figure" viewBox="0 0 400 620" aria-label=${`Body, ${panel._bodySide} view. Choose a muscle region to see recorded sets.`}>
    <ellipse cx="200" cy="59" rx="28" ry="36" class="body-outline" />
    <path d=${BODY_OUTLINE} class="body-outline" />
    ${BODY_REGIONS.filter((region) => region.sides.includes(panel._bodySide)).map((region) => {
      const data = regions.find((item) => item.key === region.key);
      const heat = data?.heat || 0;
      return svg`<g class="body-region ${heat ? "recorded" : ""}" style=${`--region-heat: ${0.18 + heat * 0.82}`} role="button" tabindex="0" aria-label=${`${region.label}, ${data?.recorded_sets || 0} recorded sets`} @click=${(event) => panel._openRegion(region.key, event)} @keydown=${(event) => activate(event, (e) => panel._openRegion(region.key, e))}>
        <title>${region.label}</title><path d=${region.path}/><path d=${region.path} transform="translate(400 0) scale(-1 1)"/>
      </g>`;
    })}
    <g class="body-anchor" role="button" tabindex="0" aria-label="Body measurements: weight, body fat and lean mass" @click=${(event) => panel._openRegion("measurements", event)} @keydown=${(event) => activate(event, (e) => panel._openRegion("measurements", e))}><circle cx="200" cy="226" r="15"/><path d="M194 226h12M200 220v12"/></g>
    <g class="body-dormant" role="button" tabindex="0" aria-label="Sleep, not available yet" @click=${(event) => panel._openRegion("sleep", event)} @keydown=${(event) => activate(event, (e) => panel._openRegion("sleep", e))}><circle cx="200" cy="59" r="20"/><path d="M204 48a12 12 0 1 0 7 19a11 11 0 0 1 -7 -19Z"/></g>
    ${panel._bodySide === "front" ? svg`<g class="body-dormant" role="button" tabindex="0" aria-label="Heart, not available yet" @click=${(event) => panel._openRegion("heart", event)} @keydown=${(event) => activate(event, (e) => panel._openRegion("heart", e))}><circle cx="200" cy="148" r="17"/><path d="M200 157C182 146 188 134 196 142L200 146L204 142C212 134 218 146 200 157Z"/></g>` : nothing}
  </svg>`;
}

function measurementRows(panel) {
  return panel._overview.metrics.filter((metric) => ["weight", "body_fat_percentage", "lean_mass"].includes(metric.metric)).map((metric) => html`
    <button class="body-measurement ${metric.stale ? "stale" : ""}" @click=${(event) => panel._openDetail(metric.metric, event)}>
      <span class="metric-name">${panel._label(metric.metric)}</span><span class="body-measurement-value">${metric.current ? panel._metricValue(metric.current) : "No reading yet"}</span>
      <span class="metric-source">${metric.current ? `${panel._providerName(metric.current.provider)} · ${metric.stale ? "Older reading · " : ""}${panel._when(metric.current.observed_at)}` : "Connect a source or log a reading"}</span>
      <span class="body-change">${changeText(panel, metric)}</span>
    </button>`);
}

export function renderBody(panel) {
  const data = panel._body;
  if (!data) return panel._bodyError ? html`<p class="error" role="alert">${panel._bodyError}<button @click=${() => panel._loadBody()}>Try again</button></p>` : html`<p role="status">Loading Body view…</p>`;
  return html`<section class="body-intro"><div><p class="eyebrow">Experimental</p><h2>Your recorded week</h2><p class="sub">${data.workout_count} completed ${data.workout_count === 1 ? "workout" : "workouts"} in the last seven days. Choose a region to see its sets.</p></div><button @click=${() => { panel._bodySide = panel._bodySide === "front" ? "back" : "front"; }}>Show ${panel._bodySide === "front" ? "back" : "front"}</button></section>
    ${panel._bodyError ? html`<p class="error" role="alert">${panel._bodyError}<button @click=${() => panel._loadBody()}>Try again</button></p>` : nothing}
    ${data.truncated || data.incomplete_workouts ? html`<p class="notice">${data.truncated ? `Showing the latest ${data.workouts.length} of ${data.workout_count} workouts. ` : ""}${data.incomplete_workouts ? `${data.incomplete_workouts} ${data.incomplete_workouts === 1 ? "workout has" : "workouts have"} incomplete exercise detail.` : ""} Colors reflect the usable records shown here.</p>` : nothing}
    <div class="body-layout"><div class="body-art"><p class="body-side" aria-live="polite">${panel._bodySide}</p>${figure(panel)}<div class="body-legend"><span>Fewer</span><span class="heat-scale" aria-hidden="true"></span><span>More</span></div><p class="body-legend-copy">Recent recorded sets, fading over seven days.<br/>Color is relative to your most active region.</p></div>
    <aside class="body-context"><section><p class="eyebrow">Body measurements</p><div class="body-measurements">${measurementRows(panel)}</div></section>
      <section class="body-future"><p class="eyebrow">Still to come</p><button @click=${(event) => panel._openRegion("sleep", event)}><span class="future-symbol" aria-hidden="true">◔</span><span>Sleep<span class="metric-source">Not available yet</span></span></button><button @click=${(event) => panel._openRegion("heart", event)}><span class="future-symbol" aria-hidden="true">♡</span><span>Heart<span class="metric-source">Not available yet</span></span></button></section>
      ${data.workouts_without_sets ? html`<p class="sub">${data.workouts_without_sets} ${data.workouts_without_sets === 1 ? "workout has" : "workouts have"} no usable non-warmup sets. Workout summaries remain available below.</p>` : nothing}
      ${data.unmapped_count ? html`<details class="body-unmapped"><summary>${data.unmapped_count} unmapped exercise ${data.unmapped_count === 1 ? "entry" : "entries"}</summary><p class="sub">These names aren't in the exercise map yet. Their sets don't color the figure.</p><ul>${data.unmapped.map((item) => html`<li>${item.name}${item.occurrences > 1 ? ` (${item.occurrences})` : ""}</li>`)}</ul><p class="sub">Up to 20 names shown. Open a workout below for its exercise detail.</p></details>` : nothing}
    </aside></div>
    <section class="body-workouts"><div class="section-heading"><h2>Recorded workouts</h2><span class="sub">Last seven days</span></div>${data.workouts.length ? data.workouts.map((workout) => workoutButton(panel, workout)) : html`<p class="empty-note">No workouts recorded this week. A source with exercise and set detail will light up the figure as completed workouts arrive.</p>`}</section>`;
}

function workoutButton(panel, workout) {
  return html`<button class="record-button" @click=${(event) => panel._openWorkout(workout.id, event)}><span>${workout.title}<span class="metric-source">${panel._providerName(workout.provider)} · ${new Date(workout.ended_at).toLocaleString()}</span></span><span>${workout.recorded_sets} sets<span class="metric-source">${panel._fmt(workout.duration_seconds / 60, 0)} min</span></span></button>`;
}

function setDescription(panel, set) {
  const parts = [];
  if (set.reps !== undefined) parts.push(`${panel._fmt(set.reps, 0)} reps`);
  if (set.weight_kg !== undefined) {
    const shown = panel._display(set.weight_kg, "kg");
    parts.push(`${panel._fmt(shown.value)} ${shown.unit}`);
  }
  if (set.duration_seconds !== undefined) parts.push(`${panel._fmt(set.duration_seconds, 0)} sec`);
  if (set.distance_m !== undefined) {
    const shown = panel._display(set.distance_m, "m");
    parts.push(`${panel._fmt(shown.value)} ${shown.unit}`);
  }
  return parts.join(" · ");
}

export function renderBodyDetail(panel) {
  if (!panel._bodyRegion) return nothing;
  const key = panel._bodyRegion;
  const data = panel._body;
  const region = data?.regions.find((item) => item.key === key);
  let title = region?.label || ({ measurements: "Body measurements", sleep: "Sleep", heart: "Heart", workout: "Workout" }[key]);
  let content;
  if (panel._workoutId) {
    const workout = panel._workoutDetail;
    title = workout?.title || "Workout";
    content = html`${panel._workoutLoading ? html`<p role="status">Loading workout…</p>` : nothing}
      ${panel._workoutError ? html`<p class="error" role="alert">${panel._workoutError}<button @click=${() => panel._loadWorkout(panel._workoutId)}>Try again</button></p>` : nothing}
      ${workout ? html`<p>${panel._providerName(workout.provider)} · ${new Date(workout.ended_at).toLocaleString()}</p><p class="sub">${panel._fmt(workout.duration_seconds / 60, 0)} min · ${workout.workout_type}</p><p class="source-id">Source record: ${workout.source}</p>
        ${workout.incomplete ? html`<p class="notice">Some exercise detail is incomplete or exceeds this view's limits. The original workout is kept in your history.</p>` : nothing}
        ${workout.exercises.length ? workout.exercises.map((exercise) => html`<details class="exercise-detail"><summary>${exercise.name}<span>${exercise.recorded_sets} sets</span></summary><p class="sub">${exercise.regions.length ? exercise.regions.map((id) => data.regions.find((item) => item.key === id)?.label || id).join(", ") : "Unmapped exercise"}</p>${exercise.notes ? html`<p class="exercise-notes">${exercise.notes}</p>` : nothing}<ol>${exercise.sets.map((set) => html`<li><span>${setDescription(panel, set)}</span><span class="sub">${set.warmup ? "Warmup, not counted" : set.type}</span></li>`)}</ol></details>`) : html`<p>No usable exercise detail was recorded for this workout.</p>`}` : nothing}`;
  } else if (key === "measurements") {
    content = html`<p class="sub">The same canonical readings and trends as Overview. Choose a metric to inspect its sources.</p>${measurementRows(panel)}`;
  } else if (key === "sleep" || key === "heart") {
    content = html`<p>Not available yet.</p><p class="sub">This region is reserved for a future ${key === "sleep" ? "sleep" : "heart data"} view.</p>`;
  } else {
    const workouts = data.workouts.filter((workout) => workout.regions.includes(key));
    content = html`<p class="region-count">${region?.recorded_sets || 0}<span> recorded sets</span></p><p class="sub">Non-warmup sets from the last seven days. Color fades with time and is relative to the most active region.</p>${workouts.length ? workouts.map((workout) => workoutButton(panel, workout)) : html`<p>No mapped sets for this region in the recorded week.</p>`}`;
  }
  return renderDialog(panel, title, "Training and sources", content);
}

export const bodyStyles = css`
  .body-intro { display: flex; justify-content: space-between; align-items: center; gap: 24px; border-top: 1px solid var(--health-line); padding-top: 28px; }
  .body-intro h2 { font-size: 28px; font-weight: 500; margin: 10px 0; color: var(--primary-text-color); }
  .body-intro .sub, .body-context .sub { font-size: 13px; line-height: 1.6; text-align: left; }
  .body-layout { display: grid; grid-template-columns: minmax(250px, 1fr) minmax(240px, .8fr); gap: 64px; }
  .body-art { text-align: center; }
  .body-side { font-size: 11px; text-transform: uppercase; letter-spacing: .12em; color: var(--secondary-text-color); margin: 22px 0 0; }
  .body-figure { display: block; height: 530px; max-width: 100%; margin: 0 auto; }
  .body-outline { fill: var(--secondary-background-color); stroke: var(--secondary-text-color); stroke-width: 1.2; }
  .body-region { cursor: pointer; outline: none; }
  .body-region path { fill: var(--secondary-text-color); fill-opacity: .15; stroke: var(--primary-background-color); stroke-width: 2; stroke-linejoin: round; transition: fill-opacity .2s; }
  .body-region.recorded path { fill: var(--health-accent); fill-opacity: var(--region-heat); }
  .body-region:hover path, .body-region:focus-visible path { stroke: var(--primary-text-color); stroke-width: 2.5; }
  .body-anchor { cursor: pointer; outline: none; }
  .body-anchor circle { fill: var(--primary-background-color); stroke: var(--secondary-text-color); }
  .body-anchor path { stroke: var(--primary-text-color); stroke-width: 1.5; }
  .body-anchor:hover circle, .body-anchor:focus-visible circle { stroke: var(--primary-text-color); stroke-width: 3; }
  .body-dormant { cursor: pointer; outline: none; fill: none; stroke: var(--secondary-text-color); opacity: .65; }
  .body-dormant circle { fill: var(--primary-background-color); stroke-dasharray: 2 3; }
  .body-dormant:hover, .body-dormant:focus-visible { opacity: 1; stroke: var(--primary-text-color); stroke-width: 2; }
  .body-legend { display: flex; align-items: center; justify-content: center; gap: 10px; font-size: 11px; color: var(--secondary-text-color); }
  .heat-scale { height: 6px; width: 120px; border-radius: 4px; background: linear-gradient(to right, color-mix(in srgb, var(--health-accent) 18%, transparent), var(--health-accent)); }
  .body-legend-copy { font-size: 12px; line-height: 1.6; color: var(--secondary-text-color); }
  .body-context { padding-top: 44px; min-width: 0; }
  button.body-measurement { display: grid; grid-template-columns: 1fr auto; gap: 4px 16px; text-align: left; width: 100%; padding: 20px 0; border: 0; border-bottom: 1px solid var(--health-line); border-radius: 0; background: transparent; color: var(--primary-text-color); }
  .body-measurement .metric-source, .body-change { grid-column: 1 / -1; }
  .body-measurement-value { font-size: 21px; font-variant-numeric: tabular-nums; }
  .body-change { font-size: 12px; color: var(--secondary-text-color); line-height: 1.5; }
  .body-future { margin-top: 36px; }
  .body-future button { display: flex; gap: 16px; align-items: center; width: 100%; margin-top: 16px; padding: 12px 0; border: 0; background: transparent; text-align: left; color: var(--secondary-text-color); }
  .future-symbol { display: grid; place-items: center; width: 38px; height: 38px; border: 1px dashed var(--health-line); border-radius: 50%; font-size: 23px; }
  .body-unmapped { margin-top: 24px; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
  .body-unmapped summary { cursor: pointer; }
  .body-workouts { margin-top: 40px; }
  .region-count { font-size: 44px; font-variant-numeric: tabular-nums; margin: 20px 0 8px; }
  .region-count span { font-size: 17px; }
  .exercise-detail { border-top: 1px solid var(--health-line); padding: 18px 0; }
  .exercise-detail summary { display: flex; justify-content: space-between; cursor: pointer; gap: 20px; font-size: 15px; }
  .exercise-detail summary span { white-space: nowrap; color: var(--secondary-text-color); font-size: 13px; }
  .exercise-detail ol { padding-left: 24px; }
  .exercise-detail li { padding: 7px 0; }
  .exercise-detail li .sub { display: block; font-size: 12px; }
  .exercise-notes { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; }
  @media (max-width: 800px) { .body-layout { gap: 28px; grid-template-columns: minmax(200px, 1fr) minmax(220px, 1fr); } .body-figure { height: 490px; } }
  @media (max-width: 560px) { .body-layout { display: block; } .body-context { padding-top: 24px; } .body-intro h2 { font-size: 23px; } .body-intro { gap: 12px; } .body-figure { height: 480px; } }
  @media (prefers-reduced-motion: reduce) { .body-region path { transition: none; } }
`;
