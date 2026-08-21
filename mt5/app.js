// Trang ra lệnh — dùng MT5 common (API cache + busy + refresh nhẹ).
const { el, initTheme, toggleTheme, apiGet, apiPost, withBusy, onVisibleRefresh, markApiOk, markApiError } = window.MT5;

function showConfirmModal(message) {
  return new Promise((resolve) => {
    const overlay = el("confirmModal");
    el("modalMessage").textContent = message;
    overlay.classList.remove("hidden");

    const cleanup = (result) => {
      overlay.classList.add("hidden");
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      overlay.removeEventListener("click", onOverlayClick);
      resolve(result);
    };
    const okBtn = el("modalOk");
    const cancelBtn = el("modalCancel");
    const onOk = () => cleanup(true);
    const onCancel = () => cleanup(false);
    const onOverlayClick = (e) => {
      if (e.target === overlay) cleanup(false);
    };

    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
    overlay.addEventListener("click", onOverlayClick);
  });
}

function renderAccounts(accounts) {
  const select = el("account");
  const previous = select.value;
  select.innerHTML = "";

  if (!accounts.length) {
    select.innerHTML = '<option value="">(không có account nào trong accounts.xml)</option>';
    el("accountInfo").textContent = "";
    return;
  }

  for (const acc of accounts) {
    const opt = document.createElement("option");
    opt.value = acc.name;
    opt.textContent = acc.name;
    select.appendChild(opt);
  }

  select.value = accounts.some((a) => a.name === previous) ? previous : accounts[0].name;
  updateAccountInfo(accounts);
  select.onchange = () => {
    updateAccountInfo(accounts);
    invalidatePreview();
    autofillTpSl();
  };
}

function updateAccountInfo(accounts) {
  const acc = accounts.find((a) => a.name === el("account").value);
  if (!acc) {
    el("accountInfo").textContent = "";
    return;
  }
  const autoCopy = acc.auto_copy_enabled && acc.auto_copy_targets.length
    ? `auto-copy → ${acc.auto_copy_targets.join(", ")}`
    : "không auto-copy";
  const maxLoss = acc.xauusd_max_loss == null ? "không giới hạn" : acc.xauusd_max_loss;
  const defaultLot = acc.default_lot ?? 0.01;
  el("accountInfo").textContent =
    `login: ${acc.login} | server: ${acc.server} | suffix: "${acc.suffix}" | multi: ${acc.multi} | default_lot: ${defaultLot} | max_loss: ${maxLoss} | ${autoCopy}`;
  applyDefaultLot();
}

let lastAccounts = [];
let fillSeq = 0;
/** null = không áp dụng; false = action cần lệnh nhưng không có */
let actionHasPositions = null;
let actionHasOrders = null;
let previewValid = false;
let previewSnapshot = null;

function getSide() {
  return el("side").value === "sell" ? "sell" : "buy";
}

function setSide(side) {
  const value = side === "sell" ? "sell" : "buy";
  el("side").value = value;
  document.querySelectorAll("#sideToggle [data-side]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.side === value);
  });
}

function accountDefaultLot(accountName) {
  const acc = lastAccounts.find((a) => a.name === accountName);
  const lot = Number(acc?.default_lot);
  return Number.isFinite(lot) && lot > 0 ? lot : 0.01;
}

function resolveLot() {
  const raw = el("lot").value.trim();
  if (raw !== "") {
    const lot = Number(raw);
    if (Number.isFinite(lot) && lot > 0) return lot;
  }
  return accountDefaultLot(el("account").value);
}

function applyDefaultLot() {
  const lotInput = el("lot");
  if (!lotInput) return;
  const lot = accountDefaultLot(el("account").value);
  lotInput.value = String(lot);
  lotInput.placeholder = `default_lot`;
}

function actionNeedsOpenPositions(action = el("action").value) {
  return action === "modify-all" || action === "close-all";
}

