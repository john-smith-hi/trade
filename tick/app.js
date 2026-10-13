(function () {
  "use strict";

  const FILTER_KEY = "tick-filters";
  const STORE_KEY = "tick-imports";
  const PAGE_SIZE = 100;
  const PROXY = "proxy.php";
  const MAX_LOCAL = 4 * 1024 * 1024;

  const state = {
    files: [],
    apiOk: false,
    dir: "data/GOLD/tick",
    symbol: "",
    file: "",
    from: "",
    to: "",
    fromTime: "00:00:00",
    toTime: "23:59:59",
    dateError: "",
    page: 0,
    result: null,
    busy: false,
  };

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function pad(n) { return String(n).padStart(2, "0"); }

  function setMsg(id, text) {
    const el = $(id);
    if (!el) return;
    el.textContent = text || "";
    el.classList.toggle("hidden", !text);
  }

  function setStatus(text, kind) {
    const el = $("apiStatus");
    el.textContent = text;
    el.className = "api-status" + (kind ? " " + kind : "");
  }

  function fmtSize(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(1) + " MB";
  }

  function fmtPx(n) {
    if (n == null || !Number.isFinite(n)) return "—";
    const a = Math.abs(n);
    const d = a >= 1000 ? 2 : a >= 100 ? 3 : 5;
    return n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  function fmtSpread(n) {
    if (n == null || !Number.isFinite(n)) return "—";
    return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 3 });
  }

  function fmtCount(n) {
    return Number(n || 0).toLocaleString("en-US");
  }

  function safeFileName(name) {
    const base = String(name || "").split(/[/\\]/).pop();
    const clean = base.replace(/[\u0000-\u001F\u007F<>:"|?*]/g, "_").trim().slice(0, 180);
    if (!clean) return "pasted.csv";
    return /\.csv$/i.test(clean) ? clean : clean + ".csv";
  }

  function splitCsvLine(line) {
    const out = [];
    let cur = "";
    let inQ = false;
    for (let i = 0; i < line.length; i++) {
      const c = line.charAt(i);
      if (c === '"') {
        inQ = !inQ;
        continue;
      }
      if (c === "," && !inQ) {
        out.push(cur);
        cur = "";
        continue;
      }
      cur += c;
    }
    out.push(cur);
    return out;
  }

  function parseUtcMs(raw) {
    let s = String(raw || "").trim().replace(/^"|"$/g, "");
    if (!s) return null;
    if (/^\d{4}-\d{2}-\d{2} /.test(s)) s = s.replace(" ", "T");
    const ms = Date.parse(s);
    return Number.isFinite(ms) ? ms : null;
  }

  function fmtVnMs(ms) {
    if (ms == null || !Number.isFinite(ms)) return "";
    const d = new Date(ms + 7 * 3600 * 1000);
    const base = pad(d.getUTCDate()) + "/" + pad(d.getUTCMonth() + 1) + "/" + d.getUTCFullYear()
      + " " + pad(d.getUTCHours()) + ":" + pad(d.getUTCMinutes()) + ":" + pad(d.getUTCSeconds());
    const frac = Math.floor(ms % 1000);
    if (!frac) return base;
    return base + "." + String(frac);
  }

  function headerCols(headerLine) {
    const row = splitCsvLine(headerLine).map(function (c) {
      return c.trim().replace(/^"|"$/g, "").replace(/^\ufeff/, "").toLowerCase();
    });
    function find() {
      for (let i = 0; i < arguments.length; i++) {
        const idx = row.indexOf(arguments[i]);
        if (idx >= 0) return idx;
      }
      return -1;
    }
    const ts = find("timestamp", "time", "datetime");
    const bid = find("bid");
    const ask = find("ask");
    const symbol = find("symbol");
    if (ts < 0 || bid < 0 || ask < 0) return null;
    return { ts: ts, bid: bid, ask: ask, symbol: symbol };
  }

  function parseTickCsv(text, fileName) {
    const lines = String(text || "").split(/\r?\n/);
    if (!lines.length) return { ok: false, error: "CSV trống.", ticks: [] };
    const cols = headerCols(lines[0]);
    if (!cols) return { ok: false, error: "CSV cần cột Timestamp, Bid, Ask.", ticks: [] };
    const ticks = [];
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      const row = splitCsvLine(line);
      const need = Math.max(cols.ts, cols.bid, cols.ask);
      if (row.length <= need) continue;
      const t = parseUtcMs(row[cols.ts]);
      const bid = Number(row[cols.bid]);
      const ask = Number(row[cols.ask]);
      if (t == null || !Number.isFinite(bid) || !Number.isFinite(ask)) continue;
      const symbol = cols.symbol >= 0 && row[cols.symbol] ? String(row[cols.symbol]).trim().replace(/^"|"$/g, "") : "";
      ticks.push({
        t: t,
        ts_vn: fmtVnMs(t),
        symbol: symbol,
        bid: bid,
        ask: ask,
        spread: Math.round((ask - bid) * 1e6) / 1e6,
        file: fileName,
      });
    }
    if (!ticks.length) return { ok: false, error: "Không đọc được dòng tick nào.", ticks: [] };
    ticks.sort(function (a, b) { return a.t - b.t; });
    return {
      ok: true,
      error: "",
      ticks: ticks,
      symbol: ticks[0].symbol,
      first_vn: ticks[0].ts_vn,
      last_vn: ticks[ticks.length - 1].ts_vn,
    };
  }

  function readStore() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return [];
      return arr.filter(function (x) {
        return x && typeof x.name === "string" && typeof x.text === "string";
      });
    } catch (e) {
      return [];
    }
  }

  function writeStore(records) {
    const payload = JSON.stringify(records.map(function (r) {
      return { name: r.name, text: r.text, importedAt: r.importedAt || Date.now() };
    }));
    if (payload.length > MAX_LOCAL + 512 * 1024) {
      throw new Error("Hết chỗ localStorage (~4 MB). Xóa bớt file đã nạp.");
    }
    try {
      localStorage.setItem(STORE_KEY, payload);
    } catch (e) {
      throw new Error("Không ghi được localStorage (hết dung lượng hoặc trình duyệt chặn).");
    }
  }

  function fileKey(f) {
    return (f.source || "disk") + ":" + f.name;
  }

  function emptyResult(spec) {
    return {
      rows: [],
      total: 0,
      offset: spec ? spec.offset : 0,
      limit: PAGE_SIZE,
      stats: { count: 0 },
      chart: [],
      files: [],
      from_vn: spec ? spec.fromVn : "",
      to_vn: spec ? spec.toVn : "",
    };
  }

  function resultFromTicks(ticks, spec) {
    const out = emptyResult(spec);
    if (!ticks.length) return out;
    let bidMin = ticks[0].bid, bidMax = ticks[0].bid;
    let askMin = ticks[0].ask, askMax = ticks[0].ask;
    let spreadMin = ticks[0].spread, spreadMax = ticks[0].spread, spreadSum = 0;
    const files = {};
    const nBucket = 800;
    const span = Math.max(1, spec.toMs - spec.fromMs);
    const buckets = {};
    ticks.forEach(function (tick) {
      if (tick.bid < bidMin) bidMin = tick.bid;
      if (tick.bid > bidMax) bidMax = tick.bid;
      if (tick.ask < askMin) askMin = tick.ask;
      if (tick.ask > askMax) askMax = tick.ask;
      if (tick.spread < spreadMin) spreadMin = tick.spread;
      if (tick.spread > spreadMax) spreadMax = tick.spread;
      spreadSum += tick.spread;
      files[tick.file] = 1;
      const idx = Math.min(nBucket - 1, Math.floor(((tick.t - spec.fromMs) / span) * nBucket));
      buckets[idx] = { t: tick.t, bid: tick.bid, ask: tick.ask, bid_min: tick.bid, bid_max: tick.bid, ask_min: tick.ask, ask_max: tick.ask };
    });
    const first = ticks[0];
    const last = ticks[ticks.length - 1];
    out.total = ticks.length;
    out.rows = ticks.slice(spec.offset, spec.offset + PAGE_SIZE);
    out.files = Object.keys(files);
    out.chart = Object.keys(buckets).sort(function (a, b) { return Number(a) - Number(b); }).map(function (k) { return buckets[k]; });
    out.stats = {
      count: ticks.length,
      first_vn: first.ts_vn,
      last_vn: last.ts_vn,
      symbol: first.symbol || spec.symbol || "",
      bid_min: bidMin,
      bid_max: bidMax,
      bid_open: first.bid,
      bid_close: last.bid,
      ask_min: askMin,
      ask_max: askMax,
      ask_open: first.ask,
      ask_close: last.ask,
      spread_min: spreadMin,
      spread_max: spreadMax,
      spread_avg: Math.round((spreadSum / ticks.length) * 1e6) / 1e6,
    };
    return out;
  }

  function queryLocal(spec, localName) {
    const ticks = [];
    state.files.forEach(function (f) {
      if (f.source !== "local" || !f.ticks) return;
      if (localName && f.name !== localName) return;
      f.ticks.forEach(function (tick) {
        if (tick.t < spec.fromMs || tick.t > spec.toMs) return;
        if (spec.symbol && tick.symbol !== spec.symbol) return;
        ticks.push(tick);
      });
    });
    ticks.sort(function (a, b) { return a.t - b.t; });
    return resultFromTicks(ticks, spec);
  }

  function mergeResults(localRes, apiRes, spec) {
    if (!localRes.total) return apiRes.total ? apiRes : localRes;
    if (!apiRes.total) return localRes;
    const files = {};
    (localRes.files || []).concat(apiRes.files || []).forEach(function (n) { files[n] = 1; });
    const ls = localRes.stats || {};
    const as = apiRes.stats || {};
    function pickMin(a, b) {
      if (a == null) return b;
      if (b == null) return a;
      return a < b ? a : b;
    }
    function pickMax(a, b) {
      if (a == null) return b;
      if (b == null) return a;
      return a > b ? a : b;
    }
    const chart = (localRes.chart || []).concat(apiRes.chart || []).sort(function (a, b) { return a.t - b.t; });
    const rows = (localRes.rows || []).concat(apiRes.rows || []).sort(function (a, b) { return a.t - b.t; });
    const count = (ls.count || 0) + (as.count || 0);
    return {
      rows: spec.offset === 0 ? rows.slice(0, PAGE_SIZE) : (apiRes.rows || []),
      total: count,
      offset: spec.offset,
      limit: PAGE_SIZE,
      chart: chart,
      files: Object.keys(files),
      from_vn: spec.fromVn,
      to_vn: spec.toVn,
      stats: {
        count: count,
        first_vn: ls.first_vn && (!as.first_vn || ls.first_vn < as.first_vn) ? ls.first_vn : (as.first_vn || ls.first_vn || ""),
        last_vn: ls.last_vn && (!as.last_vn || ls.last_vn > as.last_vn) ? ls.last_vn : (as.last_vn || ls.last_vn || ""),
        symbol: as.symbol || ls.symbol || spec.symbol || "",
        bid_min: pickMin(ls.bid_min, as.bid_min),
        bid_max: pickMax(ls.bid_max, as.bid_max),
        bid_open: ls.bid_open != null ? ls.bid_open : as.bid_open,
        bid_close: as.bid_close != null ? as.bid_close : ls.bid_close,
        ask_min: pickMin(ls.ask_min, as.ask_min),
        ask_max: pickMax(ls.ask_max, as.ask_max),
        ask_open: ls.ask_open != null ? ls.ask_open : as.ask_open,
        ask_close: as.ask_close != null ? as.ask_close : ls.ask_close,
        spread_min: pickMin(ls.spread_min, as.spread_min),
        spread_max: pickMax(ls.spread_max, as.spread_max),
        spread_avg: count ? Math.round((((ls.spread_avg || 0) * (ls.count || 0) + (as.spread_avg || 0) * (as.count || 0)) / count) * 1e6) / 1e6 : null,
      },
    };
  }

  function parseTime(raw) {
    const s = String(raw || "").trim();
    if (!s) return "";
    const m = /^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$/.exec(s);
    if (!m) return null;
    const h = Number(m[1]);
    const mi = Number(m[2]);
    const se = Number(m[3] || 0);
    if (h > 23 || mi > 59 || se > 59) return null;
    return pad(h) + ":" + pad(mi) + ":" + pad(se);
  }

  function normalizeTime(raw, fallback) {
    const parsed = parseTime(raw);
    if (parsed) return parsed;
    if (!String(raw || "").trim()) return fallback;
    return fallback;
  }

  function maskTime(digits) {
    const d = String(digits || "").slice(0, 6);
    if (d.length > 4) return d.slice(0, 2) + ":" + d.slice(2, 4) + ":" + d.slice(4);
    if (d.length > 2) return d.slice(0, 2) + ":" + d.slice(2);
    return d;
  }

  function onTimeInput(id, keyName, fallback) {
    const el = $(id);
    const digits = el.value.replace(/\D/g, "").slice(0, 6);
    el.value = maskTime(digits);
    el.classList.toggle("date-bad", digits.length === 6 && !parseTime(el.value));
    if (digits.length === 6 && parseTime(el.value)) state[keyName] = parseTime(el.value);
    else if (!digits) state[keyName] = fallback;
  }

  function onTimeBlur(id, keyName, fallback) {
    const el = $(id);
    const parsed = parseTime(el.value);
    if (parsed) {
      el.value = parsed;
      el.classList.remove("date-bad");
      state[keyName] = parsed;
      return;
    }
    if (!el.value.trim()) {
      el.value = fallback;
      el.classList.remove("date-bad");
      state[keyName] = fallback;
      return;
    }
    el.classList.add("date-bad");
  }

  function toDisplayDate(key) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(key || "");
    if (!m) return "";
    return m[3] + "/" + m[2] + "/" + m[1];
  }

  function parseDisplayDate(text) {
    const raw = String(text || "").trim();
    if (!raw) return "";
    const dmy = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(raw);
    const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
    let d, mo, y;
    if (dmy) {
      d = Number(dmy[1]); mo = Number(dmy[2]); y = Number(dmy[3]);
    } else if (iso) {
      y = Number(iso[1]); mo = Number(iso[2]); d = Number(iso[3]);
    } else {
      return null;
    }
    if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
    const dt = new Date(Date.UTC(y, mo - 1, d));
    if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return null;
    return y + "-" + pad(mo) + "-" + pad(d);
  }

  function maskDate(digits, trailingSlash) {
    const d = String(digits || "").slice(0, 8);
    let out = d;
    if (d.length > 4) out = d.slice(0, 2) + "/" + d.slice(2, 4) + "/" + d.slice(4);
    else if (d.length > 2) out = d.slice(0, 2) + "/" + d.slice(2);
    if (trailingSlash && (d.length === 2 || d.length === 4)) out += "/";
    return out;
  }

  function caretAfterDigits(masked, count) {
    if (count <= 0) return 0;
    let seen = 0;
    for (let i = 0; i < masked.length; i++) {
      if (/\d/.test(masked.charAt(i))) seen++;
      if (seen === count) return i + 1;
    }
    return masked.length;
  }

  function expandSmartDate(digits) {
    let d = digits;
    if (d.length === 1 && d >= "4" && d <= "9") d = "0" + d;
    if (d.length === 3 && d.charAt(2) >= "2" && d.charAt(2) <= "9") d = d.slice(0, 2) + "0" + d.charAt(2);
    return d.slice(0, 8);
  }

  function paintDate(el, masked, digitCaret) {
    el.value = masked;
    el.dataset.prev = masked;
    const pos = caretAfterDigits(masked, digitCaret);
    el.setSelectionRange(pos, pos);
  }

  function pickerFor(id) {
    return document.querySelector('.date-cal-native[data-date-for="' + id + '"]');
  }

  function syncPicker(id, key) {
    const picker = pickerFor(id);
    if (picker) picker.value = key || "";
  }

  function markDateFields() {
    ["filterFrom", "filterTo"].forEach(function (id) {
      const raw = $(id).value.trim();
      const key = raw ? parseDisplayDate(raw) : "";
      $(id).classList.toggle("date-bad", !!raw && !key);
      syncPicker(id, key || "");
    });
    const bad = $("filterFrom").classList.contains("date-bad") || $("filterTo").classList.contains("date-bad");
    state.dateError = bad ? "Ngày phải theo dạng dd/mm/yyyy." : "";
  }

  function applyDateEdit(el) {
    const prev = el.dataset.prev || "";
    const raw = el.value;
    const start = el.selectionStart == null ? raw.length : el.selectionStart;
    const atEnd = start >= raw.length;
    const deleting = raw.length < prev.length;
    let digits = raw.replace(/\D/g, "");
    let caretDigits = raw.slice(0, start).replace(/\D/g, "").length;
    const prevDigits = prev.replace(/\D/g, "");
    if (deleting && digits.length === prevDigits.length) {
      const onlyTrailingSlash = prev.charAt(prev.length - 1) === "/" && raw === prev.slice(0, -1);
      if (!onlyTrailingSlash && caretDigits > 0) {
        digits = digits.slice(0, caretDigits - 1) + digits.slice(caretDigits);
        caretDigits -= 1;
      }
    }
    if (!deleting && atEnd) {
      const before = digits;
      digits = expandSmartDate(digits);
      if (digits.length !== before.length) caretDigits = digits.length;
    }
    digits = digits.slice(0, 8);
    if (caretDigits > digits.length) caretDigits = digits.length;
    const slash = !deleting && caretDigits === digits.length && (digits.length === 2 || digits.length === 4);
    const masked = maskDate(digits, slash);
    paintDate(el, masked, slash ? digits.length + 1 : caretDigits);
    return { digits: digits, masked: masked };
  }

  function onDateInput(id, keyName) {
    const el = $(id);
    const edited = applyDateEdit(el);
    const digits = edited.digits;
    const masked = edited.masked;
    el.classList.remove("date-bad");
    if (!digits) {
      markDateFields();
      state[keyName] = "";
      return;
    }
    if (digits.length === 8) {
      const key = parseDisplayDate(masked);
      markDateFields();
      state[keyName] = key || "";
      return;
    }
    state[keyName] = "";
  }

  function onDateBlur(id, keyName) {
    const el = $(id);
    const raw = el.value.trim();
    const key = raw ? parseDisplayDate(raw) : "";
    if (key) {
      const shown = toDisplayDate(key);
      el.value = shown;
      el.dataset.prev = shown;
    }
    markDateFields();
    state[keyName] = key || "";
  }

  function showDate(id, key) {
    const el = $(id);
    if (!el) return;
    const shown = key ? toDisplayDate(key) : "";
    el.value = shown;
    el.dataset.prev = shown;
    el.classList.remove("date-bad");
    syncPicker(id, key || "");
  }

  function applyPickedDate(id, iso) {
    const key = parseDisplayDate(iso);
    if (!key) return "";
    showDate(id, key);
    return key;
  }

  function bindDateCalendars() {
    document.querySelectorAll(".cal-btn[data-date-for]").forEach(function (btn) {
      const id = btn.getAttribute("data-date-for");
      const text = $(id);
      const picker = pickerFor(id);
      if (!text || !picker) return;
      btn.addEventListener("click", function () {
        const key = parseDisplayDate(text.value.trim());
        picker.value = key || "";
        if (typeof picker.showPicker === "function") {
          try { picker.showPicker(); return; } catch (err) {}
        }
        picker.focus();
      });
      picker.addEventListener("mousedown", function () {
        const key = parseDisplayDate(text.value.trim());
        picker.value = key || "";
      });
      picker.addEventListener("change", function () {
        const key = applyPickedDate(id, picker.value);
        if (!key) return;
        const keyName = text.getAttribute("data-date-key");
        if (keyName) state[keyName] = key;
        markDateFields();
      });
    });
  }

  function saveFilters() {
    const payload = JSON.stringify({
      symbol: state.symbol,
      file: state.file,
      from: state.from,
      to: state.to,
      fromTime: state.fromTime,
      toTime: state.toTime,
    });
    try { localStorage.setItem(FILTER_KEY, payload); } catch (e) {}
  }

  function restoreFilters() {
    let raw = null;
    try { raw = localStorage.getItem(FILTER_KEY); } catch (e) {}
    if (!raw) return;
    try {
      const saved = JSON.parse(raw);
      if (!saved || typeof saved !== "object") return;
      if (typeof saved.symbol === "string") state.symbol = saved.symbol.slice(0, 64);
      if (typeof saved.file === "string") state.file = saved.file.slice(0, 180);
      const from = parseDisplayDate(saved.from || "") || (typeof saved.from === "string" && /^\d{4}-\d{2}-\d{2}$/.test(saved.from) ? saved.from : "");
      const to = parseDisplayDate(saved.to || "") || (typeof saved.to === "string" && /^\d{4}-\d{2}-\d{2}$/.test(saved.to) ? saved.to : "");
      state.from = from || "";
      state.to = to || "";
      state.fromTime = normalizeTime(saved.fromTime, "00:00:00");
      state.toTime = normalizeTime(saved.toTime, "23:59:59");
    } catch (e) {}
  }

  function paintFilters() {
    showDate("filterFrom", state.from);
    showDate("filterTo", state.to);
    $("filterFromTime").value = state.fromTime;
    $("filterToTime").value = state.toTime;
    fillSelect("filterSymbol", [{ value: "", label: "Tất cả" }].concat(
      uniqueSymbols().map(function (s) { return { value: s, label: s }; })
    ), state.symbol);
    fillSelect("filterFile", [{ value: "", label: "Tất cả" }].concat(
      state.files.map(function (f) {
        const tag = f.source === "local" ? " (trình duyệt)" : " (đĩa)";
        return { value: fileKey(f), label: f.name + tag };
      })
    ), state.file);
  }

  function uniqueSymbols() {
    const set = {};
    const out = [];
    state.files.forEach(function (f) {
      if (f.symbol && !set[f.symbol]) {
        set[f.symbol] = 1;
        out.push(f.symbol);
      }
    });
    return out.sort();
  }

  function fillSelect(id, options, current) {
    const el = $(id);
    el.innerHTML = options.map(function (opt) {
      return '<option value="' + esc(opt.value) + '">' + esc(opt.label) + "</option>";
    }).join("");
    const ok = Array.from(el.options).some(function (opt) { return opt.value === current; });
    el.value = ok ? current : "";
    if (!ok) {
      if (id === "filterSymbol") state.symbol = "";
      if (id === "filterFile") state.file = "";
    }
  }

  async function api(method, path, body, opts) {
    const timeoutMs = (opts && opts.timeoutMs) || 20000;
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, timeoutMs);
    const options = { method: method, signal: controller.signal };
    if (body instanceof FormData) {
      options.body = body;
    } else if (body !== undefined) {
      options.headers = { "Content-Type": "application/json" };
      options.body = JSON.stringify(body);
    }
    try {
      const res = await fetch(PROXY + "?path=" + encodeURIComponent(path), options);
      const data = await res.json().catch(function () { return {}; });
      if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
      return data;
    } catch (err) {
      if (err && err.name === "AbortError") {
        throw new Error("API timeout — chạy start_server.bat trên máy WAMP.");
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  function renderFileList() {
    const el = $("fileList");
    if (!state.files.length) {
      el.innerHTML = '<p class="hint">Chưa có file đã nạp trên trình duyệt. File tháng trên đĩa: copy vào <code>' + esc(state.dir) + "</code>.</p>";
      return;
    }
    el.innerHTML = state.files.map(function (f) {
      const range = f.first_vn && f.last_vn
        ? f.first_vn + " → " + f.last_vn
        : (f.error || "Chưa đọc được khoảng thời gian");
      const where = f.source === "local" ? "localStorage" : state.dir;
      const nTick = f.ticks ? " · " + fmtCount(f.ticks.length) + " tick" : "";
      const sym = f.symbol ? f.symbol + " · " : "";
      return '<div class="file-row"><div><span class="file-name">' + esc(f.name)
        + '</span><span class="file-meta">' + esc(sym) + fmtSize(f.size) + nTick + " · " + esc(range)
        + " · " + esc(where)
        + '</span></div><button type="button" class="btn btn-ghost" data-del="' + esc(f.name)
        + '" data-source="' + esc(f.source || "disk") + '">Xóa</button></div>';
    }).join("");
  }

  function loadLocalFiles() {
    return readStore().map(function (rec) {
      const name = safeFileName(rec.name);
      const parsed = parseTickCsv(rec.text, name);
      return {
        source: "local",
        name: name,
        text: rec.text,
        size: rec.text.length,
        importedAt: rec.importedAt || 0,
        ticks: parsed.ticks || [],
        symbol: parsed.symbol || "",
        first_vn: parsed.first_vn || "",
        last_vn: parsed.last_vn || "",
        error: parsed.ok ? "" : (parsed.error || "Lỗi CSV"),
      };
    });
  }

  function saveLocalRecord(name, text) {
    if (text.length > MAX_LOCAL) {
      throw new Error("Nội dung quá lớn cho localStorage (tối đa 4 MB). File tháng để trong " + state.dir + "/.");
    }
    const parsed = parseTickCsv(text, name);
    if (!parsed.ok) throw new Error(parsed.error || "CSV không hợp lệ.");
    const records = readStore().filter(function (r) { return safeFileName(r.name) !== name; });
    records.push({ name: name, text: text, importedAt: Date.now() });
    writeStore(records);
    return parsed;
  }

  let loadGen = 0;

  async function loadFiles() {
    const gen = ++loadGen;
    let disk = [];
    let apiOk = false;
    let apiErr = "";
    try {
      const data = await api("GET", "/api/tick/files", undefined, { timeoutMs: 5000 });
      disk = (data.files || []).map(function (f) {
        return Object.assign({ source: "disk" }, f);
      });
      state.dir = data.dir || state.dir;
      apiOk = true;
    } catch (err) {
      apiErr = err.message || String(err);
    }
    if (gen !== loadGen) return;
    state.apiOk = apiOk;
    const local = loadLocalFiles();
    state.files = local.concat(disk);
    renderFileList();
    paintFilters();
    if (apiOk) {
      setStatus("API sẵn sàng · " + disk.length + " file đĩa · " + local.length + " file trình duyệt", "ok");
    } else {
      setStatus("Không có API — chỉ file localStorage (" + local.length + "). " + apiErr, "error");
    }
  }

  async function ingestFileList(fileList) {
    const incoming = Array.from(fileList || []);
    const errors = [];
    let ok = 0;
    for (let i = 0; i < incoming.length; i++) {
      const file = incoming[i];
      const name = safeFileName(file.name);
      if (!/\.csv$/i.test(name)) {
        errors.push((file.name || "file") + ": chỉ nhận .csv");
        continue;
      }
      if (file.size > MAX_LOCAL) {
        errors.push(name + ": quá 4 MB cho localStorage — để file tháng trong " + state.dir + "/");
        continue;
      }
      try {
        const text = await file.text();
        saveLocalRecord(name, text);
        ok += 1;
      } catch (err) {
        errors.push(name + ": " + (err.message || err));
      }
    }
    setMsg("importError", errors.join(" · "));
    setMsg("importOk", ok ? "Đã nạp " + ok + " file vào localStorage." : "");
    if (ok) await loadFiles();
  }

  async function ingestPastedCsv() {
    const text = $("csvPaste").value;
    if (!String(text).trim()) {
      setMsg("importError", "Chưa có nội dung.");
      setMsg("importOk", "");
      return;
    }
    const filename = safeFileName($("pasteName").value.trim() || "pasted.csv");
    try {
      saveLocalRecord(filename, text);
      $("csvPaste").value = "";
      setMsg("importError", "");
      setMsg("importOk", "Đã nạp " + filename + " vào localStorage.");
      await loadFiles();
    } catch (err) {
      setMsg("importOk", "");
      setMsg("importError", err.message || String(err));
    }
  }

  function readFilterInputs() {
    state.symbol = $("filterSymbol").value;
    state.file = $("filterFile").value;
    state.fromTime = normalizeTime($("filterFromTime").value, "00:00:00");
    state.toTime = normalizeTime($("filterToTime").value, "23:59:59");
    const fromRaw = $("filterFrom").value.trim();
    const toRaw = $("filterTo").value.trim();
    state.from = fromRaw ? parseDisplayDate(fromRaw) || "" : "";
    state.to = toRaw ? parseDisplayDate(toRaw) || "" : "";
    markDateFields();
  }

  function buildSearchSpec() {
    readFilterInputs();
    if (state.dateError) throw new Error(state.dateError);
    if ($("filterFromTime").classList.contains("date-bad") || $("filterToTime").classList.contains("date-bad")) {
      throw new Error("Giờ phải dạng HH:MM:SS.");
    }
    if (!state.from || !state.to) throw new Error("Nhập ngày từ và đến (dd/mm/yyyy).");
    if (state.from > state.to) throw new Error("Ngày bắt đầu đang sau ngày kết thúc.");
    const from = state.from + "T" + state.fromTime;
    const to = state.to + "T" + state.toTime;
    if (from > to) throw new Error("Thời gian bắt đầu đang sau thời gian kết thúc.");
    const fromMs = Date.parse(from + "+07:00");
    const toMs = Date.parse(to + "+07:00");
    if (!Number.isFinite(fromMs) || !Number.isFinite(toMs)) throw new Error("Thời gian không hợp lệ.");
    return {
      from: from,
      to: to,
      fromMs: fromMs,
      toMs: toMs + 999,
      fromVn: fmtVnMs(fromMs),
      toVn: fmtVnMs(toMs),
      symbol: state.symbol,
      file: state.file,
      offset: state.page * PAGE_SIZE,
    };
  }

  async function runSearch() {
    if (state.busy) return;
    let spec;
    try {
      spec = buildSearchSpec();
    } catch (err) {
      $("filterMeta").textContent = err.message || String(err);
      return;
    }
    saveFilters();
    state.busy = true;
    $("btnSearch").disabled = true;
    $("filterMeta").textContent = "Đang tìm…";
    const key = spec.file || "";
    const localOnly = key.indexOf("local:") === 0;
    const diskOnly = key.indexOf("disk:") === 0;
    try {
      const localRes = diskOnly ? emptyResult(spec) : queryLocal(spec, localOnly ? key.slice(6) : "");
      let apiRes = emptyResult(spec);
      if (!localOnly && (state.apiOk || diskOnly)) {
        const qs = new URLSearchParams();
        qs.set("from", spec.from);
        qs.set("to", spec.to);
        if (spec.symbol) qs.set("symbol", spec.symbol);
        if (diskOnly) qs.set("file", key.slice(5));
        qs.set("limit", String(PAGE_SIZE));
        qs.set("offset", String(spec.offset));
        try {
          apiRes = await api("GET", "/api/tick/query?" + qs.toString(), undefined, { timeoutMs: 180000 });
        } catch (err) {
          if (!localRes.total) throw err;
        }
      }
      state.result = mergeResults(localRes, apiRes, spec);
      renderResults();
    } catch (err) {
      state.result = null;
      $("dashboard").classList.add("hidden");
      $("filterMeta").textContent = err.message || String(err);
      setStatus(err.message || String(err), "error");
    } finally {
      state.busy = false;
      $("btnSearch").disabled = false;
    }
  }

  function renderResults() {
    const data = state.result;
    if (!data) {
      $("dashboard").classList.add("hidden");
      return;
    }
    $("dashboard").classList.remove("hidden");
    const s = data.stats || {};
    $("filterMeta").textContent = (data.from_vn || "") + " → " + (data.to_vn || "")
      + " · " + fmtCount(s.count) + " tick"
      + (data.files && data.files.length ? " · " + data.files.join(", ") : "");
    $("stats").innerHTML = '<div class="kpi-grid">'
      + kpi("Số tick", fmtCount(s.count))
      + kpi("Từ (VN)", s.first_vn || "—")
      + kpi("Đến (VN)", s.last_vn || "—")
      + kpi("Symbol", s.symbol || "—")
      + kpi("Giá bán min", fmtPx(s.bid_min))
      + kpi("Giá bán max", fmtPx(s.bid_max))
      + kpi("Giá mua min", fmtPx(s.ask_min))
      + kpi("Giá mua max", fmtPx(s.ask_max))
      + kpi("Spread TB", fmtSpread(s.spread_avg))
      + kpi("Spread min", fmtSpread(s.spread_min))
      + kpi("Spread max", fmtSpread(s.spread_max))
      + kpi("Giá bán đóng", fmtPx(s.bid_close))
      + "</div>";
    drawChart(data.chart || []);
    renderTable(data);
    const totalPages = Math.max(1, Math.ceil((data.total || 0) / PAGE_SIZE));
    const page = Math.floor((data.offset || 0) / PAGE_SIZE) + 1;
    $("pageInfo").textContent = "Trang " + page + " / " + totalPages;
    $("pagePrev").disabled = page <= 1;
    $("pageNext").disabled = page >= totalPages;
    $("tableMeta").textContent = data.total
      ? "Hiển thị " + data.rows.length + " / " + fmtCount(data.total)
      : "Không có tick trong khoảng này.";
  }

  function kpi(label, value) {
    return '<div class="kpi"><div class="label">' + esc(label) + '</div><div class="value">' + esc(value) + "</div></div>";
  }

  function renderTable(data) {
    const rows = data.rows || [];
    if (!rows.length) {
      $("tickTableWrap").innerHTML = '<p class="hint">Không có dòng.</p>';
      return;
    }
    const body = rows.map(function (r) {
      return "<tr><td class=\"left\">" + esc(r.ts_vn) + "</td><td class=\"left\">" + esc(r.symbol)
        + '</td><td class="bid">' + fmtPx(r.bid) + '</td><td class="ask">' + fmtPx(r.ask)
        + "</td><td>" + fmtSpread(r.spread) + '</td><td class="left">' + esc(r.file) + "</td></tr>";
    }).join("");
    $("tickTableWrap").innerHTML = "<table><thead><tr>"
      + '<th class="left">Thời gian VN</th><th class="left">Symbol</th>'
      + "<th>Giá bán (Bid)</th><th>Giá mua (Ask)</th><th>Spread</th><th class=\"left\">File</th>"
      + "</tr></thead><tbody>" + body + "</tbody></table>";
  }

  let chartPoints = [];

  function drawChart(points) {
    chartPoints = points || [];
    const canvas = $("tickChart");
    const wrap = canvas.parentNode;
    const dpr = window.devicePixelRatio || 1;
    const w = wrap.clientWidth || 800;
    const h = wrap.clientHeight || 300;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!chartPoints.length) {
      ctx.fillStyle = getCss("--muted");
      ctx.font = "13px Segoe UI, Arial, sans-serif";
      ctx.fillText("Không có điểm để vẽ.", 16, 28);
      return;
    }
    const padL = 58, padR = 16, padT = 16, padB = 28;
    let min = Infinity, max = -Infinity, t0 = chartPoints[0].t, t1 = chartPoints[0].t;
    chartPoints.forEach(function (p) {
      min = Math.min(min, p.bid_min != null ? p.bid_min : p.bid, p.ask_min != null ? p.ask_min : p.ask);
      max = Math.max(max, p.bid_max != null ? p.bid_max : p.bid, p.ask_max != null ? p.ask_max : p.ask);
      if (p.t < t0) t0 = p.t;
      if (p.t > t1) t1 = p.t;
    });
    if (!(max > min)) { max = min + 1; }
    const span = Math.max(1, t1 - t0);
    function xOf(t) { return padL + ((t - t0) / span) * (w - padL - padR); }
    function yOf(v) { return padT + (1 - (v - min) / (max - min)) * (h - padT - padB); }

    ctx.strokeStyle = getCss("--border");
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, padT);
    ctx.lineTo(padL, h - padB);
    ctx.lineTo(w - padR, h - padB);
    ctx.stroke();

    ctx.fillStyle = getCss("--muted");
    ctx.font = "11px Segoe UI, Arial, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(fmtPx(max), padL - 6, padT + 10);
    ctx.fillText(fmtPx(min), padL - 6, h - padB);
    ctx.textAlign = "left";
    ctx.fillText(fmtTipTime(t0), padL, h - 8);
    ctx.textAlign = "right";
    ctx.fillText(fmtTipTime(t1), w - padR, h - 8);

    function strokeLine(key, color) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      chartPoints.forEach(function (p, i) {
        const x = xOf(p.t), y = yOf(p[key]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
    strokeLine("bid", getCss("--bid"));
    strokeLine("ask", getCss("--ask"));
  }

  function getCss(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
  }

  function fmtTipTime(ms) {
    const d = new Date(ms);
    const vn = new Date(d.getTime() + 7 * 3600 * 1000);
    return pad(vn.getUTCDate()) + "/" + pad(vn.getUTCMonth() + 1) + "/" + vn.getUTCFullYear()
      + " " + pad(vn.getUTCHours()) + ":" + pad(vn.getUTCMinutes()) + ":" + pad(vn.getUTCSeconds());
  }

  function onChartMove(ev) {
    const tip = $("chartTip");
    if (!chartPoints.length) {
      tip.classList.add("hidden");
      return;
    }
    const canvas = $("tickChart");
    const rect = canvas.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const w = rect.width;
    const padL = 58, padR = 16;
    const t0 = chartPoints[0].t;
    const t1 = chartPoints[chartPoints.length - 1].t;
    const span = Math.max(1, t1 - t0);
    const t = t0 + ((x - padL) / Math.max(1, w - padL - padR)) * span;
    let best = chartPoints[0], bestD = Infinity;
    for (let i = 0; i < chartPoints.length; i++) {
      const d = Math.abs(chartPoints[i].t - t);
      if (d < bestD) { bestD = d; best = chartPoints[i]; }
    }
    tip.innerHTML = esc(fmtTipTime(best.t)) + "<br>Bán " + fmtPx(best.bid) + " · Mua " + fmtPx(best.ask)
      + " · Spread " + fmtSpread(best.ask - best.bid);
    tip.classList.remove("hidden");
    const left = Math.min(rect.width - 180, Math.max(8, x + 12));
    tip.style.left = left + "px";
    tip.style.top = "12px";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    $("themeToggle").textContent = theme === "dark" ? "Chế độ sáng" : "Chế độ tối";
    if (state.result) drawChart(state.result.chart || []);
  }

  function initTheme() {
    let theme = "light";
    try {
      const saved = localStorage.getItem("mt5-theme");
      if (saved === "dark" || saved === "light") theme = saved;
    } catch (e) {}
    applyTheme(theme);
  }

  function bind() {
    $("themeToggle").addEventListener("click", function () {
      const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      const next = cur === "dark" ? "light" : "dark";
      try { localStorage.setItem("mt5-theme", next); } catch (e) {}
      applyTheme(next);
    });

    const drop = $("dropzone");
    const pick = $("fileInput");
    $("btnPick").addEventListener("click", function () { pick.click(); });
    pick.addEventListener("change", function () {
      ingestFileList(pick.files);
      pick.value = "";
    });
    drop.addEventListener("dragover", function (ev) {
      ev.preventDefault();
      drop.classList.add("drag");
    });
    drop.addEventListener("dragleave", function () { drop.classList.remove("drag"); });
    drop.addEventListener("drop", function (ev) {
      ev.preventDefault();
      drop.classList.remove("drag");
      ingestFileList(ev.dataTransfer.files);
    });
    $("btnPaste").addEventListener("click", ingestPastedCsv);
    $("btnReloadFiles").addEventListener("click", function () {
      loadFiles().catch(function (err) { setStatus(err.message || String(err), "error"); });
    });
    $("fileList").addEventListener("click", function (ev) {
      const btn = ev.target.closest("[data-del]");
      if (!btn) return;
      const name = btn.getAttribute("data-del");
      const source = btn.getAttribute("data-source") || "disk";
      if (!name) return;
      if (source === "local") {
        if (!window.confirm("Xóa " + name + " khỏi localStorage?")) return;
        try {
          writeStore(readStore().filter(function (r) { return safeFileName(r.name) !== name; }));
          setMsg("importOk", "Đã xóa " + name + " khỏi localStorage.");
          setMsg("importError", "");
          loadFiles();
        } catch (err) {
          setMsg("importError", err.message || String(err));
        }
        return;
      }
      if (!window.confirm("Xóa file " + name + " khỏi " + state.dir + "?")) return;
      api("DELETE", "/api/tick/files/" + encodeURIComponent(name)).then(function () {
        setMsg("importOk", "Đã xóa " + name + ".");
        setMsg("importError", "");
        return loadFiles();
      }).catch(function (err) {
        setMsg("importError", err.message || String(err));
      });
    });

    $("filterFrom").addEventListener("input", function () { onDateInput("filterFrom", "from"); });
    $("filterTo").addEventListener("input", function () { onDateInput("filterTo", "to"); });
    $("filterFrom").addEventListener("blur", function () { onDateBlur("filterFrom", "from"); });
    $("filterTo").addEventListener("blur", function () { onDateBlur("filterTo", "to"); });
    bindDateCalendars();

    $("btnSearch").addEventListener("click", runSearch);
    $("btnResetFilters").addEventListener("click", function () {
      state.symbol = "";
      state.file = "";
      state.from = "";
      state.to = "";
      state.fromTime = "00:00:00";
      state.toTime = "23:59:59";
      state.page = 0;
      state.result = null;
      paintFilters();
      saveFilters();
      $("dashboard").classList.add("hidden");
      $("filterMeta").textContent = "Chọn khoảng thời gian tới giây rồi bấm Tìm. Bid = giá bán, Ask = giá mua.";
    });
    $("pagePrev").addEventListener("click", function () {
      if (state.page > 0) { state.page -= 1; runSearch(); }
    });
    $("pageNext").addEventListener("click", function () {
      state.page += 1;
      runSearch();
    });
    $("tickChart").addEventListener("mousemove", onChartMove);
    $("tickChart").addEventListener("mouseleave", function () {
      $("chartTip").classList.add("hidden");
    });
    window.addEventListener("resize", function () {
      if (state.result) drawChart(state.result.chart || []);
    });
    $("filterFromTime").addEventListener("input", function () { onTimeInput("filterFromTime", "fromTime", "00:00:00"); });
    $("filterToTime").addEventListener("input", function () { onTimeInput("filterToTime", "toTime", "23:59:59"); });
    $("filterFromTime").addEventListener("blur", function () {
      onTimeBlur("filterFromTime", "fromTime", "00:00:00");
      saveFilters();
    });
    $("filterToTime").addEventListener("blur", function () {
      onTimeBlur("filterToTime", "toTime", "23:59:59");
      saveFilters();
    });
    ["filterSymbol", "filterFile"].forEach(function (id) {
      $(id).addEventListener("change", function () {
        readFilterInputs();
        saveFilters();
      });
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" && ev.target && (ev.target.id || "").indexOf("filter") === 0) {
        ev.preventDefault();
        state.page = 0;
        runSearch();
      }
    });
  }

  restoreFilters();
  initTheme();
  bind();
  paintFilters();
  loadFiles().catch(function (err) {
    setStatus(err.message || String(err), "error");
  });
})();
