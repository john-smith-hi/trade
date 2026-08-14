// Checklist setup — dùng MT5 common (proxy.php + apiGet/apiPost/apiPut/apiDelete).
const {
  el,
  initTheme,
  toggleTheme,
  apiGet,
  apiPost,
  apiPut,
  apiDelete,
  withBusy,
  markApiOk,
  markApiError,
} = window.MT5;

const WEEKDAY_LABELS = {
  1: "Thứ 2", 2: "Thứ 3", 3: "Thứ 4", 4: "Thứ 5",
  5: "Thứ 6", 6: "Thứ 7", 7: "Chủ nhật",
};

const ACCOUNT_KEY = "setup-quote-account";

const state = {
  week: null,
  weekday: null,
  canTrade: false,
  editingSetupId: null,
  quoteSeq: 0,
};

function formatDate(iso) {
  if (!iso) return "--";
  const parts = iso.split("-");
  if (parts.length !== 3) return iso;
  return `${parts[2]}/${parts[1]}`;
}

function numOrEmpty(value) {
  return value === null || value === undefined ? "" : value;
}

function computeRR(side, entry, sl, tp) {
  if ([entry, sl, tp].some((v) => v === null || v === "" || Number.isNaN(v))) {
    return null;
  }
  let risk;
  let reward;
  if (side === "buy") {
    risk = entry - sl;
    reward = tp - entry;
  } else {
    risk = sl - entry;
    reward = entry - tp;
  }
  if (risk <= 0 || reward <= 0) return null;
  return reward / risk;
}

function updateStructureHint() {
  const side = el("side").value;
  const expected = side === "buy" ? "HL (Higher Low)" : "LH (Lower High)";
  el("structurePatternHint").textContent =
    `Cần thấy ${expected} hình thành trước khi vào ${side.toUpperCase()}.`;
}

function updateTradeRangeVisibility() {
  const isSideway = (state.week && state.week.trend_d1) === "sideway";
  el("tradeRangeField").classList.toggle("hidden", !isSideway);
}

function updateRRPreview() {
  const side = el("side").value;
  const entry = parseFloat(el("entry").value);
  const sl = parseFloat(el("sl").value);
  const tp = parseFloat(el("tp").value);
  const rr = computeRR(side, entry, sl, tp);
  const hint = el("rrHint");
  if (rr === null) {
    hint.textContent = "RR: -- (cần Entry/SL/TP hợp lệ theo hướng lệnh)";
  } else {
    hint.textContent = `RR: 1 : ${rr.toFixed(2)}${rr >= 2 ? "  ✓ đạt tối thiểu 1:2" : "  ✗ chưa đạt 1:2"}`;
  }
}

function setEntryHint(text, asError = false) {
  const hint = el("entryHint");
  hint.textContent = text || "";
  hint.classList.toggle("hint-error", !!asError && !!text);
}

function renderWeekBanner() {
  const week = state.week;
  const banner = el("weekBanner");
  if (!week) {
    banner.textContent = "Chưa có tuần nào đang hoạt động.";
    return;
  }
  const statusLabel = week.status === "active" ? "Đang hoạt động" : "Đã đóng";
  const pillClass = week.status === "active" ? "pill-active" : "pill-closed";
  banner.innerHTML =
    `${week.id} · ${WEEKDAY_LABELS[state.weekday]} · Thứ 2 ${formatDate(week.week_start)}` +
    ` – Thứ 6 ${formatDate(week.week_end)}` +
    ` <span class="pill ${pillClass}">${statusLabel}</span>`;
}

function fillObservationForm(week) {
  el("mondayHigh").value = numOrEmpty(week.monday_high);
  el("mondayLow").value = numOrEmpty(week.monday_low);
  el("prevHigh").value = numOrEmpty(week.prev_week_high);
  el("prevLow").value = numOrEmpty(week.prev_week_low);
  el("trendD1").value = week.trend_d1 || "";
  el("trendH4").value = week.trend_h4 || "";
  el("newsNotes").value = week.news_notes || "";
}

