(function () {
  "use strict";

  const FILTER_KEY = "tick-filters";
  const PAGE_SIZE = 100;
  const PROXY = "proxy.php";
  const SAVE_URL = "save.php";
  const CHUNK = 1024 * 1024;

  const state = {
    files: [],
    apiOk: false,
    dir: "www/tick",
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

  function fmtVnMs(ms) {
    if (ms == null || !Number.isFinite(ms)) return '';
    const d = new Date(ms + 7 * 3600 * 1000);
    const base = pad(d.getUTCDate()) + '/' + pad(d.getUTCMonth() + 1) + '/' + d.getUTCFullYear()
      + ' ' + pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes()) + ':' + pad(d.getUTCSeconds());
    const frac = Math.floor(ms % 1000);
    if (!frac) return base;
    return base + '.' + String(frac);
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
      state.files.map(function (f) { return { value: f.name, label: f.name }; })
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
      el.innerHTML = '<p class="hint">Chưa có CSV. Chọn file để nạp, hoặc copy vào <code>' + esc(state.dir) + "</code>.</p>";
      return;
    }
    el.innerHTML = state.files.map(function (f) {
      const range = f.first_vn && f.last_vn
        ? f.first_vn + " → " + f.last_vn
        : (f.error || "Chưa đọc được khoảng thời gian");
      const sym = f.symbol ? f.symbol + " · " : "";
      return '<div class="file-row"><div><span class="file-name">' + esc(f.name)
        + '</span><span class="file-meta">' + esc(sym) + fmtSize(f.size) + " · " + esc(range)
        + '</span></div><button type="button" class="btn btn-ghost" data-del="' + esc(f.name)
        + '">Xóa</button></div>';
    }).join("");
  }

  async function saveToWww(body, asJson) {
    const options = { method: "POST", body: body };
    if (asJson) options.headers = { "Content-Type": "application/json" };
    const res = await fetch(SAVE_URL, options);
    const data = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
    return data;
  }

  let loadGen = 0;

  async function loadFiles() {
    const gen = ++loadGen;
    try {
      const data = await api("GET", "/api/tick/files", undefined, { timeoutMs: 8000 });
      if (gen !== loadGen) return;
      state.apiOk = true;
      state.files = data.files || [];
      state.dir = data.dir || state.dir;
      renderFileList();
      paintFilters();
      setStatus("API sẵn sàng · " + state.files.length + " file trong " + state.dir, "ok");
    } catch (err) {
      if (gen !== loadGen) return;
      state.apiOk = false;
      state.files = [];
      renderFileList();
      paintFilters();
      setStatus(err.message || String(err), "error");
    }
  }

  async function tryAdopt(name, size) {
    if (!state.apiOk) return false;
    try {
      await api("POST", "/api/tick/adopt", { filename: name, size: size }, { timeoutMs: 15000 });
      return true;
    } catch (e) {
      return false;
    }
  }

  async function uploadChunked(file, name) {
    const total = Math.max(1, Math.ceil(file.size / CHUNK) || 1);
    for (let i = 0; i < total; i++) {
      const blob = file.slice(i * CHUNK, Math.min(file.size, (i + 1) * CHUNK));
      const fd = new FormData();
      fd.append("file", blob, name);
      fd.append("filename", name);
      fd.append("index", String(i));
      fd.append("total", String(total));
      fd.append("size", String(file.size));
      await saveToWww(fd);
      const pct = Math.round(((i + 1) / total) * 100);
      setMsg("importOk", "Đang gửi " + name + " · " + pct + "% (" + (i + 1) + "/" + total + ")");
      setMsg("importError", "");
    }
  }

  async function ingestFileList(fileList) {
    const incoming = Array.from(fileList || []);
    const errors = [];
    const notes = [];
    let ok = 0;
    if (!state.apiOk) {
      try { await loadFiles(); } catch (e) {}
    }
    for (let i = 0; i < incoming.length; i++) {
      const file = incoming[i];
      const name = safeFileName(file.name);
      if (!/\.csv$/i.test(name)) {
        errors.push((file.name || "file") + ": chỉ nhận .csv");
        continue;
      }
      try {
        if (await tryAdopt(name, file.size)) {
          notes.push(name + ": đã có trên đĩa, không cần gửi lại.");
          ok += 1;
          continue;
        }
        await uploadChunked(file, name);
        ok += 1;
      } catch (err) {
        errors.push(name + ": " + (err.message || err));
      }
    }
    setMsg("importError", errors.join(" · "));
    setMsg("importOk", (ok ? "Đã nạp " + ok + " file vào " + state.dir + "." : "") + (notes.length ? " " + notes.join(" ") : ""));
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
      await saveToWww(JSON.stringify({ csv: text, filename: filename }), true);
      $("csvPaste").value = "";
      setMsg("importError", "");
      setMsg("importOk", "Đã lưu " + filename + " vào " + state.dir + ".");
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
    try {
      const qs = new URLSearchParams();
      qs.set("from", spec.from);
      qs.set("to", spec.to);
      if (spec.symbol) qs.set("symbol", spec.symbol);
      if (spec.file) qs.set("file", spec.file.replace(/^disk:/, "").replace(/^local:/, ""));
      qs.set("limit", String(PAGE_SIZE));
      qs.set("offset", String(spec.offset));
      state.result = await api("GET", "/api/tick/query?" + qs.toString(), undefined, { timeoutMs: 180000 });
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
      if (!name) return;
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