function actionNeedsPendingOrders(action = el("action").value) {
  return action === "cancel-pending";
}

function actionUsesQuote(action = el("action").value) {
  return action === "open" || action === "pending";
}

function invalidatePreview() {
  previewValid = false;
  previewSnapshot = null;
  syncConfirmEnabled();
}

function markPreviewOk() {
  previewValid = true;
  previewSnapshot = payloadSnapshot();
  syncConfirmEnabled();
}

function payloadSnapshot() {
  return JSON.stringify(buildPayload(false));
}

function payloadsMatchPreview() {
  return previewValid && previewSnapshot === payloadSnapshot();
}

function setPreviewEnabled(enabled) {
  const preview = el("btnPreview");
  if (preview) preview.disabled = !enabled;
}

function syncConfirmEnabled() {
  const confirm = el("btnConfirm");
  if (!confirm) return;
  let enabled = payloadsMatchPreview();
  if (actionNeedsOpenPositions()) {
    enabled = enabled && actionHasPositions === true;
  } else if (actionNeedsPendingOrders()) {
    enabled = enabled && actionHasOrders === true;
  }
  confirm.disabled = !enabled;
}

function syncExecuteForAction() {
  if (actionNeedsOpenPositions()) {
    setPreviewEnabled(actionHasPositions === true);
  } else if (actionNeedsPendingOrders()) {
    setPreviewEnabled(actionHasOrders === true);
  } else {
    actionHasPositions = null;
    actionHasOrders = null;
    setPreviewEnabled(true);
  }
  syncConfirmEnabled();
}

function setPriceHint(text, { asError = false } = {}) {
  const hint = el("priceFillHint");
  if (!hint) return;
  hint.textContent = text || "";
  hint.classList.toggle("hidden", !text);
  hint.classList.toggle("hint-error", !!asError && !!text);
}

function setTpSl(tp, sl) {
  el("tpPrice").value = tp != null && tp !== "" ? tp : "";
  el("slPrice").value = sl != null && sl !== "" ? sl : "";
}

async function autofillFromQuote() {
  actionHasPositions = null;
  actionHasOrders = null;
  syncExecuteForAction();
  const account = el("account").value;
  const symbol = el("symbol").value.trim();
  const side = getSide();
  const action = el("action").value;
  if (!account || !symbol) {
    setPriceHint("Chọn account và nhập symbol để lấy giá.");
    return;
  }

  const seq = ++fillSeq;
  setPriceHint("Đang lấy giá thị trường...");
  try {
    const q = new URLSearchParams({ account, symbol, side });
    const data = await apiGet(`/api/quote?${q}`, { useCache: false, timeoutMs: 30000 });
    if (seq !== fillSeq) return;
    const price = data.entry;
    // SL bắt buộc — điền tạm = entry; TP tùy chọn — để trống.
    setTpSl("", price);
    if (action === "pending") {
      const pendingType = el("pendingType").value;
      let tip;
      if (side === "buy" && pendingType === "limit") {
        tip = `Buy Limit: nhập giá chờ < ask ${data.ask}`;
      } else if (side === "buy" && pendingType === "stop") {
        tip = `Buy Stop: nhập giá chờ > ask ${data.ask}`;
      } else if (side === "sell" && pendingType === "limit") {
        tip = `Sell Limit: nhập giá chờ > bid ${data.bid}`;
      } else {
        tip = `Sell Stop: nhập giá chờ < bid ${data.bid}`;
      }
      setPriceHint(
        `Quote ${data.symbol}: bid=${data.bid} ask=${data.ask}. ${tip}. Đã điền SL tạm = entry — hãy chỉnh SL (TP tùy chọn).`,
      );
    } else {
      setPriceHint(
        `Đã điền từ quote ${data.symbol}: bid=${data.bid} ask=${data.ask} → entry ${side}=${price}. Hãy chỉnh SL (bắt buộc); TP tùy chọn.`,
      );
    }
    markApiOk("Đã lấy giá thị trường");
  } catch (err) {
    if (seq !== fillSeq) return;
    setPriceHint(`Không lấy được giá: ${err.message || err}`, { asError: true });
  }
}