function setFormDisabled(disabled) {
  [
    "mondayHigh", "mondayLow", "prevHigh", "prevLow", "trendD1", "trendH4", "newsNotes",
    "btnSaveWeek", "account", "symbol", "side", "tradeRange", "zoneConfirmed", "noChase",
    "structureBreak", "entry", "btnFetchEntry", "sl", "tp", "newsOk", "commitClose",
    "btnCheck", "btnReset",
  ].forEach((id) => {
    const node = el(id);
    if (node) node.disabled = disabled;
  });
  document.querySelectorAll(".reaction").forEach((node) => {
    node.disabled = disabled;
  });
}

async function loadAccounts() {
  const data = await apiGet("/api/accounts", { useCache: true });
  const accounts = data.accounts || [];
  const select = el("account");
  const saved = localStorage.getItem(ACCOUNT_KEY) || "";
  select.innerHTML = "";
  if (!accounts.length) {
    select.innerHTML = '<option value="">-- chưa có account --</option>';
    setEntryHint("Chưa có account trong accounts.xml — không lấy được giá.", true);
    return;
  }
  accounts.forEach((acc) => {
    const opt = document.createElement("option");
    opt.value = acc.name;
    opt.textContent = acc.name + (acc.server ? ` (${acc.server})` : "");
    select.appendChild(opt);
  });
  if (saved && accounts.some((a) => a.name === saved)) {
    select.value = saved;
  }
}

async function fetchEntryQuote() {
  const account = el("account").value;
  const symbol = (el("symbol").value || "").trim();
  const side = el("side").value;
  if (!account) {
    setEntryHint("Chọn account để lấy giá.", true);
    return;
  }
  if (!symbol) {
    setEntryHint("Nhập symbol để lấy giá.", true);
    return;
  }

  const seq = ++state.quoteSeq;
  setEntryHint("Đang lấy giá thị trường...");
  el("btnFetchEntry").disabled = true;

  try {
    const q = new URLSearchParams({ account, symbol, side });
    const data = await withBusy(
      () => apiGet(`/api/quote?${q}`, { useCache: false, timeoutMs: 30000 }),
      "Đang lấy giá thị trường...",
    );
    if (seq !== state.quoteSeq) return;
    el("entry").value = data.entry;
    updateRRPreview();
    setEntryHint(
      `Quote ${data.symbol}: bid=${data.bid} ask=${data.ask} → entry ${side.toUpperCase()}=${data.entry}`,
    );
    markApiOk("Đã lấy giá thị trường");
  } catch (err) {
    if (seq !== state.quoteSeq) return;
    setEntryHint(`Không lấy được giá: ${err.message || err}`, true);
  } finally {
    if (seq === state.quoteSeq) {
      const closed = state.week && state.week.status !== "active";
      el("btnFetchEntry").disabled = !!closed;
    }
  }
}

function renderSetupsTable(setups) {
  const body = el("setupTableBody");
  body.innerHTML = "";
  if (!setups || !setups.length) {
    body.innerHTML = '<tr class="empty-row"><td colspan="6">Chưa có setup nào trong tuần này</td></tr>';
    return;
  }
  setups.slice().reverse().forEach((setup) => {
    const tr = document.createElement("tr");
    const time = (setup.created_at || "").replace("T", " ").slice(0, 16);
    const rrText = setup.rr === null || setup.rr === undefined ? "--" : setup.rr.toFixed(2);
    const statusClass = setup.result === "pass" ? "status-pass" : "status-fail";
    const statusText = setup.result === "pass" ? "PASS" : "FAIL";
    tr.innerHTML =
      `<td>${time}</td>` +
      `<td>${setup.symbol}</td>` +
      `<td>${setup.side.toUpperCase()}</td>` +
      `<td>${rrText}</td>` +
      `<td><span class="status-pill ${statusClass}">${statusText}</span></td>` +
      `<td class="row-actions"></td>`;

    const actionsCell = tr.querySelector(".row-actions");
    if (state.week.status === "active") {
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn btn-secondary";
      editBtn.textContent = "Sửa";
      editBtn.addEventListener("click", () => loadSetupIntoForm(setup));

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn-danger-outline";
      delBtn.textContent = "Xóa";
      delBtn.addEventListener("click", () => deleteSetup(setup.id));

      actionsCell.appendChild(editBtn);
      actionsCell.appendChild(delBtn);
    }
    body.appendChild(tr);
  });
}

