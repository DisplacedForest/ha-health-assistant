import { LitElement, html, css, svg, nothing } from "lit";
import { renderOverview, renderDetail, overviewStyles } from "./overview-view.js";

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

const PROVIDER_LABELS = {
  ha_entity: "Home Assistant sensors",
  manual: "Manual entries",
  withings: "Withings",
  fitbit: "Fitbit",
  hevy: "Hevy",
};

class HealthAssistantPanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    panel: { attribute: false },
    _overview: { state: true },
    _loading: { state: true },
    _detailMetric: { state: true },
    _detail: { state: true },
    _records: { state: true },
    _showExcluded: { state: true },
    _detailError: { state: true },
    _detailLoading: { state: true },
    _busyId: { state: true },
    _series: { state: true },
    _tab: { state: true },
    _metric: { state: true },
    _days: { state: true },
    _error: { state: true },
    _form: { state: true },
    _saving: { state: true },
  };

  constructor() {
    super();
    this._tab = "overview";
    this._metric = "weight";
    this._days = 30;
    this._form = null;
    this._saving = false;
    this._loadedOnce = false;
    this._showExcluded = false;
    this._records = [];
    this._request = 0;
    this._detailRequest = 0;
    this._dialogSession = 0;
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

  connectedCallback() {
    super.connectedCallback();
    this._timer = window.setInterval(() => {
      if (this.hass && !this._loading) this._refresh();
    }, 60000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.clearInterval(this._timer);
  }

  async _refresh() {
    const request = ++this._request;
    this._loading = true;
    this._error = undefined;
    try {
      const overview = await this.hass.callWS({ type: `${this._domain}/overview` });
      if (request === this._request) this._overview = overview;
      if (this._tab === "trends") await this._loadSeries();
    } catch {
      if (request === this._request) this._error = "Health data could not refresh. Check the integration and try again.";
    } finally {
      if (request === this._request) this._loading = false;
    }
  }

  _providerName(key) {
    return PROVIDER_LABELS[key] || this._overview?.providers.find((p) => p.key === key)?.name || key.replaceAll("_", " ");
  }

  _label(key) {
    return METRICS.find((m) => m.key === key)?.label || key;
  }

  async _openDetail(metric, event) {
    const session = ++this._dialogSession;
    this._opener = event?.currentTarget;
    this._detailMetric = metric;
    this._detail = undefined;
    this._showExcluded = false;
    this._records = [];
    await this.updateComplete;
    if (session !== this._dialogSession) return;
    this.shadowRoot.querySelector("dialog").showModal();
    await this._loadDetail();
  }

  _closeDetail() {
    this._dialogSession++;
    this._detailRequest++;
    this.shadowRoot.querySelector("dialog")?.close();
    this._detailMetric = undefined;
    this._opener?.focus();
  }

  async _loadDetail(observationId, more = false) {
    const request = ++this._detailRequest;
    const metric = this._detailMetric;
    if (!metric) return;
    this._detailLoading = true;
    this._detailError = undefined;
    const current = this._overview?.metrics.find((m) => m.metric === metric)?.current;
    try {
      const records = await this.hass.callWS({
        type: `${this._domain}/observations`, metric,
        excluded: this._showExcluded, limit: 20,
        ...(more && this._nextRecord ? {before_id: this._nextRecord} : {}),
      });
      const id = observationId || (this._showExcluded ? records.observations[0]?.id : current?.id);
      const detail = id ? await this.hass.callWS({type: `${this._domain}/observation_detail`, observation_id: id}) : undefined;
      if (request !== this._detailRequest) return;
      this._records = more ? [...this._records, ...records.observations] : records.observations;
      this._nextRecord = records.next_before_id;
      this._detail = detail;
    } catch {
      if (request === this._detailRequest) this._detailError = "That reading could not load. It may have changed during a sync. Try again.";
    } finally {
      if (request === this._detailRequest) this._detailLoading = false;
    }
  }

  async _toggleExclusion() {
    const reading = this._detail?.observation;
    if (!reading || this._busyId) return;
    const session = this._dialogSession;
    let request = this._detailRequest;
    const ownsDetail = () => session === this._dialogSession && request === this._detailRequest;
    this._busyId = reading.id;
    this._detailError = undefined;
    try {
      await this.hass.callWS({type: `${this._domain}/observation_exclusion`, observation_id: reading.id, excluded: !reading.excluded});
      await this._refresh();
      if (ownsDetail()) {
        request++;
        await this._loadDetail(reading.id);
      }
    } catch {
      if (ownsDetail()) this._detailError = "The reading could not be changed. Refresh and try again.";
    } finally {
      this._busyId = undefined;
      await this.updateComplete;
      if (ownsDetail()) this.shadowRoot.querySelector(".exclusion-control button")?.focus();
    }
  }

  async _loadSeries() {
    const request = (this._seriesRequest || 0) + 1;
    this._seriesRequest = request;
    this._series = undefined;
    try {
      const series = await this.hass.callWS({
        type: `${this._domain}/time_series`,
        metric: this._metric,
        days: this._days,
      });
      if (request === this._seriesRequest) this._series = series;
    } catch {
      if (request === this._seriesRequest) this._error = "Trend data could not load. Try refreshing.";
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


  _metricValue(entry, digits = 1) {
    if (!entry) {
      return html`<span class="empty-value">no data</span>`;
    }
    const shown = this._display(entry.value, entry.unit);
    const unitLabel =
      shown.unit === "count" ? nothing : html`<span class="unit">${shown.unit}</span>`;
    return html`<span class="value">${this._fmt(shown.value, digits)}</span>${unitLabel}`;
  }

  _defaultUnit(metric) {
    if (metric === "weight" || metric === "lean_mass") {
      return this._imperial ? "lb" : "kg";
    }
    if (metric === "distance") {
      return this._imperial ? "mi" : "km";
    }
    if (metric === "body_fat_percentage") {
      return "%";
    }
    if (metric === "active_energy") {
      return "kcal";
    }
    return "";
  }

  _localNow(offsetMinutes = 0) {
    const date = new Date(Date.now() - offsetMinutes * 60000);
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  _openForm(form) {
    this._error = undefined;
    this._form = this._form === form ? null : form;
  }

  _formValue(id) {
    const el = this.shadowRoot.getElementById(id);
    return el ? el.value.trim() : "";
  }

  async _submitMeasurement(ev) {
    ev.preventDefault();
    const value = Number(this._formValue("m-value"));
    if (!Number.isFinite(value)) {
      this._error = "Enter a numeric value";
      return;
    }
    const metric = this._formValue("m-metric");
    const data = { metric, value };
    const unit = this._formValue("m-unit");
    if (unit && unit !== "count") {
      data.unit = unit;
    }
    const when = this._formValue("m-when");
    if (when) {
      data.observed_at = new Date(when).toISOString();
    }
    await this._callAction("add_observation", data);
  }

  async _submitWorkout(ev) {
    ev.preventDefault();
    const workoutType = this._formValue("w-type");
    const start = this._formValue("w-start");
    const end = this._formValue("w-end");
    if (!workoutType || !start || !end) {
      this._error = "Workout type, start, and end are required";
      return;
    }
    const data = { workout_type: workoutType, start: new Date(start).toISOString(), end: new Date(end).toISOString() };
    const title = this._formValue("w-title");
    if (title) {
      data.title = title;
    }
    const energy = this._formValue("w-energy");
    if (energy) {
      data.energy_kcal = Number(energy);
    }
    const distance = this._formValue("w-distance");
    if (distance) {
      data.distance = Number(distance);
      data.distance_unit = this._imperial ? "mi" : "km";
    }
    await this._callAction("add_workout", data);
  }

  async _callAction(action, data) {
    this._saving = true;
    this._error = undefined;
    try {
      await this.hass.callService(this._domain, action, data);
      this._form = null;
      await this._refresh();
    } catch (err) {
      this._error = (err && err.message) || "Unable to save";
    } finally {
      this._saving = false;
    }
  }

  _measurementForm() {
    if (this._form !== "measure") {
      return nothing;
    }
    return html`
      <form class="entry" @submit=${this._submitMeasurement}>
        <label>Metric
          <select id="m-metric" @change=${(ev) => {
            const unitField = this.shadowRoot.getElementById("m-unit");
            if (unitField) {
              unitField.value = this._defaultUnit(ev.target.value);
            }
          }}>
            ${METRICS.map((m) => html`<option value=${m.key}>${m.label}</option>`)}
          </select>
        </label>
        <label>Value
          <input id="m-value" type="number" step="any" required />
        </label>
        <label>Unit
          <input id="m-unit" type="text" .value=${this._defaultUnit("weight")} />
        </label>
        <label>When
          <input id="m-when" type="datetime-local" .value=${this._localNow()} />
        </label>
        <button type="submit" class="primary" ?disabled=${this._saving}>
          ${this._saving ? "Saving" : "Save"}
        </button>
      </form>
    `;
  }

  _workoutForm() {
    if (this._form !== "workout") {
      return nothing;
    }
    return html`
      <form class="entry" @submit=${this._submitWorkout}>
        <label>Type
          <input id="w-type" type="text" placeholder="running, strength, yoga" required />
        </label>
        <label>Title
          <input id="w-title" type="text" placeholder="optional" />
        </label>
        <label>Start
          <input id="w-start" type="datetime-local" .value=${this._localNow(60)} required />
        </label>
        <label>End
          <input id="w-end" type="datetime-local" .value=${this._localNow()} required />
        </label>
        <label>Energy (kcal)
          <input id="w-energy" type="number" step="any" placeholder="optional" />
        </label>
        <label>Distance (${this._imperial ? "mi" : "km"})
          <input id="w-distance" type="number" step="any" placeholder="optional" />
        </label>
        <button type="submit" class="primary" ?disabled=${this._saving}>
          ${this._saving ? "Saving" : "Save"}
        </button>
      </form>
    `;
  }

  _renderOverview() {
    return renderOverview(this);
  }

  _chart() {
    const series = this._series;
    if (!series) return html`<p role="status">Loading trend…</p>`;
    if (series.points.length === 0) {
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
      provider: p.provider,
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
                <title>${this._fmt(p.shown.value)} ${unit} · ${new Date(p.time).toLocaleString()} · ${PROVIDER_LABELS[p.provider] || p.provider}</title>
              </circle>`
          )
        : nothing;
    const providers = [...new Set(series.points.map((p) => p.provider))].map(
      (p) => PROVIDER_LABELS[p] || p
    );
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
      <div class="sub caption">
        ${series.points.length} points${unit === "count" ? "" : ` (${unit})`}
        ${series.downsampled ? " · downsampled" : ""} · from ${providers.join(", ")}
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
          <div class="header-identity">${this.narrow ? html`<button aria-label="Open sidebar" @click=${() => this.dispatchEvent(new window.Event("hass-toggle-menu", { bubbles: true, composed: true }))}>Menu</button>` : nothing}<div><h1>Health</h1><p class="page-subtitle">Your record, at a glance</p></div></div>
          <nav aria-label="Health views">
            <button @click=${this._refresh} ?disabled=${this._loading}>${this._loading ? "Refreshing" : "Refresh"}</button>
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
        ${renderDetail(this)}
      </div>
    `;
  }

  static styles = [overviewStyles, css`
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
    button.active,
    button.primary {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
      border-color: var(--primary-color);
    }
    button.ghost {
      margin-top: 14px;
      border-style: dashed;
    }
    button[disabled] {
      opacity: 0.6;
      cursor: default;
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
    .sub {
      color: var(--secondary-text-color);
      font-size: 0.78em;
      margin-top: 2px;
      text-align: right;
    }
    .sub.caption {
      text-align: left;
    }
    .empty-value {
      color: var(--secondary-text-color);
    }
    .entry {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--divider-color, #444);
    }
    .entry label {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .entry input,
    .entry select {
      background: var(--primary-background-color);
      color: var(--primary-text-color);
      border: 1px solid var(--divider-color, #444);
      border-radius: 8px;
      padding: 7px 9px;
      font: inherit;
      min-width: 0;
    }
    .entry button {
      align-self: end;
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
  `];
}

if (!customElements.get("health-assistant-panel")) {
  customElements.define("health-assistant-panel", HealthAssistantPanel);
}
