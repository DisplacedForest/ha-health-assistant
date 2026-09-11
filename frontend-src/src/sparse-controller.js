export function keyString(key) {
  return JSON.stringify(Object.fromEntries(Object.keys(key).sort().map((name) => [name, key[name]])));
}

export function savedKey(value, domain) {
  try {
    const key = JSON.parse(value);
    const fields = domain === "sleep" ? ["provider", "source_id"] : ["provider", "source_id", "metric", "context", "algorithm_id", "algorithm_version"];
    if (!key || Array.isArray(key) || Object.keys(key).length !== fields.length || !fields.every((name) => Object.hasOwn(key, name))) return undefined;
    if (![key.provider, key.source_id].every((part) => typeof part === "string" && part.length > 0)) return undefined;
    if (domain === "recovery" && (!["resting_heart_rate", "hrv_sdnn", "hrv_rmssd", "respiratory_rate"].includes(key.metric) || !["spot", "sleep_summary", "daily_summary", "unknown"].includes(key.context) || ![key.algorithm_id, key.algorithm_version].every((part) => part === null || typeof part === "string" && part.length > 0))) return undefined;
    return key;
  } catch { return undefined; }
}

export function displayDate(value, zone) {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(value));
  const part = (name) => parts.find((item) => item.type === name).value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function addDays(day, count) {
  const value = new Date(`${day}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + count);
  return value.toISOString().slice(0, 10);
}

export function dayStart(day, zone) {
  const center = Date.parse(`${day}T12:00:00Z`);
  let low = center - 48 * 3600000, high = center + 48 * 3600000;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (displayDate(mid, zone) < day) low = mid + 1;
    else high = mid;
  }
  return new Date(low).toISOString();
}

export function message(error) {
  return error?.code === "unauthorized" ? "You don't have permission to read this history." : "History could not refresh. Check the connection and try again.";
}

export class SparseController {
  constructor(host) {
    this.host = host;
    this.version = 0;
    this.selectionVersion = 0;
    this.detailVersion = 0;
    this.listVersion = 0;
    this.active = true;
    this.domain = undefined;
    this.days = 28;
    this.sources = [];
    this.records = [];
    this.loading = false;
  }

  update() { this.host.requestUpdate?.(); }
  ws(name, data = {}) { return this.host.hass.callWS({ type: `${this.host._domain}/${name}`, ...data }); }
  get timezone() { return this.host.hass?.config?.time_zone || "UTC"; }
  get admin() { return Boolean(this.host.hass?.user?.is_admin); }
  get preference() { return `${this.host._domain}:${this.host.hass?.user?.id || "local"}:${this.domain}:source`; }
  get descriptor() { return this.sources.find((item) => keyString(item.series_key) === keyString(this.selected || {})); }
  get ownsSelection() { return Boolean(this.selected); }

  invalidate() {
    this.version++;
    this.selectionVersion++;
    this.detailVersion++;
    this.listVersion++;
    this.detail = undefined;
    this.detailError = undefined;
    this.detailLoading = false;
    this.listLoading = false;
    this.listError = undefined;
    this.listNotice = undefined;
    this.listDay = undefined;
    this.recordCursor = undefined;
    this.sourceLoading = false;
    this.stale = false;
  }

  disconnect() { this.active = false; this.invalidate(); }
  connect() { this.active = true; }

  navigate(domain) {
    this.invalidate();
    if (!["sleep", "recovery"].includes(domain)) { this.domain = undefined; return; }
    if (this.domain === domain) return;
    this.domain = domain;
    this.endDate = displayDate(Date.now(), this.timezone);
    this.autoEnd = true;
    this.selected = undefined;
    this.sources = [];
    this.records = [];
    this.series = undefined;
    this.lastSuccess = undefined;
    this.error = undefined;
    this.excluded = false;
    try {
      this.selected = savedKey(window.localStorage.getItem(this.preference), domain);
    } catch {}
  }

  select(value) {
    this.invalidate();
    this.selected = savedKey(value, this.domain);
    this.series = undefined;
    this.records = [];
    this.lastSuccess = undefined;
    this.listDay = undefined;
    try {
      if (this.selected) window.localStorage.setItem(this.preference, keyString(this.selected));
      else window.localStorage.removeItem(this.preference);
    } catch {}
    return this.refresh();
  }

  setRange(days, endDate = this.endDate) {
    this.invalidate();
    this.days = days;
    this.endDate = endDate;
    this.autoEnd = endDate === displayDate(Date.now(), this.timezone);
    this.series = undefined;
    this.records = [];
    this.lastSuccess = undefined;
    this.listDay = undefined;
    return this.refresh();
  }

  async refresh(domain = this.domain) {
    if (domain !== this.domain) this.navigate(domain);
    if (!this.domain || !this.active) return;
    if (this.autoEnd) this.endDate = displayDate(Date.now(), this.timezone);
    const version = ++this.version;
    this.listVersion++;
    const current = () => this.active && version === this.version;
    this.loading = true;
    this.sourceLoading = false;
    this.error = undefined;
    this.update();
    try {
      const catalog = await this.ws("derived_sources", { domain: this.domain, limit: 50 });
      if (!current()) return;
      this.sources = catalog.sources;
      this.sourceCursor = catalog.next_cursor;
      if (!this.selected && !this.sourceCursor && this.sources.length === 1) {
        this.selected = this.sources[0].series_key;
        try { window.localStorage.setItem(this.preference, keyString(this.selected)); } catch {}
      }
      if (!this.selected) { this.series = undefined; this.records = []; return; }
      const series = await this.ws("derived_series", { domain: this.domain, series_key: this.selected, days: this.days, end_date: this.endDate, timezone: this.timezone });
      if (!current()) return;
      this.series = series;
      this.lastSuccess = new Date().toISOString();
      this.stale = false;
      await this.loadRecords(false, version);
      if (current() && this.detail && !this.detailLoading && !this.mutation) await this.openDetail(this.detail.id, undefined, true, false);
    } catch (error) {
      if (current()) { this.error = message(error); this.stale = Boolean(this.series); }
    } finally {
      if (current()) { this.loading = false; this.update(); }
    }
  }

  async moreSources() {
    if (!this.sourceCursor || this.sourceLoading || this.loading) return;
    const version = this.version;
    this.sourceLoading = true;
    try {
      const page = await this.ws("derived_sources", { domain: this.domain, limit: 50, cursor: this.sourceCursor });
      if (version !== this.version || !this.active) return;
      this.sources = [...this.sources, ...page.sources];
      this.sourceCursor = page.next_cursor;
    } catch (error) {
      if (version !== this.version || !this.active) return;
      if (error?.code === "stale_cursor") await this.refresh();
      else this.error = message(error);
    } finally { if (version === this.version && this.active) { this.sourceLoading = false; this.update(); } }
  }

  async loadRecords(more = false, version = this.version, retry = true) {
    if (!this.selected || !this.active) return;
    const request = ++this.listVersion;
    const current = () => version === this.version && request === this.listVersion && this.active;
    const startDay = this.listDay || addDays(this.endDate, 1 - this.days);
    const endDay = addDays(this.listDay || this.endDate, 1);
    const start = dayStart(startDay, this.timezone), end = dayStart(endDay, this.timezone);
    this.listLoading = true;
    this.listError = undefined;
    this.update();
    try {
      const result = start === end ? { sessions: [], observations: [], next_cursor: null } : await this.ws(this.domain === "sleep" ? "sleep_sessions" : "recovery_observations", {
        start, end, excluded: Boolean(this.excluded), limit: 50,
        ...(this.domain === "sleep" ? { source: this.selected, date_basis: this.listDay ? "ended_at" : "overlap" } : { series: this.selected }),
        ...(more && this.recordCursor ? { cursor: this.recordCursor } : {}),
      });
      if (!current()) return;
      this.records = result.sessions || result.observations;
      this.recordCursor = result.next_cursor;
      this.listPage = more ? (this.listPage || 1) + 1 : 1;
    } catch (error) {
      if (!current()) return;
      if (error?.code === "stale_cursor" && retry) {
        this.listNotice = "History changed. The list restarted at its first page.";
        await this.loadRecords(false, version, false);
      } else this.listError = message(error);
    } finally { if (current()) { this.listLoading = false; this.update(); } }
  }

  drill(day) { this.listDay = day; this.excluded = false; return this.loadRecords(); }
  showExcluded(value) { this.excluded = value; return this.loadRecords(); }

  closeDetail() {
    this.detailVersion++;
    this.detail = undefined;
    this.detailLoading = false;
    this.detailError = undefined;
    this.detailNotice = undefined;
    this.update();
    this.opener?.focus();
  }

  async openDetail(id, event, retry = true, focus = true) {
    this.opener = event?.currentTarget || this.opener;
    const version = this.selectionVersion;
    const request = ++this.detailVersion;
    const current = () => this.active && version === this.selectionVersion && request === this.detailVersion;
    if (focus) this.detail = undefined;
    this.detailId = id;
    this.detailError = undefined;
    this.detailNotice = undefined;
    this.detailLoading = true;
    this.intervalPage = 0;
    this.update();
    try {
      const name = this.domain === "sleep" ? "sleep_session" : "recovery_observation";
      const selector = this.domain === "sleep" ? { session_id: id, limit: 128 } : { record_id: id };
      const detail = await this.ws(name, selector);
      if (!current()) return;
      this.detail = { ...detail, stages: [], in_bed_intervals: [], completeTimeline: this.domain !== "sleep" };
      this.update();
      await this.host.updateComplete;
      if (!current()) return;
      if (focus) this.host.shadowRoot?.querySelector(".sparse-detail h3")?.focus();
      if (this.domain === "sleep" && detail.status !== "deleted") {
        for (const kind of ["stages", "in_bed_intervals"]) {
          let page = kind === "stages" ? detail : await this.ws(name, { ...selector, kind });
          let pages = 0;
          while (page) {
            if (!current()) return;
            if (page.source_revision !== detail.source_revision || page.payload_hash !== detail.payload_hash || page.started_at !== detail.started_at || page.ended_at !== detail.ended_at) throw { code: "stale_cursor" };
            if (++pages > 32 || this.detail[kind].length + (page.intervals?.length || 0) > 4096) throw { code: "invalid_detail" };
            this.detail = { ...this.detail, [kind]: [...this.detail[kind], ...(page.intervals || [])] };
            this.update();
            page = page.next_cursor ? await this.ws(name, { ...selector, kind, cursor: page.next_cursor }) : null;
          }
        }
        if (!current()) return;
        this.detail = { ...this.detail, completeTimeline: true };
      }
    } catch (error) {
      if (!current()) return;
      this.detail = undefined;
      if (error?.code === "stale_cursor" && retry) {
        await this.openDetail(id, undefined, false, focus);
        if (version === this.selectionVersion && this.detailId === id && this.active) { this.detailNotice = "This record changed. Its detail was reloaded."; this.update(); }
      } else this.detailError = error?.code === "unauthorized" ? "You don't have permission to read this record." : "This record could not load. Refresh it and try again.";
    } finally { if (current()) { this.detailLoading = false; this.update(); } }
  }

  async exclude() {
    const record = this.detail;
    if (!record || !this.admin || record.status === "deleted" || this.mutation) return;
    const request = this.detailVersion, domain = this.domain, selection = this.selectionVersion;
    const current = () => this.active && this.domain === domain && this.detailVersion === request;
    this.mutation = record.id;
    this.detailError = undefined;
    this.update();
    try {
      await this.ws(domain === "sleep" ? "sleep_session_exclusion" : "recovery_observation_exclusion", {
        ...(domain === "sleep" ? { session_id: record.id } : { record_id: record.id }),
        excluded: !record.locally_excluded, expected_source_revision: record.source_revision, expected_payload_hash: record.payload_hash,
      });
      if (!this.active || this.domain !== domain || this.selectionVersion !== selection) return;
      const reconcileDetail = this.detailId === record.id && Boolean(this.detail || this.detailLoading);
      const detailRequest = reconcileDetail ? ++this.detailVersion : undefined;
      await this.refresh();
      if (reconcileDetail && this.active && this.domain === domain && this.selectionVersion === selection && this.detailVersion === detailRequest) await this.openDetail(record.id, undefined, true, false);
    } catch (error) {
      if (!current()) return;
      if (error?.code === "revision_conflict") {
        const selection = this.selectionVersion;
        await this.openDetail(record.id);
        if (this.active && this.domain === domain && this.selectionVersion === selection && this.detailId === record.id) this.detailNotice = "The record changed. Review the refreshed details before choosing the action again.";
      } else this.detailError = error?.code === "unauthorized" ? "Only an administrator can change local exclusions." : "The exclusion could not be confirmed. Refresh before trying again.";
    } finally { this.mutation = undefined; this.update(); }
  }
}
