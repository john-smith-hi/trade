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
  el("accountInfo").textContent =
    `login: ${acc.login} | server: ${acc.server} | suffix: "${acc.suffix}" | multi: ${acc.multi} | max_loss: ${maxLoss} | ${autoCopy}`;
}

let lastAccounts = [];
let fillSeq = 0;
/** null = không áp dụng; false = close-all/modify-all nhưng không có lệnh mở */
let actionHasPositions = null;

function actionNeedsOpenPositions(action = el("action").value) {
  return action === "modify-all" || action === "close-all";
}

function setExecuteEnabled(enabled) {
  const preview = el("btnPreview");
  const confirm = el("btnConfirm");
  if (preview) preview.disabled = !enabled;
  if (confirm) confirm.disabled = !enabled;
}

function syncExecuteForAction() {
  if (actionNeedsOpenPositions()) {
    setExecuteEnabled(actionHasPositions === true);
  } else {
    actionHasPositions = null;
    setExecuteEnabled(true);
  }
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
  syncExecuteForAction();
  const account = el("account").value;
  const symbol = el("symbol").value.trim();
  const side = el("side").value;
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
    setTpSl(price, price);
    setPriceHint(
      `Đã điền từ quote ${data.symbol}: bid=${data.bid} ask=${data.ask} → entry ${side}=${price}. Hãy chỉnh TP/SL cho đúng hướng.`,
    );
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
  setExecuteEnabled(false);
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
        `Đã điền từ lệnh #${pos.ticket} (${pos.side} ${pos.symbol}): TP=${pos.tp ?? "chưa đặt"} | SL=${pos.sl ?? "chưa đặt"} | mở=${pos.price_open}`
        + (positions.length > 1 ? ` — tổng ${positions.length} lệnh mở` : ""),
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

async function autofillTpSl() {
  const action = el("action").value;
  if (action === "open") {
    await withBusy(() => autofillFromQuote(), "Đang lấy giá...", { block: false });
  } else if (actionNeedsOpenPositions(action)) {
    await withBusy(() => checkOpenPositionsForAction(), "Đang lấy lệnh mở...", { block: false });
  } else {
    actionHasPositions = null;
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
    side: isVisible("side") ? el("side").value : undefined,
    lot: isVisible("lot") ? el("lot").value : undefined,
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
  if (noAsk) {
    const ok = await showConfirmModal(
      "Bạn chắc chắn muốn GỬI LỆNH THẬT (hoặc thực thi thật) không? Hành động này không thể xem trước lại.",
    );
    if (!ok) return;
  }

  const output = el("output");
  triggerBtn.disabled = true;
  try {
    const data = await withBusy(
      () => apiPost("/api/action", buildPayload(noAsk), { timeoutMs: 60000 }),
      "Đang gửi lệnh / xem trước...",
      { block: true },
    );
    output.textContent = data.output || "(không có output)";
    if (actionNeedsOpenPositions()) {
      await checkOpenPositionsForAction();
    }
  } catch (err) {
    output.textContent = `Lỗi: ${err.message}`;
  } finally {
    syncExecuteForAction();
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  updateParamsVisibility();
  await loadAccounts({ useCache: false });

  el("themeToggle").addEventListener("click", toggleTheme);
  el("action").addEventListener("change", () => {
    updateParamsVisibility();
    autofillTpSl();
  });
  el("symbol").addEventListener("change", () => {
    if (el("action").value === "open") autofillTpSl();
  });
  el("symbol").addEventListener("blur", () => {
    if (el("action").value === "open") autofillTpSl();
  });
  el("side").addEventListener("change", () => {
    if (el("action").value === "open") autofillTpSl();
  });
  el("btnReloadAccounts").addEventListener("click", reloadAccounts);
  el("btnPreview").addEventListener("click", (e) => submitAction(false, e.target));
  el("btnConfirm").addEventListener("click", (e) => submitAction(true, e.target));

  onVisibleRefresh(() => loadAccounts({ silent: true, useCache: true }), { minIntervalMs: 20000 });
});
