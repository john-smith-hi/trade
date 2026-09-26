(function () {
  "use strict";

  const FILTER_KEY = "history-journal-filters";
  const PAGE_SIZE = 50;
  const REASON_ORDER = ["tp", "sl", "user", "so", "unknown"];
  const REASON_LABEL = {
    tp: "Take profit",
    sl: "Stop loss",
    user: "Đóng tay",
    so: "Stop out",
    unknown: "Không rõ",
  };
  const TEXT_SORT = { symbol: 1, side: 1, reason: 1 };

  const state = {
    files: [],
    symbols: null,
    symbolFilterReady: false,
    knownSymbols: new Set(),
    allSymbols: [],
    allReasons: [],
    side: "",
    reason: "",
    file: "",
    from: "",
    to: "",
    dateError: "",
    search: "",
    sortKey: "close",
    sortDir: -1,
    page: 0,
    report: null,
    shown: [],
  };

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function safeFileName(name) {
    const base = String(name || "").split(/[/\\]/).pop();
    const clean = base.replace(/[\u0000-\u001F\u007F<>:"|?*]/g, "_").trim().slice(0, 180);
    return clean || "import.csv";
  }

  function pad(n) { return String(n).padStart(2, "0"); }

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
    let d;
    let mo;
    let y;
    if (dmy) {
      d = Number(dmy[1]);
      mo = Number(dmy[2]);
      y = Number(dmy[3]);
    } else if (iso) {
      y = Number(iso[1]);
      mo = Number(iso[2]);
      d = Number(iso[3]);
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

  function markDateFields() {
    ["filterFrom", "filterTo"].forEach(function (id) {
      const raw = $(id).value.trim();
      $(id).classList.toggle("date-bad", !!raw && !parseDisplayDate(raw));
    });
    const bad = $("filterFrom").classList.contains("date-bad") || $("filterTo").classList.contains("date-bad");
    state.dateError = bad ? "Ngày phải theo dạng dd/mm/yyyy." : "";
  }

  function setDateFilter(keyName, key) {
    if (state[keyName] === key) return;
    state[keyName] = key;
    state.page = 0;
    renderResults();
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
      setDateFilter(keyName, "");
      return;
    }
    if (digits.length === 8) {
      const key = parseDisplayDate(masked);
      if (key) {
        const before = state.dateError;
        markDateFields();
        if (state[keyName] !== key) setDateFilter(keyName, key);
        else if (state.dateError !== before) renderResults();
        return;
      }
      markDateFields();
      if (state[keyName]) setDateFilter(keyName, "");
      else renderResults();
      return;
    }
    if (state[keyName]) setDateFilter(keyName, "");
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
    const before = state.dateError;
    markDateFields();
    if (key) {
      if (state[keyName] !== key) setDateFilter(keyName, key);
      else if (state.dateError !== before) renderResults();
      return;
    }
    if (state[keyName]) setDateFilter(keyName, "");
    else if (state.dateError !== before) renderResults();
  }

  function showDate(id, key) {
    const el = $(id);
    if (!el) return;
    const shown = key ? toDisplayDate(key) : "";
    el.value = shown;
    el.dataset.prev = shown;
    el.classList.remove("date-bad");
  }

  const ORDERS_ACCOUNT = "201967146";
  const ORDERS_FROM_DEFAULT = "2007-01-01";

  function todayKey() {
    const p = HistoryAnalyze.ictParts(Date.now());
    return p.year + "-" + pad(p.month) + "-" + pad(p.day);
  }

  function linkDateKey(id) {
    const el = $(id);
    const raw = el.value.trim();
    if (!raw) return "";
    const key = parseDisplayDate(raw);
    el.classList.toggle("date-bad", !key);
    return key;
  }

  function ordersHistoryUrl() {
    const fromRaw = $("linkFrom").value.trim();
    const toRaw = $("linkTo").value.trim();
    const fromKey = fromRaw ? linkDateKey("linkFrom") : ORDERS_FROM_DEFAULT;
    const toKey = toRaw ? linkDateKey("linkTo") : todayKey();
    if ((fromRaw && !fromKey) || (toRaw && !toKey)) {
      setMsg("importError", "Ngày link phải theo dạng dd/mm/yyyy.");
      return "";
    }
    if (fromKey > toKey) {
      setMsg("importError", "Ngày bắt đầu link đang sau ngày kết thúc.");
      return "";
    }
    setMsg("importError", "");
    const url = new URL("https://my.ex-markets.pro/v4/orders-history/orders/" + ORDERS_ACCOUNT);
    url.searchParams.set("limit", "100000");
    url.searchParams.set("offset", "0");
    url.searchParams.set("accountNumber", ORDERS_ACCOUNT);
    url.searchParams.set("sort", "close_time_desc");
    url.searchParams.set("closed", "1");
    url.searchParams.set("close_time_from", fromKey + "T00:00:00.000Z");
    url.searchParams.set("close_time_to", toKey + "T23:59:59.999Z");
    url.searchParams.set("platform", "mt5");
    return url.toString();
  }

  function onPlainDateInput(id) {
    const el = $(id);
    const edited = applyDateEdit(el);
    if (!edited.digits || edited.digits.length < 8) {
      el.classList.remove("date-bad");
      return;
    }
    el.classList.toggle("date-bad", !parseDisplayDate(edited.masked));
  }

  function onPlainDateBlur(id) {
    const el = $(id);
    const raw = el.value.trim();
    const key = raw ? parseDisplayDate(raw) : "";
    if (key) {
      const shown = toDisplayDate(key);
      el.value = shown;
      el.dataset.prev = shown;
      el.classList.remove("date-bad");
      return;
    }
    el.classList.toggle("date-bad", !!raw);
  }

  function setMsg(id, text) {
    const el = $(id);
    if (!el) return;
    el.textContent = text || "";
    el.classList.toggle("hidden", !text);
  }

  function reasonLabel(key) {
    return REASON_LABEL[key] || key || "Không rõ";
  }

  function moneyClass(n) {
    if (n > 0) return "pos";
    if (n < 0) return "neg";
    return "";
  }

  function fmtMoney(n) {
    if (n == null || !Number.isFinite(n)) return "—";
    const abs = Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (n > 0) return "+" + abs;
    if (n < 0) return "−" + abs;
    return abs;
  }

  function fmtPct(n) {
    if (n == null || !Number.isFinite(n)) return "—";
    return (n * 100).toFixed(1) + "%";
  }

  function fmtPf(n) {
    if (n == null) return "—";
    if (!Number.isFinite(n)) return "∞";
    return n.toFixed(2);
  }

  function fmtR(n) {
    if (n == null || !Number.isFinite(n)) return "—";
    const body = Math.abs(n).toFixed(2) + "R";
    if (n > 0) return "+" + body;
    if (n < 0) return "−" + body;
    return body;
  }

  function fmtLots(n) {
    if (n == null || !Number.isFinite(n)) return "—";
    return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fmtPx(n) {
    if (n == null || !Number.isFinite(n)) return "—";
    const a = Math.abs(n);
    const d = a >= 1000 ? 2 : a >= 100 ? 3 : 5;
    return n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  function fmtDuration(ms) {
    if (ms == null || !Number.isFinite(ms) || ms < 0) return "—";
    const s = Math.round(ms / 1000);
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (d > 0) return d + " ngày " + h + " giờ";
    if (h > 0) return h + " giờ " + m + " phút";
    if (m > 0) return m + " phút";
    return s + " giây";
  }

  function fmtDayTime(ms) {
    if (ms == null) return "—";
    const p = HistoryAnalyze.ictParts(ms);
    return pad(p.day) + "/" + pad(p.month) + "/" + p.year + " " + pad(p.hour) + ":" + pad(p.minute);
  }

  function fmtImportAt(ms) {
    if (!ms) return "";
    const p = HistoryAnalyze.ictParts(ms);
    return pad(p.day) + "/" + pad(p.month) + "/" + p.year + " "
      + pad(p.hour) + ":" + pad(p.minute) + ":" + pad(p.second);
  }

  function sortReasons(list) {
    return list.slice().sort(function (a, b) {
      const ia = REASON_ORDER.indexOf(a);
      const ib = REASON_ORDER.indexOf(b);
      return (ia < 0 ? 50 : ia) - (ib < 0 ? 50 : ib) || String(a).localeCompare(String(b));
    });
  }

  function openDb() {
    return new Promise(function (resolve, reject) {
      const req = indexedDB.open("trade-history", 1);
      req.onupgradeneeded = function () {
        const db = req.result;
        if (!db.objectStoreNames.contains("files")) db.createObjectStore("files", { keyPath: "name" });
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function idbAll() {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        const tx = db.transaction("files", "readonly");
        const req = tx.objectStore("files").getAll();
        req.onsuccess = function () { resolve(req.result || []); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function idbPut(rec) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        const tx = db.transaction("files", "readwrite");
        tx.objectStore("files").put(rec);
        tx.oncomplete = function () { resolve(); };
        tx.onerror = function () { reject(tx.error); };
      });
    });
  }

  function idbDelete(name) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        const tx = db.transaction("files", "readwrite");
        tx.objectStore("files").delete(name);
        tx.oncomplete = function () { resolve(); };
        tx.onerror = function () { reject(tx.error); };
      });
    });
  }

  function idbClear() {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        const tx = db.transaction("files", "readwrite");
        tx.objectStore("files").clear();
        tx.oncomplete = function () { resolve(); };
        tx.onerror = function () { reject(tx.error); };
      });
    });
  }

  function saveFilters() {
    try {
      sessionStorage.setItem(FILTER_KEY, JSON.stringify({
        symbols: state.symbols ? Array.from(state.symbols) : null,
        side: state.side,
        reason: state.reason,
        file: state.file,
        from: state.from,
        to: state.to,
        search: state.search,
      }));
    } catch (e) {}
  }

  function restoreFilters() {
    let saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(FILTER_KEY) || "null"); } catch (e) { saved = null; }
    if (!saved || typeof saved !== "object" || Array.isArray(saved)) return;
    if (Array.isArray(saved.symbols)) {
      const next = [];
      for (let i = 0; i < saved.symbols.length && next.length < 100; i++) {
        if (typeof saved.symbols[i] !== "string") continue;
        const symbol = saved.symbols[i].replace(/[\u0000-\u001F\u007F]/g, "").trim().slice(0, 64);
        if (symbol) next.push(symbol);
      }
      state.symbols = new Set(next);
      state.symbolFilterReady = true;
    }
    state.side = saved.side === "buy" || saved.side === "sell" ? saved.side : "";
    state.reason = typeof saved.reason === "string" && /^[a-z0-9][a-z0-9 ._-]{0,31}$/i.test(saved.reason)
      ? saved.reason.toLowerCase()
      : "";
    state.file = typeof saved.file === "string" ? safeFileName(saved.file) : "";
    if (state.file === "import.csv" && saved.file !== "import.csv") state.file = "";
    state.from = isoOrEmpty(saved.from);
    state.to = isoOrEmpty(saved.to);
    state.search = typeof saved.search === "string" ? saved.search.replace(/[\u0000-\u001F\u007F]/g, "").slice(0, 80) : "";
  }

  function isoOrEmpty(v) {
    if (typeof v !== "string" || !v) return "";
    const shown = toDisplayDate(v);
    if (!shown) return "";
    return parseDisplayDate(shown) === v ? v : "";
  }

  async function loadFiles() {
    const rows = await idbAll();
    state.files = rows.map(function (rec) {
      const parsed = HistoryAnalyze.parseInput(rec.text || "");
      return {
        name: rec.name,
        text: rec.text || "",
        importedAt: rec.importedAt || 0,
        trades: parsed.ok ? parsed.trades.map(function (t) { return Object.assign({}, t, { source: rec.name }); }) : [],
        skipped: parsed.skipped || [],
        skippedTotal: parsed.skippedTotal || (parsed.skipped ? parsed.skipped.length : 0),
        error: parsed.ok ? "" : parsed.error,
      };
    }).sort(function (a, b) {
      return a.importedAt - b.importedAt || a.name.localeCompare(b.name);
    });
  }

  async function ingestFileList(fileList) {
    const incoming = Array.from(fileList || []);
    const errors = [];
    for (let i = 0; i < incoming.length; i++) {
      const file = incoming[i];
      const name = safeFileName(file.name);
      if (!/\.csv$/i.test(name)) {
        errors.push(name + ": chỉ nhận file .csv");
        continue;
      }
      if (file.size > 8 * 1024 * 1024) {
        errors.push(name + ": nội dung quá lớn (tối đa 8 MB)");
        continue;
      }
      let text = "";
      try {
        text = await file.text();
      } catch (err) {
        errors.push(name + ": không đọc được file");
        continue;
      }
      const parsed = HistoryAnalyze.parseCsv(text);
      if (!parsed.ok || !parsed.trades.length) {
        errors.push(name + ": " + (parsed.error || "Không có lệnh hợp lệ."));
        continue;
      }
      const rec = {
        name: name,
        text: text,
        importedAt: Date.now() + i,
        trades: parsed.trades.map(function (t) { return Object.assign({}, t, { source: name }); }),
        skipped: parsed.skipped,
        skippedTotal: parsed.skippedTotal || 0,
        error: "",
      };
      const existing = state.files.findIndex(function (f) { return f.name === rec.name; });
      if (existing >= 0) state.files[existing] = rec;
      else state.files.push(rec);
      try {
        await idbPut({ name: rec.name, text: rec.text, importedAt: rec.importedAt });
      } catch (err) {
        setMsg("persistError", "Không ghi được bộ nhớ trình duyệt — file chỉ còn đến khi tải lại trang.");
      }
    }
    setMsg("importError", errors.join(" · "));
    refreshAfterFiles();
  }

  async function ingestPastedCsv() {
    const text = $("csvPaste").value;
    if (!String(text).trim()) {
      setMsg("importError", "Chưa có nội dung.");
      return;
    }
    if (String(text).length > 8 * 1024 * 1024) {
      setMsg("importError", "Nội dung quá lớn (tối đa 8 MB).");
      return;
    }
    const parsed = HistoryAnalyze.parseInput(text);
    if (!parsed.ok || !parsed.trades.length) {
      setMsg("importError", parsed.error || "Không có lệnh hợp lệ.");
      return;
    }
    const trimmed = String(text).trim();
    const name = trimmed.charAt(0) === "{" || trimmed.charAt(0) === "[" ? "Đã dán.json" : "Đã dán.csv";
    const rec = {
      name: name,
      text: text,
      importedAt: Date.now(),
      trades: parsed.trades.map(function (t) { return Object.assign({}, t, { source: name }); }),
      skipped: parsed.skipped,
      skippedTotal: parsed.skippedTotal || 0,
      error: "",
    };
    const existing = state.files.findIndex(function (f) { return f.name === name; });
    if (existing >= 0) state.files[existing] = rec;
    else state.files.push(rec);
    try {
      await idbPut({ name: rec.name, text: rec.text, importedAt: rec.importedAt });
    } catch (err) {
      setMsg("persistError", "Không ghi được bộ nhớ trình duyệt — dữ liệu chỉ còn đến khi tải lại trang.");
    }
    setMsg("importError", "");
    $("csvPaste").value = "";
    refreshAfterFiles();
  }

  function renderFileList() {
    const el = $("fileList");
    const clearBtn = $("btnClear");
    clearBtn.classList.toggle("hidden", state.files.length === 0);
    if (!state.files.length) {
      el.innerHTML = "";
      return;
    }
    el.innerHTML = state.files.map(function (f, i) {
      const net = f.trades.reduce(function (sum, t) { return sum + t.net; }, 0);
      const nSkip = f.skippedTotal || (f.skipped ? f.skipped.length : 0);
      const skip = nSkip ? " · bỏ " + nSkip + " dòng" : "";
      const err = f.error ? " · " + f.error : "";
      const imported = fmtImportAt(f.importedAt);
      const when = imported ? " · Import " + imported : "";
      let skipHtml = "";
      if (f.skipped && f.skipped.length) {
        const items = f.skipped.slice(0, 8).map(function (row) {
          return "<li>Dòng " + Number(row.line) + ": " + esc(row.reason) + "</li>";
        }).join("");
        const more = nSkip > 8 ? "<li>…</li>" : "";
        skipHtml = `<details><summary>Dòng bỏ qua</summary><ul>${items}${more}</ul></details>`;
      }
      return `<div class="file-row"><div><span class="file-name">${esc(f.name)}</span><span class="file-meta">${f.trades.length} lệnh${esc(skip)}${esc(err)} · ${fmtMoney(net)}${esc(when)}</span>${skipHtml}</div><button type="button" class="btn btn-ghost" data-name="${esc(f.name)}">Bỏ</button></div>`;
    }).join("");
  }

  function renderSymbolChecks() {
    const el = $("symbolFilters");
    el.innerHTML = state.allSymbols.map(function (symbol) {
      const on = state.symbols && state.symbols.has(symbol) ? " checked" : "";
      return `<label class="check"><input type="checkbox" data-symbol="${esc(symbol)}"${on} /> ${esc(symbol)}</label>`;
    }).join("");
  }

  function fillSelect(id, options, current) {
    const el = $(id);
    el.innerHTML = options.map(function (opt) {
      return `<option value="${esc(opt.value)}">${esc(opt.label)}</option>`;
    }).join("");
    const ok = Array.from(el.options).some(function (opt) { return opt.value === current; });
    el.value = ok ? current : (options[0] ? options[0].value : "");
    return el.value;
  }

  function renderReasonOptions() {
    const options = [{ value: "", label: "Tất cả" }].concat(state.allReasons.map(function (key) {
      return { value: key, label: reasonLabel(key) };
    }));
    state.reason = fillSelect("filterReason", options, state.reason);
  }

  function renderFileOptions() {
    const options = [{ value: "", label: "Tất cả file" }].concat(state.files.map(function (f) {
      return { value: f.name, label: f.name };
    }));
    state.file = fillSelect("filterFile", options, state.file);
  }

  function syncFilterDom() {
    $("filterSide").value = state.side || "";
    showDate("filterFrom", state.from);
    showDate("filterTo", state.to);
    $("tradeSearch").value = state.search || "";
  }

  function refreshAfterFiles() {
    const symbols = new Set();
    const reasons = new Set();
    state.files.forEach(function (f) {
      f.trades.forEach(function (t) {
        symbols.add(t.symbol);
        reasons.add(t.reason);
      });
    });
    const allSymbols = Array.from(symbols).sort();
    const known = state.knownSymbols;
    if (!state.symbolFilterReady) {
      state.symbols = new Set(allSymbols);
      if (allSymbols.length) state.symbolFilterReady = true;
    } else {
      const prev = state.symbols || new Set();
      const next = new Set();
      allSymbols.forEach(function (symbol) {
        const isNew = known.size > 0 && !known.has(symbol);
        if (prev.has(symbol) || isNew) next.add(symbol);
      });
      state.symbols = next;
    }
    state.knownSymbols = new Set(allSymbols);
    state.allSymbols = allSymbols;
    state.allReasons = sortReasons(Array.from(reasons));
    renderFileList();
    renderSymbolChecks();
    renderReasonOptions();
    renderFileOptions();
    syncFilterDom();
    const has = state.files.some(function (f) { return f.trades.length; });
    $("dashboard").classList.toggle("hidden", !has);
    $("emptyHint").classList.toggle("hidden", has);
    if (has) renderResults();
    else {
      state.report = null;
      state.shown = [];
      $("stats").innerHTML = "";
      $("tradeTableWrap").innerHTML = "";
      $("pageInfo").textContent = "";
      $("filterMeta").textContent = "";
      $("pager").classList.add("hidden");
      $("pagePrev").disabled = true;
      $("pageNext").disabled = true;
    }
  }

  function collect() {
    const files = state.files.slice().sort(function (a, b) {
      return a.importedAt - b.importedAt || a.name.localeCompare(b.name);
    });
    const map = new Map();
    let dupes = 0;
    files.forEach(function (f) {
      if (state.file && f.name !== state.file) return;
      f.trades.forEach(function (t) {
        if (map.has(t.ticket)) dupes++;
        map.set(t.ticket, t);
      });
    });
    if (state.from && state.to && state.from > state.to) {
      return { trades: [], dupes: dupes, invalidRange: true, total: map.size };
    }
    const trades = [];
    map.forEach(function (t) {
      if (state.symbols && !state.symbols.has(t.symbol)) return;
      if (state.side && t.side !== state.side) return;
      if (state.reason && t.reason !== state.reason) return;
      if (state.from) {
        const start = HistoryAnalyze.ictDayStart(state.from);
        if (Number.isFinite(start) && t.close < start) return;
      }
      if (state.to) {
        const end = HistoryAnalyze.ictDayStart(state.to);
        if (Number.isFinite(end) && t.close >= end + 86400000) return;
      }
      trades.push(t);
    });
    return { trades: trades, dupes: dupes, invalidRange: false, total: map.size };
  }

  function filterMeta(collected) {
    if (state.dateError) return state.dateError;
    if (collected.invalidRange) return "Ngày bắt đầu đang sau ngày kết thúc.";
    let text = collected.trades.length + " lệnh sau lọc";
    if (collected.trades.length !== collected.total) text += " / " + collected.total + " lệnh";
    if (collected.dupes) text += " · gộp " + collected.dupes + " ticket trùng";
    return text;
  }

  function td(html, cls) {
    const allowed = cls === "left" || cls === "pos" || cls === "neg";
    return `<td${allowed ? ` class="${cls}"` : ""}>${html}</td>`;
  }

  function kpi(label, value, cls, id) {
    const klass = cls === "pos" || cls === "neg" ? " " + cls : "";
    const idAttr = id === "kpiNet" ? ' id="kpiNet"' : "";
    return `<article class="kpi"><div class="label">${esc(label)}</div><div class="value${klass}"${idAttr}>${esc(value)}</div></article>`;
  }

  function statsHtml(report) {
    if (!report.n) {
      return `<section class="card" id="sec-overview"><h2>Tổng quan</h2><p>Không có lệnh khớp bộ lọc.</p></section>`;
    }
    const ddValue = report.maxDrawdown > 0
      ? fmtMoney(-report.maxDrawdown) + (report.maxDrawdownPct != null ? " (" + fmtPct(report.maxDrawdownPct) + ")" : "")
      : "—";

    return `<section class="card" id="sec-overview">
      <h2>Tổng quan</h2>
      <div class="kpi-grid">
        ${kpi("Net", fmtMoney(report.net), moneyClass(report.net), "kpiNet")}
        ${kpi("Profit factor", fmtPf(report.profitFactor), report.profitFactor >= 1 ? "pos" : report.profitFactor != null ? "neg" : "")}
        ${kpi("Win rate", fmtPct(report.winRate))}
        ${kpi("Kỳ vọng / lệnh", fmtMoney(report.avg), moneyClass(report.avg))}
        ${kpi("Payoff", report.payoff == null ? "—" : report.payoff.toFixed(2))}
        ${kpi("Max drawdown", ddValue, report.maxDrawdown > 0 ? "neg" : "")}
        ${kpi("Số lệnh", String(report.n))}
        ${kpi("Giữ lệnh TB", fmtDuration(report.avgHold))}
      </div>
    </section>`;
  }

  function renderResults() {
    try {
      const collected = collect();
      state.shown = collected.trades;
      state.report = HistoryAnalyze.analyze(collected.trades);
      $("stats").innerHTML = statsHtml(state.report);
      $("filterMeta").textContent = filterMeta(collected);
      renderTrades();
      saveFilters();
    } catch (err) {
      setMsg("persistError", "Không tính được số liệu.");
    }
  }

  function sortValue(t, key) {
    switch (key) {
      case "open": return t.open;
      case "close": return t.close;
      case "symbol": return t.symbol;
      case "side": return t.side;
      case "lots": return t.lots;
      case "openPrice": return t.openPrice;
      case "closePrice": return t.closePrice;
      case "sl": return t.sl;
      case "tp": return t.tp;
      case "net": return t.net;
      case "r": return t.r;
      case "hold": return t.holdMs;
      case "reason": return t.reason;
      case "ticket": return ticketSortKey(t.ticket);
      default: return t.close;
    }
  }

  function ticketSortKey(ticket) {
    const raw = String(ticket);
    if (!/^\d+$/.test(raw)) return raw;
    const n = Number(raw);
    if (!Number.isFinite(n) || String(n) !== raw) return raw;
    return n;
  }

  function cmpTrade(a, b) {
    const va = sortValue(a, state.sortKey);
    const vb = sortValue(b, state.sortKey);
    const na = va == null || va === "" || (typeof va === "number" && !Number.isFinite(va));
    const nb = vb == null || vb === "" || (typeof vb === "number" && !Number.isFinite(vb));
    if (na && nb) return 0;
    if (na) return 1;
    if (nb) return -1;
    if (typeof va === "number" && typeof vb === "number") return (va - vb) * state.sortDir;
    return String(va).localeCompare(String(vb)) * state.sortDir;
  }

  function arrow(key) {
    if (state.sortKey !== key) return "";
    return state.sortDir < 0 ? " ↓" : " ↑";
  }

  function th(key, label, cls) {
    return `<th data-sort="${key}"${cls ? ` class="${cls}"` : ""}>${esc(label)}${arrow(key)}</th>`;
  }

  function renderTrades() {
    const q = state.search.trim().toLowerCase();
    let rows = state.shown.slice();
    if (q) {
      rows = rows.filter(function (t) {
        return t.ticket.toLowerCase().indexOf(q) >= 0
          || t.symbol.toLowerCase().indexOf(q) >= 0
          || t.reason.indexOf(q) >= 0
          || t.side.indexOf(q) >= 0
          || reasonLabel(t.reason).toLowerCase().indexOf(q) >= 0;
      });
    }
    rows.sort(cmpTrade);
    const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    if (state.page > pages - 1) state.page = pages - 1;
    if (state.page < 0) state.page = 0;
    const start = state.page * PAGE_SIZE;
    const slice = rows.slice(start, start + PAGE_SIZE);
    const body = slice.map(function (t) {
      const lot = t.partial && t.originalLots != null ? fmtLots(t.lots) + " / " + fmtLots(t.originalLots) : fmtLots(t.lots);
      return `<tr>
        ${td(fmtDayTime(t.open))}
        ${td(fmtDayTime(t.close))}
        ${td(esc(t.symbol), "left")}
        ${td(`<span class="badge ${t.side === "buy" ? "buy" : "sell"}">${t.side === "buy" ? "Buy" : "Sell"}</span>`, "left")}
        ${td(lot)}
        ${td(fmtPx(t.openPrice))}
        ${td(fmtPx(t.closePrice))}
        ${td(fmtPx(t.sl))}
        ${td(fmtPx(t.tp))}
        ${td(fmtMoney(t.net), moneyClass(t.net))}
        ${td(fmtR(t.r), moneyClass(t.r))}
        ${td(fmtDuration(t.holdMs))}
        ${td(esc(reasonLabel(t.reason)), "left")}
        ${td(esc(t.ticket), "left")}
      </tr>`;
    }).join("");
    const empty = rows.length ? body : `<tr><td class="left" colspan="14">Không có lệnh.</td></tr>`;
    $("tradeTableWrap").innerHTML = `<table><thead><tr>
      ${th("open", "Mở")}
      ${th("close", "Đóng")}
      ${th("symbol", "Symbol", "left")}
      ${th("side", "Side", "left")}
      ${th("lots", "Lot")}
      ${th("openPrice", "Vào")}
      ${th("closePrice", "Ra")}
      ${th("sl", "SL")}
      ${th("tp", "TP")}
      ${th("net", "Net")}
      ${th("r", "R")}
      ${th("hold", "Giữ")}
      ${th("reason", "Lý do", "left")}
      ${th("ticket", "Ticket", "left")}
    </tr></thead><tbody>${empty}</tbody></table>`;
    const from = rows.length ? start + 1 : 0;
    const to = start + slice.length;
    $("pageInfo").textContent = rows.length ? from + "–" + to + " / " + rows.length : "0 lệnh";
    $("pagePrev").disabled = state.page <= 0;
    $("pageNext").disabled = start + PAGE_SIZE >= rows.length;
    $("pager").classList.toggle("hidden", rows.length <= PAGE_SIZE);
  }

  function savedTheme() {
    try { return localStorage.getItem("mt5-theme") === "dark" ? "dark" : "light"; }
    catch (e) { return "light"; }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    const btn = $("themeToggle");
    if (btn) btn.textContent = theme === "dark" ? "Chế độ sáng" : "Chế độ tối";
    try { localStorage.setItem("mt5-theme", theme); } catch (e) {}
  }

  function resetFilters() {
    state.symbols = new Set(state.allSymbols);
    state.side = "";
    state.reason = "";
    state.file = "";
    state.from = "";
    state.to = "";
    state.dateError = "";
    state.search = "";
    state.page = 0;
    renderSymbolChecks();
    renderReasonOptions();
    renderFileOptions();
    syncFilterDom();
    renderResults();
  }

  function bind() {
    $("themeToggle").addEventListener("click", function () {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
    });
    $("btnPaste").addEventListener("click", function () { ingestPastedCsv(); });
    $("linkTo").placeholder = toDisplayDate(todayKey());
    ["linkFrom", "linkTo"].forEach(function (id) {
      const el = $(id);
      el.dataset.prev = el.value || "";
      el.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          onPlainDateBlur(id);
          return;
        }
        if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
        const allow = ["Backspace", "Delete", "Tab", "ArrowLeft", "ArrowRight", "Home", "End"];
        if (allow.indexOf(ev.key) >= 0) return;
        if (!/^\d$/.test(ev.key)) ev.preventDefault();
      });
      el.addEventListener("paste", function (ev) {
        const text = (ev.clipboardData && ev.clipboardData.getData("text")) || "";
        const key = parseDisplayDate(String(text).trim());
        if (!key) return;
        ev.preventDefault();
        const shown = toDisplayDate(key);
        el.value = shown;
        el.dataset.prev = shown;
        el.classList.remove("date-bad");
        el.setSelectionRange(shown.length, shown.length);
      });
      el.addEventListener("input", function () { onPlainDateInput(id); });
      el.addEventListener("blur", function () { onPlainDateBlur(id); });
    });
    $("btnOrders").addEventListener("click", function () {
      const url = ordersHistoryUrl();
      if (!url) return;
      const opened = window.open(url, "_blank", "noopener,noreferrer");
      if (opened) opened.opener = null;
      else setMsg("importError", "Trình duyệt đã chặn cửa sổ mới.");
    });
    $("btnPick").addEventListener("click", function () { $("fileInput").click(); });
    $("fileInput").addEventListener("change", function () {
      if ($("fileInput").files && $("fileInput").files.length) ingestFileList($("fileInput").files);
      $("fileInput").value = "";
    });
    const zone = $("dropzone");
    zone.addEventListener("dragover", function (ev) {
      ev.preventDefault();
      zone.classList.add("drag");
    });
    zone.addEventListener("dragleave", function () { zone.classList.remove("drag"); });
    zone.addEventListener("drop", function (ev) {
      ev.preventDefault();
      zone.classList.remove("drag");
      if (ev.dataTransfer && ev.dataTransfer.files.length) ingestFileList(ev.dataTransfer.files);
    });
    $("btnClear").addEventListener("click", async function () {
      if (!state.files.length) return;
      if (!window.confirm("Xóa mọi file CSV đã import trên trình duyệt này?")) return;
      state.files = [];
      state.symbols = null;
      state.symbolFilterReady = false;
      state.knownSymbols = new Set();
      try { await idbClear(); }
      catch (err) { setMsg("persistError", "Không xóa được bộ nhớ trình duyệt."); }
      refreshAfterFiles();
    });
    $("fileList").addEventListener("click", async function (ev) {
      const btn = ev.target.closest("[data-name]");
      if (!btn || btn.disabled) return;
      const name = btn.getAttribute("data-name");
      const file = state.files.find(function (item) { return item.name === name; });
      if (!file) return;
      btn.disabled = true;
      state.files = state.files.filter(function (item) { return item !== file; });
      try { await idbDelete(file.name); }
      catch (err) { setMsg("persistError", "Không xóa được file trong bộ nhớ trình duyệt."); }
      refreshAfterFiles();
    });
    $("symbolFilters").addEventListener("change", function () {
      const boxes = $("symbolFilters").querySelectorAll("input[data-symbol]");
      state.symbols = new Set(Array.from(boxes).filter(function (box) { return box.checked; }).map(function (box) {
        return box.dataset.symbol;
      }));
      state.page = 0;
      renderResults();
    });
    $("filterSide").addEventListener("change", function () {
      state.side = $("filterSide").value;
      state.page = 0;
      renderResults();
    });
    $("filterReason").addEventListener("change", function () {
      state.reason = $("filterReason").value;
      state.page = 0;
      renderResults();
    });
    $("filterFile").addEventListener("change", function () {
      state.file = $("filterFile").value;
      state.page = 0;
      renderResults();
    });
    ["filterFrom", "filterTo"].forEach(function (id) {
      const keyName = id === "filterFrom" ? "from" : "to";
      const el = $(id);
      el.dataset.prev = el.value || "";
      el.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          onDateBlur(id, keyName);
          return;
        }
        if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
        const allow = ["Backspace", "Delete", "Tab", "ArrowLeft", "ArrowRight", "Home", "End"];
        if (allow.indexOf(ev.key) >= 0) return;
        if (!/^\d$/.test(ev.key)) ev.preventDefault();
      });
      el.addEventListener("paste", function (ev) {
        const text = (ev.clipboardData && ev.clipboardData.getData("text")) || "";
        const key = parseDisplayDate(String(text).trim());
        if (!key) return;
        ev.preventDefault();
        const shown = toDisplayDate(key);
        el.value = shown;
        el.dataset.prev = shown;
        el.classList.remove("date-bad");
        el.setSelectionRange(shown.length, shown.length);
        state.dateError = "";
        setDateFilter(keyName, key);
      });
      el.addEventListener("input", function () { onDateInput(id, keyName); });
      el.addEventListener("blur", function () { onDateBlur(id, keyName); });
    });
    $("btnResetFilters").addEventListener("click", resetFilters);
    $("tradeSearch").addEventListener("input", function () {
      state.search = $("tradeSearch").value;
      state.page = 0;
      renderTrades();
      saveFilters();
    });
    $("pagePrev").addEventListener("click", function () {
      state.page -= 1;
      renderTrades();
    });
    $("pageNext").addEventListener("click", function () {
      state.page += 1;
      renderTrades();
    });
    $("tradeTableWrap").addEventListener("click", function (ev) {
      const head = ev.target.closest("th[data-sort]");
      if (!head) return;
      const key = head.dataset.sort;
      if (state.sortKey === key) state.sortDir *= -1;
      else {
        state.sortKey = key;
        state.sortDir = TEXT_SORT[key] ? 1 : -1;
      }
      state.page = 0;
      renderTrades();
    });
  }

  function init() {
    applyTheme(savedTheme());
    if (!window.HistoryAnalyze) {
      setMsg("importError", "Không tải được analyze.js.");
      return;
    }
    bind();
    loadFiles().then(function () {
      restoreFilters();
      refreshAfterFiles();
    }).catch(function () {
      setMsg("persistError", "Không đọc được dữ liệu đã import. Có thể chọn file lại cho phiên này.");
      refreshAfterFiles();
    });
  }

  init();
})();