async function checkOpenPositionsForAction() {
  const action = el("action").value;
  const account = el("account").value;
  if (!account) {
    actionHasPositions = false;
    syncExecuteForAction();
    setPriceHint("Chọn account để kiểm tra lệnh đang mở.", { asError: true });
    return;
  }

  const seq = ++fillSeq;
  setPriceHint("Đang lấy lệnh mở...");
  setPreviewEnabled(false);
  try {
    const q = new URLSearchParams({ account });
    const data = await apiGet(`/api/positions?${q}`, { useCache: false, timeoutMs: 30000 });
    if (seq !== fillSeq) return;
    const positions = data.positions || [];

    if (!positions.length) {
      actionHasPositions = false;
      if (action === "modify-all") setTpSl("", "");
      setPriceHint(
        `Không có lệnh đang mở — ${action} không làm gì được. Chọn status/open hoặc mở lệnh trước.`,
        { asError: true },
      );
      markApiOk(`Không có lệnh mở — ${action} vô nghĩa`);
      syncExecuteForAction();
      return;
    }

    actionHasPositions = true;

    if (action === "modify-all") {
      const withLevels = positions.find((p) => p.tp != null || p.sl != null);
      const pos = withLevels || positions[0];
      setTpSl(pos.tp != null ? pos.tp : "", pos.sl != null ? pos.sl : "");
      setPriceHint(
        `Đã điền từ lệnh #${pos.ticket} (${pos.side} ${pos.symbol}): SL=${pos.sl ?? "chưa đặt"} | TP=${pos.tp ?? "chưa đặt"} | mở=${pos.price_open}`
        + (positions.length > 1 ? ` — tổng ${positions.length} lệnh mở` : "")
        + (pos.sl == null ? " — cần nhập Stop loss trước khi sửa" : ""),
      );
      markApiOk("Đã lấy SL/TP từ lệnh mở");
    } else {
      // close-all
      const summary = positions
        .slice(0, 3)
        .map((p) => `#${p.ticket} ${p.side} ${p.symbol} ${p.volume}lot`)
        .join("; ");
      const more = positions.length > 3 ? ` … (+${positions.length - 3})` : "";
      setPriceHint(`Có ${positions.length} lệnh mở sẽ bị đóng: ${summary}${more}`);
      markApiOk(`Có ${positions.length} lệnh mở`);
    }
    syncExecuteForAction();
  } catch (err) {
    if (seq !== fillSeq) return;
    actionHasPositions = false;
    setPriceHint(`Không lấy được lệnh mở: ${err.message || err}`, { asError: true });
    syncExecuteForAction();
  }
}

async function checkPendingOrdersForAction() {
  const account = el("account").value;
  if (!account) {
    actionHasOrders = false;
    syncExecuteForAction();
    setPriceHint("Chọn account để kiểm tra lệnh chờ.", { asError: true });
    return;
  }

  const seq = ++fillSeq;
  setPriceHint("Đang lấy lệnh chờ...");
  setPreviewEnabled(false);
  try {
    const q = new URLSearchParams({ account });
    const data = await apiGet(`/api/orders?${q}`, { useCache: false, timeoutMs: 30000 });
    if (seq !== fillSeq) return;
    const orders = data.orders || [];

    if (!orders.length) {
      actionHasOrders = false;
      setPriceHint(
        "Không có lệnh chờ — cancel-pending không làm gì được. Chọn pending để đặt lệnh chờ trước.",
        { asError: true },
      );
      markApiOk("Không có lệnh chờ");
      syncExecuteForAction();
      return;
    }

    actionHasOrders = true;
    const summary = orders
      .slice(0, 3)
      .map((o) => `#${o.ticket} ${o.type} ${o.symbol} @ ${o.price}`)
      .join("; ");
    const more = orders.length > 3 ? ` … (+${orders.length - 3})` : "";
    setPriceHint(`Có ${orders.length} lệnh chờ sẽ bị hủy: ${summary}${more}`);
    markApiOk(`Có ${orders.length} lệnh chờ`);
    syncExecuteForAction();
  } catch (err) {
    if (seq !== fillSeq) return;
    actionHasOrders = false;
    setPriceHint(`Không lấy được lệnh chờ: ${err.message || err}`, { asError: true });
    syncExecuteForAction();
  }
}