function render(data) {
  state.week = data.week;
  state.weekday = data.weekday;
  state.canTrade = data.can_trade;

  el("weekendCard").classList.toggle("hidden", !!data.week);
  el("mainCard").classList.toggle("hidden", !data.week);

  if (!data.week) {
    markApiOk("Kết nối OK — cuối tuần, chưa có tuần mới.");
    return;
  }

  markApiOk("Đã kết nối API (qua proxy.php)");
  renderWeekBanner();
  fillObservationForm(data.week);
  updateTradeRangeVisibility();
  renderSetupsTable(data.week.setups);

  const isClosed = data.week.status !== "active";
  const isMonday = data.weekday === 1;

  el("closedNotice").classList.toggle("hidden", !isClosed);
  el("mondayNotice").classList.toggle("hidden", isClosed || !isMonday);

  setFormDisabled(isClosed);
  el("btnCheck").disabled = isClosed || isMonday;
}

async function loadWeek() {
  try {
    const data = await apiGet("/api/setup/week", { useCache: false });
    render(data);
  } catch (err) {
    markApiError(err);
  }
}

async function saveWeekObservations() {
  const payload = {
    monday_high: el("mondayHigh").value === "" ? null : parseFloat(el("mondayHigh").value),
    monday_low: el("mondayLow").value === "" ? null : parseFloat(el("mondayLow").value),
    prev_week_high: el("prevHigh").value === "" ? null : parseFloat(el("prevHigh").value),
    prev_week_low: el("prevLow").value === "" ? null : parseFloat(el("prevLow").value),
    trend_d1: el("trendD1").value,
    trend_h4: el("trendH4").value,
    news_notes: el("newsNotes").value,
  };
  el("weekSaveHint").textContent = "Đang lưu...";
  try {
    const data = await apiPut(`/api/setup/week/${encodeURIComponent(state.week.id)}`, payload);
    state.week = data.week;
    updateTradeRangeVisibility();
    el("weekSaveHint").textContent = `Đã lưu lúc ${new Date().toLocaleTimeString("vi-VN")}`;
    markApiOk("Đã lưu quan sát tuần");
  } catch (err) {
    el("weekSaveHint").textContent = `Lỗi: ${err.message || err}`;
  }
}

function collectSetupPayload() {
  const reactions = Array.from(document.querySelectorAll(".reaction:checked")).map((node) => node.value);
  return {
    week_id: state.week.id,
    symbol: el("symbol").value,
    side: el("side").value,
    trade_range: el("tradeRange").checked,
    zone_confirmed: el("zoneConfirmed").checked,
    no_chase: el("noChase").checked,
    reactions,
    structure_break: el("structureBreak").checked,
    entry: el("entry").value === "" ? null : parseFloat(el("entry").value),
    sl: el("sl").value === "" ? null : parseFloat(el("sl").value),
    tp: el("tp").value === "" ? null : parseFloat(el("tp").value),
    news_ok: el("newsOk").checked,
    commit_sl_tp_close: el("commitClose").checked,
  };
}

function showResult(setup) {
  const box = el("resultBox");
  box.classList.remove("hidden", "pass", "fail");
  box.classList.add(setup.result);
  el("resultTitle").textContent = setup.result === "pass"
    ? "✓ ĐỦ ĐIỀU KIỆN VÀO LỆNH"
    : "✗ CHƯA ĐỦ ĐIỀU KIỆN — xem lý do bên dưới";
  el("resultFails").innerHTML = "";
  (setup.fails || []).forEach((msg) => {
    const li = document.createElement("li");
    li.textContent = msg;
    el("resultFails").appendChild(li);
  });
}

