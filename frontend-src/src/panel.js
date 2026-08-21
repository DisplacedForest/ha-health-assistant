import { LitElement, html, css, svg, nothing } from "lit";

const KG_TO_LB = 2.204622621848776;
const M_TO_MI = 1 / 1609.344;

const METRICS = [
  { key: "weight", label: "Weight" },
  { key: "body_fat_percentage", label: "Body fat" },
  { key: "lean_mass", label: "Lean mass" },
  { key: "steps", label: "Steps" },
  { key: "distance", label: "Distance" },
  { key: "active_energy", label: "Active energy" },
];

const RANGES = [7, 30, 90];

class HealthAssistantPanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    panel: { attribute: false },
    _summary: { state: true },
    _series: { state: true },
    _tab: { state: true },
    _metric: { state: true },
    _days: { state: true },
    _error: { state: true },
  };

  constructor() {
    super();
    this._tab = "overview";
    this._metric = "weight";
    this._days = 30;
    this._loadedOnce = false;
  }

  get _domain() {
    return (this.panel && this.panel.config && this.panel.config.domain) || "health_assistant";
  }

  get _imperial() {
    return Boolean(
      this.hass &&
        this.hass.config &&
        this.hass.config.unit_system &&
        this.hass.config.unit_system.length === "mi"
    );
  }

  updated(changed) {
    if (changed.has("hass") && this.hass && !this._loadedOnce) {
      this._loadedOnce = true;
      this._refresh();
    }
  }

  async _refresh() {
    this._error = undefined;
    try {
      this._summary = await this.hass.callWS({ type: `${this._domain}/summary` });
      await this._loadSeries();
    } catch (err) {
      this._error = (err && err.message) || "Unable to load health data";
    }
  }

  async _loadSeries() {
    try {
      this._series = await this.hass.callWS({
        type: `${this._domain}/time_series`,
        metric: this._metric,
        days: this._days,
      });
    } catch (err) {
      this._error = (err && err.message) || "Unable to load trend data";
    }
  }

  _setTab(tab) {
    this._tab = tab;
    if (tab === "trends") {
      this._loadSeries();
    } else {
      this._refresh();
    }
  }

  _setMetric(metric) {
    this._metric = metric;
    this._loadSeries();
  }

  _setDays(days) {
    this._days = days;
    this._loadSeries();
  }

  _display(value, unit) {
    if (value === null || value === undefined) {
      return null;
    }
    if (unit === "kg" && this._imperial) {
      return { value: value * KG_TO_LB, unit: "lb" };
    }
    if (unit === "m" && this._imperial) {
      return { value: value * M_TO_MI, unit: "mi" };
    }
    if (unit === "m" && value >= 1000) {
      return { value: value / 1000, unit: "km" };
    }
    return { value, unit };
  }

  _fmt(value, digits = 1) {
    return new Intl.NumberFormat(undefined, {
      maximumFractionDigits: digits,
    }).format(value);
  }

  _when(iso) {
    const date = new Date(iso);
    const now = new Date();
    const days = Math.floor((now - date) / 86400000);
    if (days <= 0) {
      return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
    }
    if (days === 1) {
      return "yesterday";
    }
    if (days < 7) {
      return `${days} days ago`;
    }
    return date.toLocaleDateString();
  }

  _provenance(entry) {
    if (!entry) {
      return nothing;
    }
    return html`<div class="prov">${entry.source} · ${this._when(entry.observed_at)}</div>`;
  }

  _metricValue(entry, digits = 1) {
    if (!entry) {
      return html`<span class="empty-value">no data</span>`;
    }
    const shown = this._display(entry.value, entry.unit);
    return html`<span class="value">${this._fmt(shown.value, digits)}</span>
      <span class="unit">${shown.unit}</span>`;
  }

  _renderEmptyState() {
    return html`
      <div class="card guide">
        <h2>No health data yet</h2>
        <p>
          Health Assistant builds a local health record from sources you already
          have. Two ways to get started:
        </p>
        <p>
          <b>Map sensors.</b> Open Settings, then Devices &amp; services, choose
          Health Assistant, and press Configure. Pick the sensors that feed each
          metric, like a smart scale's weight sensor.
        </p>
        <p>
          <b>Add records directly.</b> Call the
          <code>${this._domain}.add_observation</code> or
          <code>${this._domain}.add_workout</code> actions from Developer Tools
          or an automation, including backfill with past timestamps.
        </p>
      </div>
    `;
  }

  _renderOverview() {
    const s = this._summary;
    if (!s) {
      return nothing;
    }
    const empty =
      !s.current_weight &&
      !s.current_body_fat &&
      !s.steps_today &&
      !s.active_energy_today &&
      !s.latest_workout;
    if (empty) {
      return this._renderEmptyState();
    }
    const workout = s.latest_workout;
    return html`
      <div class="grid">
        <div class="card">
          <h2>Body</h2>
          <div class="row">
            <span class="label">Weight</span>
            <span>${this._metricValue(s.current_weight)}</span>
          </div>
          ${this._provenance(s.current_weight)}
          <div class="row">
            <span class="label">Body fat</span>
            <span>${this._metricValue(s.current_body_fat)}</span>
          </div>
          ${this._provenance(s.current_body_fat)}
        </div>
        <div class="card">
          <h2>Today</h2>
          <div class="row">
            <span class="label">Steps</span>
            <span>${this._metricValue(s.steps_today, 0)}</span>
          </div>
          ${this._provenance(s.steps_today)}
          <div class="row">
            <span class="label">Active energy</span>
            <span>${this._metricValue(s.active_energy_today, 0)}</span>
          </div>
          ${this._provenance(s.active_energy_today)}
        </div>
        <div class="card">
          <h2>Latest workout</h2>
          ${workout
            ? html`
                <div class="row">
                  <span class="label">${workout.title || workout.workout_type}</span>
                  <span class="value">${this._fmt(workout.duration_seconds / 60, 0)}
                    <span class="unit">min</span></span>
                </div>
                <div class="prov">
                  ${workout.workout_type} · ${this._when(workout.started_at)} ·
                  ${workout.provider}
                </div>
                <div class="row">
                  <span class="label">Last 7 days</span>
                  <span class="value">${s.workouts_last_7_days ?? "no data"}</span>
                </div>
              `
            : html`<p class="empty-value">
                No workouts recorded yet. Use the
                <code>${this._domain}.add_workout</code> action.
              </p>`}
        </div>
      </div>
    `;
  }

  _chart() {
    const series = this._series;
    if (!series || series.points.length === 0) {
      return html`<p class="empty-value">
        No ${this._metricLabel().toLowerCase()} data in the last ${this._days} days.
      </p>`;
    }
    const width = 640;
    const height = 260;
    const pad = { left: 54, right: 16, top: 16, bottom: 34 };
    const points = series.points.map((p) => ({
      time: new Date(p.t).getTime(),
      shown: this._display(p.v, series.unit),
      source: p.source,
      raw: p,
    }));
    const unit = points[0].shown.unit;
    const values = points.map((p) => p.shown.value);
    const times = points.map((p) => p.time);
    const vMin = Math.min(...values);
    const vMax = Math.max(...values);
    const vSpan = vMax - vMin || Math.abs(vMax) * 0.1 || 1;
    const tMin = Math.min(...times);
    const tMax = Math.max(...times);
    const tSpan = tMax - tMin || 1;
    const x = (t) => pad.left + ((t - tMin) / tSpan) * (width - pad.left - pad.right);
    const y = (v) =>
      height - pad.bottom - ((v - (vMin - vSpan * 0.05)) / (vSpan * 1.1)) * (height - pad.top - pad.bottom);
    const path = points
      .map((p, i) => `${i === 0 ? "M" : "L"}${x(p.time).toFixed(1)},${y(p.shown.value).toFixed(1)}`)
      .join(" ");
    const dots =
      points.length <= 120
        ? points.map(
            (p) => svg`<circle cx="${x(p.time)}" cy="${y(p.shown.value)}" r="3">
                <title>${this._fmt(p.shown.value)} ${unit} · ${new Date(p.time).toLocaleString()} · ${p.source}</title>
              </circle>`
          )
        : nothing;
    const providers = [...new Set(series.points.map((p) => p.provider))];
    return html`
      <svg viewBox="0 0 ${width} ${height}" role="img">
        <line class="axis" x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}"></line>
        <line class="axis" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
        <text class="tick" x="${pad.left - 8}" y="${y(vMax) + 4}" text-anchor="end">${this._fmt(vMax)}</text>
        <text class="tick" x="${pad.left - 8}" y="${y(vMin) + 4}" text-anchor="end">${this._fmt(vMin)}</text>
        <text class="tick" x="${pad.left}" y="${height - 10}">${new Date(tMin).toLocaleDateString()}</text>
        <text class="tick" x="${width - pad.right}" y="${height - 10}" text-anchor="end">${new Date(tMax).toLocaleDateString()}</text>
        <path class="line" d="${path}"></path>
        ${dots}
      </svg>
      <div class="prov">
        ${series.points.length} points (${unit})
        ${series.downsampled ? " · downsampled" : ""} · source${providers.length > 1 ? "s" : ""}:
        ${providers.join(", ")}
      </div>
    `;
  }

  _metricLabel() {
    const metric = METRICS.find((m) => m.key === this._metric);
    return metric ? metric.label : this._metric;
  }

  _renderTrends() {
    return html`
      <div class="card wide">
        <div class="selector">
          ${METRICS.map(
            (m) => html`<button
              class=${this._metric === m.key ? "active" : ""}
              @click=${() => this._setMetric(m.key)}
            >
              ${m.label}
            </button>`
          )}
        </div>
        <div class="selector">
          ${RANGES.map(
            (d) => html`<button
              class=${this._days === d ? "active" : ""}
              @click=${() => this._setDays(d)}
            >
              ${d} days
            </button>`
          )}
        </div>
        ${this._chart()}
      </div>
    `;
  }

  render() {
    return html`
      <div class="wrapper">
        <header>
          <h1>Health</h1>
          <nav>
            <button
              class=${this._tab === "overview" ? "active" : ""}
              @click=${() => this._setTab("overview")}
            >
              Overview
            </button>
            <button
              class=${this._tab === "trends" ? "active" : ""}
              @click=${() => this._setTab("trends")}
            >
              Trends
            </button>
          </nav>
        </header>
        ${this._error
          ? html`<div class="card error">${this._error}</div>`
          : nothing}
        ${this._tab === "overview" ? this._renderOverview() : this._renderTrends()}
      </div>
    `;
  }

  static styles = css`
    :host {
      display: block;
      height: 100%;
      overflow-y: auto;
      background: var(--primary-background-color);
      color: var(--primary-text-color);
      font-family: var(--paper-font-body1_-_font-family, sans-serif);
    }
    .wrapper {
      max-width: 1100px;
      margin: 0 auto;
      padding: 16px;
      box-sizing: border-box;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
    }
    h1 {
      font-size: 1.6em;
      font-weight: 400;
      margin: 0;
    }
    nav,
    .selector {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .selector {
      margin-bottom: 12px;
    }
    button {
      background: var(--card-background-color, #fff);
      color: var(--primary-text-color);
      border: 1px solid var(--divider-color, #444);
      border-radius: 16px;
      padding: 6px 14px;
      cursor: pointer;
      font: inherit;
    }
    button.active {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
      border-color: var(--primary-color);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }
    .card {
      background: var(--card-background-color, #fff);
      border-radius: 12px;
      box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0, 0, 0, 0.2));
      padding: 16px 20px;
    }
    .card.wide {
      width: 100%;
      box-sizing: border-box;
    }
    .card.error {
      border-left: 4px solid var(--error-color, #b71c1c);
      margin-bottom: 16px;
    }
    .card.guide p {
      line-height: 1.5;
    }
    h2 {
      font-size: 1.05em;
      font-weight: 500;
      margin: 0 0 12px;
      color: var(--secondary-text-color);
    }
    .row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-top: 10px;
    }
    .label {
      color: var(--secondary-text-color);
    }
    .value {
      font-size: 1.4em;
      font-weight: 500;
    }
    .unit {
      color: var(--secondary-text-color);
      font-size: 0.9em;
      margin-left: 2px;
    }
    .prov {
      color: var(--secondary-text-color);
      font-size: 0.78em;
      margin-top: 2px;
      text-align: right;
    }
    .empty-value {
      color: var(--secondary-text-color);
    }
    code {
      background: var(--secondary-background-color, rgba(127, 127, 127, 0.2));
      border-radius: 4px;
      padding: 1px 5px;
    }
    svg {
      width: 100%;
      height: auto;
      margin-top: 8px;
    }
    .axis {
      stroke: var(--divider-color, #666);
      stroke-width: 1;
    }
    .tick {
      fill: var(--secondary-text-color);
      font-size: 11px;
    }
    .line {
      fill: none;
      stroke: var(--primary-color, #03a9f4);
      stroke-width: 2;
    }
    circle {
      fill: var(--primary-color, #03a9f4);
    }
  `;
}

if (!customElements.get("health-assistant-panel")) {
  customElements.define("health-assistant-panel", HealthAssistantPanel);
}