async function autofillTpSl() {
  const action = el("action").value;
  if (actionUsesQuote(action)) {
    await withBusy(() => autofillFromQuote(), "Đang lấy giá...", { block: false });
  } else if (actionNeedsOpenPositions(action)) {
    await withBusy(() => checkOpenPositionsForAction(), "Đang lấy lệnh mở...", { block: false });
  } else if (actionNeedsPendingOrders(action)) {
    await withBusy(() => checkPendingOrdersForAction(), "Đang lấy lệnh chờ...", { block: false });
  } else {
    actionHasPositions = null;
    actionHasOrders = null;
    setPriceHint("");
    syncExecuteForAction();
  }
}

async function loadAccounts({ silent = false, useCache = true } = {}) {
  const run = async () => {
    const data = await apiGet("/api/accounts", { useCache });
    lastAccounts = data.accounts || [];
    renderAccounts(lastAccounts);
    markApiOk();
  };
  try {
    if (silent) await run();
    else await withBusy(run, "Đang tải accounts...", { block: false });
  } catch (err) {
    markApiError(err);
  }
}

async function reloadAccounts() {
  try {
    await withBusy(async () => {
      const data = await apiPost("/api/reload-accounts");
      lastAccounts = data.accounts || [];
      renderAccounts(lastAccounts);
      markApiOk("Đã nạp lại accounts.xml");
    }, "Đang nạp lại accounts...");
    await autofillTpSl();
  } catch (err) {
    alert(`Lỗi tải lại account: ${err.message}`);
  }
}

function updateParamsVisibility() {
  const action = el("action").value;
  const fields = document.querySelectorAll("[data-actions]");
  let visibleCount = 0;

  fields.forEach((field) => {
    const allowed = field.dataset.actions.split(",");
    const visible = allowed.includes(action);
    field.classList.toggle("hidden", !visible);
    if (visible && !field.classList.contains("hint")) visibleCount += 1;
  });

  el("paramsEmptyHint").classList.toggle("hidden", visibleCount > 0);
}

function buildPayload(noAsk) {
  const action = el("action").value;
  const isVisible = (fieldId) => {
    const field = el(fieldId).closest("[data-actions]");
    return field ? field.dataset.actions.split(",").includes(action) : true;
  };

  return {
    account: el("account").value,
    action,
    symbol: isVisible("symbol") ? el("symbol").value : undefined,
    side: isVisible("side") ? getSide() : undefined,
    pending_type: isVisible("pendingType") ? el("pendingType").value : undefined,
    price: isVisible("price") ? el("price").value : undefined,
    lot: isVisible("lot") ? resolveLot() : undefined,
    tp_price: isVisible("tpPrice") ? el("tpPrice").value : "",
    sl_price: isVisible("slPrice") ? el("slPrice").value : "",
    comment: isVisible("comment") ? el("comment").value : undefined,
    copy: isVisible("copy") && el("copy").value ? el("copy").value : undefined,
    no_ask: noAsk,
  };
}