async function submitSetup() {
  const payload = collectSetupPayload();
  try {
    const data = state.editingSetupId
      ? await apiPut(`/api/setup/setups/${encodeURIComponent(state.editingSetupId)}`, payload)
      : await apiPost("/api/setup/setups", payload);
    state.week = data.week;
    showResult(data.setup);
    renderSetupsTable(data.week.setups);
    exitEditMode();
    markApiOk(state.editingSetupId ? "Đã cập nhật setup" : "Đã lưu setup");
  } catch (err) {
    el("resultBox").classList.remove("hidden", "pass");
    el("resultBox").classList.add("fail");
    el("resultTitle").textContent = "Lỗi";
    el("resultFails").innerHTML = `<li>${err.message || err}</li>`;
  }
}

function loadSetupIntoForm(setup) {
  state.editingSetupId = setup.id;
  el("setupFormTitle").textContent = `Sửa setup #${setup.id}`;
  el("btnCheck").textContent = "Chấm điểm & cập nhật setup";
  el("symbol").value = setup.symbol;
  el("side").value = setup.side;
  el("tradeRange").checked = !!setup.trade_range;
  const checklist = setup.checklist || {};
  el("zoneConfirmed").checked = !!(checklist["3"] && checklist["3"].ok);
  el("noChase").checked = !!(checklist["4"] && checklist["4"].ok);
  el("structureBreak").checked = !!(checklist["6"] && checklist["6"].ok);
  el("newsOk").checked = !!(checklist["8"] && checklist["8"].ok);
  el("commitClose").checked = !!(checklist["10"] && checklist["10"].ok);
  el("entry").value = numOrEmpty(setup.entry);
  el("sl").value = numOrEmpty(setup.sl);
  el("tp").value = numOrEmpty(setup.tp);
  document.querySelectorAll(".reaction").forEach((node) => { node.checked = false; });
  updateStructureHint();
  updateRRPreview();
  el("resultBox").classList.add("hidden");
  window.scrollTo({ top: el("setupFormTitle").offsetTop - 20, behavior: "smooth" });
}

function exitEditMode() {
  state.editingSetupId = null;
  el("setupFormTitle").textContent = "Chấm điểm setup trước khi vào lệnh";
  el("btnCheck").textContent = "Chấm điểm & lưu setup";
}

async function deleteSetup(setupId) {
  if (!window.confirm(`Xóa setup #${setupId}?`)) return;
  try {
    const path = `/api/setup/setups/${encodeURIComponent(setupId)}?week_id=${encodeURIComponent(state.week.id)}`;
    const data = await apiDelete(path);
    state.week = data.week;
    renderSetupsTable(data.week.setups);
    if (state.editingSetupId === setupId) exitEditMode();
    markApiOk(`Đã xóa setup #${setupId}`);
  } catch (err) {
    window.alert(`Lỗi xóa: ${err.message || err}`);
  }
}

function resetForm() {
  el("zoneConfirmed").checked = false;
  el("noChase").checked = false;
  el("structureBreak").checked = false;
  el("newsOk").checked = false;
  el("commitClose").checked = false;
  el("tradeRange").checked = false;
  document.querySelectorAll(".reaction").forEach((node) => { node.checked = false; });
  el("entry").value = "";
  el("sl").value = "";
  el("tp").value = "";
  setEntryHint("");
  updateRRPreview();
  el("resultBox").classList.add("hidden");
  exitEditMode();
}

function bindEvents() {
  el("themeToggle").addEventListener("click", toggleTheme);
  el("btnSaveWeek").addEventListener("click", saveWeekObservations);
  el("btnCheck").addEventListener("click", submitSetup);
  el("btnReset").addEventListener("click", resetForm);
  el("btnFetchEntry").addEventListener("click", fetchEntryQuote);
  el("account").addEventListener("change", () => {
    localStorage.setItem(ACCOUNT_KEY, el("account").value);
    fetchEntryQuote();
  });
  el("side").addEventListener("change", () => {
    updateStructureHint();
    updateRRPreview();
    fetchEntryQuote();
  });
  el("symbol").addEventListener("change", fetchEntryQuote);
  ["entry", "sl", "tp"].forEach((id) => {
    el(id).addEventListener("input", updateRRPreview);
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  bindEvents();
  updateStructureHint();
  updateRRPreview();
  try {
    await loadAccounts();
    await loadWeek();
    if (el("account").value && el("symbol").value.trim()) {
      fetchEntryQuote();
    }
  } catch (err) {
    markApiError(err);
  }
});