async function submitAction(noAsk, triggerBtn) {
  if (!lastAccounts.length) {
    await loadAccounts({ useCache: false });
  } else {
    loadAccounts({ silent: true, useCache: true });
  }
  if (!el("account").value) {
    alert("Chưa có account nào để chọn.");
    return;
  }
  if (actionNeedsOpenPositions() && actionHasPositions !== true) {
    const action = el("action").value;
    alert(`Không có lệnh đang mở — ${action} không làm gì được. Hãy chọn status hoặc mở lệnh trước.`);
    return;
  }
  if (actionNeedsPendingOrders() && actionHasOrders !== true) {
    alert("Không có lệnh chờ — cancel-pending không làm gì được. Hãy đặt lệnh chờ trước.");
    return;
  }
  if (el("action").value === "pending" && !el("price").value) {
    alert("Lệnh pending cần nhập Giá chờ.");
    return;
  }
  const action = el("action").value;
  if (action === "open" || action === "pending" || action === "modify-all") {
    const slRaw = el("slPrice").value.trim();
    const sl = Number(slRaw);
    if (!slRaw || !Number.isFinite(sl) || sl <= 0) {
      alert("Stop loss là bắt buộc — hãy nhập mức giá SL hợp lệ (> 0).");
      el("slPrice").focus();
      return;
    }
  }
  if (noAsk) {
    if (!payloadsMatchPreview()) {
      alert("Cần bấm Xem trước với đúng thông số hiện tại trước khi gửi lệnh thật.");
      return;
    }
    const ok = await showConfirmModal(
      "Bạn chắc chắn muốn GỬI LỆNH THẬT (hoặc thực thi thật) không?",
    );
    if (!ok) return;
  }

  const output = el("output");
  triggerBtn.disabled = true;
  try {
    const data = await withBusy(
      () => apiPost("/api/action", buildPayload(noAsk), { timeoutMs: 60000 }),
      noAsk ? "Đang gửi lệnh thật..." : "Đang xem trước...",
      { block: true },
    );
    output.textContent = data.output || "(không có output)";
    if (noAsk) {
      invalidatePreview();
    } else {
      markPreviewOk();
    }
    if (actionNeedsOpenPositions()) {
      await checkOpenPositionsForAction();
    } else if (actionNeedsPendingOrders()) {
      await checkPendingOrdersForAction();
    }
  } catch (err) {
    output.textContent = `Lỗi: ${err.message}`;
    if (!noAsk) invalidatePreview();
  } finally {
    syncExecuteForAction();
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  updateParamsVisibility();
  await loadAccounts({ useCache: false });
  syncConfirmEnabled();

  el("themeToggle").addEventListener("click", toggleTheme);
  el("action").addEventListener("change", () => {
    invalidatePreview();
    updateParamsVisibility();
    autofillTpSl();
  });
  el("symbol").addEventListener("change", () => {
    invalidatePreview();
    if (actionUsesQuote()) autofillTpSl();
  });
  el("symbol").addEventListener("blur", () => {
    invalidatePreview();
    if (actionUsesQuote()) autofillTpSl();
  });
  el("pendingType").addEventListener("change", () => {
    invalidatePreview();
    if (el("action").value === "pending") autofillTpSl();
  });
  ["price", "lot", "tpPrice", "slPrice", "comment", "copy"].forEach((id) => {
    const node = el(id);
    if (!node) return;
    node.addEventListener("input", invalidatePreview);
    node.addEventListener("change", invalidatePreview);
  });
  el("account").addEventListener("change", invalidatePreview);
  document.querySelectorAll("#sideToggle [data-side]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = btn.dataset.side;
      if (next === getSide()) return;
      setSide(next);
      invalidatePreview();
      if (actionUsesQuote()) autofillTpSl();
    });
  });
  el("btnReloadAccounts").addEventListener("click", reloadAccounts);
  el("btnPreview").addEventListener("click", (e) => submitAction(false, e.target));
  el("btnConfirm").addEventListener("click", (e) => submitAction(true, e.target));

  onVisibleRefresh(() => loadAccounts({ silent: true, useCache: true }), { minIntervalMs: 20000 });
});
