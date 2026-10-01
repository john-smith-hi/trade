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
    renderOpenPositionWarn([]);
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
    renderOpenPositionWarn([]);
    autofillTpSl();
    if (!actionNeedsOpenPositions()) refreshOpenPositionWarn();
  };
}

function fmtPrice(n) {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  if (Number.isInteger(x)) return String(x);
  return x.toFixed(5).replace(/0+$/, "").replace(/\.$/, "");
}

function fmtLevel(n) {
  const x = Number(n);
  if (!Number.isFinite(x) || x <= 0) return "chưa đặt";
  return fmtPrice(x);
}

function fmtPnl(n) {
  const x = Number(n);
  if (!Number.isFinite(x)) return "0.00";
  const abs = Math.abs(x).toFixed(2);
  if (x > 0) return `+${abs}`;
  if (x < 0) return `-${abs}`;
  return "0.00";
}

function fmtVol(n) {
  const x = Number(n);
  if (!Number.isFinite(x)) return String(n ?? "");
  return String(x);
}

function positionHeadline(p) {
  const side = String(p.side || "").toUpperCase();
  return `${side} ${p.symbol || "?"} ${fmtVol(p.volume)} lot`;
}

function positionLevels(p) {
  return `Giá mở cửa ${fmtPrice(p.price_open)} · Stop loss ${fmtLevel(p.sl)} · Take profit ${fmtLevel(p.tp)} · Lời/Lỗ ${fmtPnl(p.profit)}`;
}

function renderOpenPositionWarn(positions) {
  const box = el("openPositionWarn");
  const line1 = el("openPositionWarnL1");
  const line2 = el("openPositionWarnL2");
  if (!box || !line1 || !line2) return;
  const list = Array.isArray(positions) ? positions : [];
  if (!list.length) {
    box.classList.add("hidden");
    line1.textContent = "";
    line2.textContent = "";
    return;
  }
  if (list.length === 1) {
    line1.textContent = `Có 1 lệnh đang chạy ${positionHeadline(list[0])}`;
    line2.textContent = positionLevels(list[0]);
  } else {
    const total = list.reduce((sum, p) => sum + (Number(p.profit) || 0), 0);
    line1.textContent = `Có ${list.length} lệnh đang chạy: ${list.map(positionHeadline).join(", ")}`;
    line2.textContent = `${list.map(positionLevels).join(" | ")} · Tổng ${fmtPnl(total)}`;
  }
  box.classList.remove("hidden");
}

let warnSeq = 0;

async function refreshOpenPositionWarn({ positions = null } = {}) {
  if (Array.isArray(positions)) {
    renderOpenPositionWarn(positions);
    return;
  }
  const account = el("account").value;
  if (!account) {
    renderOpenPositionWarn([]);
    return;
  }
  const seq = ++warnSeq;
  try {
    const q = new URLSearchParams({ account });
    const data = await apiGet(`/api/positions?${q}`, { useCache: false, timeoutMs: 30000 });
    if (seq !== warnSeq) return;
    const list = data.positions || [];
    lastFetchedPositions = list;
    renderOpenPositionWarn(list);
  } catch {
    if (seq !== warnSeq) return;
  }
}

function updateAccountInfo(accounts) {
  const acc = accounts.find((a) => a.name === el("account").value);
  if (!acc) {
    el("accountInfo").textContent = "";
    renderOpenPositionWarn([]);
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
/** Account đã gắn default_lot vào ô Lot — tránh ghi đè khi refresh danh sách (vd. Xem trước). */
let lotBoundToAccount = null;
let fillSeq = 0;
/** Quote gần nhất cho open-2-side — hint tính SL/TP theo khoảng cách. */
let lastTwoSideQuote = null;
/** null = không áp dụng; false = action cần lệnh nhưng không có */
let actionHasPositions = null;
let actionHasOrders = null;
let lastFetchedPositions = [];
let previewValid = false;
let previewSnapshot = null;
/** true khi JS đang ghi form — không được coi là người dùng sửa thông số. */
let fillingForm = false;

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

function applyDefaultLot({ force = false } = {}) {
  const lotInput = el("lot");
  if (!lotInput) return;
  const accountName = el("account").value;
  const lot = accountDefaultLot(accountName);
  lotInput.placeholder = "default_lot";
  // Chỉ điền mặc định khi đổi account (hoặc force). Refresh accounts sau
  // Xem trước / tab visible không được đè số lot người dùng đã nhập.
  if (!force && lotBoundToAccount === accountName) return;
  lotInput.value = String(lot);
  lotBoundToAccount = accountName;
}

function actionNeedsOpenPositions(action = el("action").value) {
  return action === "modify-all" || action === "close" || action === "close-all" || action === "modify-all-if";
}

function actionIsClose(action = el("action").value) {
  return action === "close";
}

function normalizeSymbol(sym) {
  return String(sym || "").trim().toUpperCase().replace(/M$/, "");
}

function positionsForClose(positions) {
  const wantSymbol = normalizeSymbol(el("symbol").value);
  const wantSide = getSide();
  return (positions || []).filter((p) => {
    if (p.side !== wantSide) return false;
    if (!wantSymbol) return true;
    return normalizeSymbol(p.symbol) === wantSymbol;
  });
}

function actionNeedsPendingOrders(action = el("action").value) {
  return action === "cancel-pending";
}

function actionUsesQuote(action = el("action").value) {
  return action === "open" || action === "pending";
}

function actionIsTwoSide(action = el("action").value) {
  return action === "open-2-side";
}

function actionIsModifyIf(action = el("action").value) {
  return action === "modify-all-if";
}

function actionCancelsModifyIf(action = el("action").value) {
  return action === "cancel-modify-if";
}

function formatCloseHint(positions) {
  const side = getSide();
  const symbol = el("symbol").value.trim() || "XAUUSD";
  const matched = positionsForClose(positions);
  const others = (positions || []).filter((p) => !matched.includes(p));
  if (!matched.length) {
    const otherSameSymbol = others.filter((p) => normalizeSymbol(p.symbol) === normalizeSymbol(symbol));
    if (otherSameSymbol.length) {
      const summary = otherSameSymbol
        .map((p) => `#${p.ticket} ${p.side.toUpperCase()} ${p.volume}lot`)
        .join("; ");
      return {
        ok: false,
        text: `Không có lệnh ${side.toUpperCase()} ${symbol} đang mở. Có lệnh khác cùng symbol: ${summary} — đổi Side nếu muốn đóng những lệnh đó.`,
      };
    }
    return {
      ok: false,
      text: `Không có lệnh ${side.toUpperCase()} ${symbol} đang mở để đóng một phần.`,
    };
  }

  const totalVol = matched.reduce((sum, p) => sum + Number(p.volume || 0), 0);
  const lot = resolveLot();
  const willClose = Math.min(lot, totalVol);
  const remain = Math.max(0, Math.round((totalVol - willClose) * 1e8) / 1e8);
  const summary = matched
    .slice(0, 3)
    .map((p) => `#${p.ticket} ${p.side} ${p.symbol} ${p.volume}lot`)
    .join("; ");
  const more = matched.length > 3 ? ` … (+${matched.length - 3})` : "";
  const remainText = remain > 0 ? `còn ~${remain}` : "hết vị thế khớp";
  const over = lot > totalVol + 1e-12 ? ` Lot nhập ${lot} > tổng ${totalVol} — sẽ đóng hết phần khớp.` : "";
  return {
    ok: true,
    text: `Sẽ đóng ${willClose} lot ${side.toUpperCase()} ${symbol} (${remainText}). Khớp: ${summary}${more}.${over} Copy sẽ nhân multi.`,
  };
}

function invalidatePreview() {
  if (fillingForm) return;
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
  fillingForm = true;
  try {
    el("tpPrice").value = tp != null && tp !== "" ? tp : "";
    el("slPrice").value = sl != null && sl !== "" ? sl : "";
  } finally {
    fillingForm = false;
  }
}

function formatTwoSideHint(quote) {
  const bid = Number(quote.bid);
  const ask = Number(quote.ask);
  const base = `Giá ${quote.symbol || ""}: bid=${quote.bid} ask=${quote.ask}. SL/TP là khoảng cách so với giá khớp (BUY = ask, SELL = bid), không phải mức giá. Lot áp dụng cho từng lệnh.`;
  const slRaw = el("slPrice").value.trim();
  const tpRaw = el("tpPrice").value.trim();
  const sl = Number(slRaw);
  const tp = tpRaw === "" ? null : Number(tpRaw);
  if (!slRaw) {
    return {
      text: `${base} Nhập SL (ví dụ 10) và TP (ví dụ 50, có thể để trống).`,
      asError: false,
    };
  }
  if (!Number.isFinite(sl) || sl <= 0 || !Number.isFinite(bid) || !Number.isFinite(ask)) {
    return { text: `${base} SL phải là số > 0.`, asError: true };
  }
  if (tp != null && (!Number.isFinite(tp) || tp <= 0)) {
    return { text: `${base} TP phải là số > 0 hoặc để trống.`, asError: true };
  }
  const buySl = ask - sl;
  const sellSl = bid + sl;
  const buyTp = tp == null ? null : ask + tp;
  const sellTp = tp == null ? null : bid - tp;
  const buyTpText = buyTp == null ? "không TP" : `TP ${fmtPrice(buyTp)}`;
  const sellTpText = sellTp == null ? "không TP" : `TP ${fmtPrice(sellTp)}`;
  const bad = buySl <= 0 || sellSl <= 0 || (buyTp != null && buyTp <= 0) || (sellTp != null && sellTp <= 0);
  return {
    text: `${base} SL ${fmtPrice(sl)}${tp == null ? "" : `, TP ${fmtPrice(tp)}`} → BUY ${fmtPrice(ask)} SL ${fmtPrice(buySl)} ${buyTpText} | SELL ${fmtPrice(bid)} SL ${fmtPrice(sellSl)} ${sellTpText}`,
    asError: bad,
  };
}

function updateTwoSideHint() {
  if (!actionIsTwoSide() || !lastTwoSideQuote) return;
  const hint = formatTwoSideHint(lastTwoSideQuote);
  setPriceHint(hint.text, { asError: hint.asError });
}

async function autofillTwoSide() {
  actionHasPositions = null;
  actionHasOrders = null;
  syncExecuteForAction();
  const account = el("account").value;
  const symbol = el("symbol").value.trim();
  if (!account || !symbol) {
    lastTwoSideQuote = null;
    setPriceHint("Chọn account và nhập symbol để lấy giá.");
    return;
  }

  const seq = ++fillSeq;
  setPriceHint("Đang lấy giá thị trường...");
  try {
    const q = new URLSearchParams({ account, symbol, side: "buy" });
    const data = await apiGet(`/api/quote?${q}`, { useCache: false, timeoutMs: 30000 });
    if (seq !== fillSeq) return;
    lastTwoSideQuote = data;
    const hint = formatTwoSideHint(data);
    setPriceHint(hint.text, { asError: hint.asError });
    markApiOk("Đã lấy giá cho open-2-side");
  } catch (err) {
    if (seq !== fillSeq) return;
    lastTwoSideQuote = null;
    setPriceHint(`Không lấy được giá: ${err.message || err}`, { asError: true });
  }
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
      setPriceHint(
        `Quote ${data.symbol}: bid=${data.bid} ask=${data.ask}. Nhập giá chờ bất kỳ — Limit/Stop sẽ tự chọn (BUY dưới ask = Limit, trên ask = Stop; SELL ngược lại). Đã điền SL tạm = entry — hãy chỉnh SL (TP tùy chọn).`,
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

async function checkOpenPositionsForAction({ fillLevels = false } = {}) {
  const action = el("action").value;
  const account = el("account").value;
  if (!account) {
    actionHasPositions = false;
    syncExecuteForAction();
    setPriceHint("Chọn account để kiểm tra lệnh đang mở.", { asError: true });
    renderOpenPositionWarn([]);
    return;
  }

  const seq = ++fillSeq;
  setPriceHint("Đang lấy lệnh mở...");
  if (fillLevels) setPreviewEnabled(false);
  try {
    const q = new URLSearchParams({ account });
    const data = await apiGet(`/api/positions?${q}`, { useCache: false, timeoutMs: 30000 });
    if (seq !== fillSeq) return;
    const positions = data.positions || [];
    lastFetchedPositions = positions;
    warnSeq += 1;
    renderOpenPositionWarn(positions);

    if (!positions.length) {
      actionHasPositions = false;
      if (fillLevels && (action === "modify-all" || action === "modify-all-if")) setTpSl("", "");
      setPriceHint(
        `Không có lệnh đang mở — ${action} không làm gì được. Chọn status/open hoặc mở lệnh trước.`,
        { asError: true },
      );
      markApiOk(`Không có lệnh mở — ${action} vô nghĩa`);
      syncExecuteForAction();
      return;
    }

    if (action === "close") {
      const hint = formatCloseHint(positions);
      actionHasPositions = hint.ok;
      setPriceHint(hint.text, { asError: !hint.ok });
      markApiOk(hint.ok ? "Có lệnh khớp để đóng một phần" : "Không có lệnh khớp để close");
      syncExecuteForAction();
      return;
    }

    actionHasPositions = true;

    if (action === "modify-all" || action === "modify-all-if") {
      const withLevels = positions.find((p) => p.tp != null || p.sl != null);
      const pos = withLevels || positions[0];
      if (fillLevels) {
        setTpSl(pos.tp != null ? pos.tp : "", pos.sl != null ? pos.sl : "");
      }
      const source = fillLevels ? "Đã điền từ" : "Tham chiếu";
      setPriceHint(
        `${source} lệnh #${pos.ticket} (${pos.side} ${pos.symbol}): SL=${pos.sl ?? "chưa đặt"} | TP=${pos.tp ?? "chưa đặt"} | mở=${pos.price_open}`
        + (positions.length > 1 ? ` — tổng ${positions.length} lệnh mở` : "")
        + (fillLevels && pos.sl == null ? " — cần nhập Stop loss trước khi sửa" : "")
        + (!fillLevels ? " — SL/TP trên form sẽ áp dụng cho tất cả lệnh" : ""),
      );
      markApiOk(fillLevels ? "Đã lấy SL/TP từ lệnh mở" : `Có ${positions.length} lệnh mở`);
      if (action === "modify-all-if") {
        await appendModifyIfQuoteHint(account, positions.length);
      }
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
    // Refresh sau xem trước thất bại không được coi là "không có lệnh" — giữ trạng thái cũ.
    if (fillLevels) actionHasPositions = false;
    setPriceHint(`Không lấy được lệnh mở: ${err.message || err}`, { asError: true });
    syncExecuteForAction();
  }
}

async function appendModifyIfQuoteHint(account, posCount) {
  const hint = el("priceFillHint");
  const base = hint ? hint.textContent : "";
  const symbol = (el("symbol").value || "XAUUSD").trim();
  try {
    const q = new URLSearchParams({ account, symbol, side: getSide() });
    const quote = await apiGet(`/api/quote?${q}`, { useCache: false, timeoutMs: 30000 });
    const jobsData = await apiGet(`/api/modify-if?${new URLSearchParams({ account })}`, { useCache: false });
    const jobs = jobsData.jobs || [];
    const jobLine = jobs.length
      ? ` Job đang chờ: ${jobs.map((j) => `${j.symbol} ${j.zoneLow}–${j.zoneHigh} SL=${j.slPrice}`).join("; ")}.`
      : " Chưa có job modify-all-if.";
    setPriceHint(
      `${base} Quote ${quote.symbol}: bid=${quote.bid} ask=${quote.ask}. `
      + `Nhập vùng kích hoạt (một mức cũng được). Khi giá đi vào vùng, watcher (~30s) sẽ sửa SL/TP ${posCount} lệnh.`
      + jobLine,
    );
  } catch (err) {
    setPriceHint(`${base} (không lấy được giá/job: ${err.message || err})`);
  }
}

async function checkModifyIfJobsForAction() {
  const account = el("account").value;
  if (!account) {
    setPriceHint("Chọn account để xem job modify-all-if.", { asError: true });
    return;
  }
  const seq = ++fillSeq;
  setPriceHint("Đang lấy job modify-all-if...");
  try {
    const data = await apiGet(`/api/modify-if?${new URLSearchParams({ account })}`, { useCache: false });
    if (seq !== fillSeq) return;
    const jobs = data.jobs || [];
    if (!jobs.length) {
      setPriceHint("Không có job modify-all-if đang chờ.");
      markApiOk("Không có job modify-all-if");
      return;
    }
    const summary = jobs.map((j) => `${j.symbol} ${j.zoneLow}–${j.zoneHigh} SL=${j.slPrice}`).join("; ");
    setPriceHint(`Sẽ hủy ${jobs.length} job: ${summary}`);
    markApiOk(`Có ${jobs.length} job modify-all-if`);
  } catch (err) {
    if (seq !== fillSeq) return;
    setPriceHint(`Không lấy được job: ${err.message || err}`, { asError: true });
  }
}

async function checkPendingOrdersForAction({ lockButtons = false } = {}) {
  const account = el("account").value;
  if (!account) {
    actionHasOrders = false;
    syncExecuteForAction();
    setPriceHint("Chọn account để kiểm tra lệnh chờ.", { asError: true });
    return;
  }

  const seq = ++fillSeq;
  setPriceHint("Đang lấy lệnh chờ...");
  if (lockButtons) setPreviewEnabled(false);
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
    if (lockButtons) actionHasOrders = false;
    setPriceHint(`Không lấy được lệnh chờ: ${err.message || err}`, { asError: true });
    syncExecuteForAction();
  }
}

async function autofillTpSl() {
  const action = el("action").value;
  if (actionIsTwoSide(action)) {
    await withBusy(() => autofillTwoSide(), "Đang lấy giá...", { block: false });
  } else if (actionUsesQuote(action)) {
    await withBusy(() => autofillFromQuote(), "Đang lấy giá...", { block: false });
  } else if (actionNeedsOpenPositions(action)) {
    await withBusy(() => checkOpenPositionsForAction({ fillLevels: true }), "Đang lấy lệnh mở...", { block: false });
  } else if (actionNeedsPendingOrders(action)) {
    await withBusy(() => checkPendingOrdersForAction({ lockButtons: true }), "Đang lấy lệnh chờ...", { block: false });
  } else if (actionCancelsModifyIf(action)) {
    await withBusy(() => checkModifyIfJobsForAction(), "Đang lấy job modify-all-if...", { block: false });
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
    if (!actionNeedsOpenPositions()) await refreshOpenPositionWarn();
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

  const lotLabel = document.querySelector('label[for="lot"]');
  if (lotLabel) {
    lotLabel.textContent = action === "close" ? "Lot muốn đóng" : actionIsTwoSide(action) ? "Lot mỗi lệnh" : "Lot";
  }
  const slLabel = document.querySelector('label[for="slPrice"]');
  const tpLabel = document.querySelector('label[for="tpPrice"]');
  const slInput = el("slPrice");
  const tpInput = el("tpPrice");
  if (slLabel && tpLabel && slInput && tpInput) {
    if (actionIsTwoSide(action)) {
      slLabel.textContent = "SL cách giá *";
      tpLabel.textContent = "TP cách giá";
      slInput.placeholder = "vd 10 — không phải mức giá";
      tpInput.placeholder = "vd 50 — để trống nếu không đặt";
    } else {
      slLabel.textContent = "SL price *";
      tpLabel.textContent = "TP price";
      slInput.placeholder = "bắt buộc";
      tpInput.placeholder = "để trống nếu không đặt";
    }
  }
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
    zone_low: isVisible("zoneLow") ? el("zoneLow").value : undefined,
    zone_high: isVisible("zoneHigh") ? el("zoneHigh").value : undefined,
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
  if (el("action").value === "modify-all-if") {
    const low = el("zoneLow").value.trim();
    const high = el("zoneHigh").value.trim();
    if (!low && !high) {
      alert("modify-all-if cần nhập vùng kích hoạt (một mức cũng được).");
      el("zoneLow").focus();
      return;
    }
  }
  const action = el("action").value;
  if (action === "open" || action === "open-2-side" || action === "pending" || action === "modify-all" || action === "modify-all-if") {
    const slRaw = el("slPrice").value.trim();
    const sl = Number(slRaw);
    if (!slRaw || !Number.isFinite(sl) || sl <= 0) {
      alert(action === "open-2-side"
        ? "Stop loss là khoảng cách từ giá hiện tại (ví dụ 10), không phải mức giá."
        : "Stop loss là bắt buộc — hãy nhập mức giá SL hợp lệ (> 0).");
      el("slPrice").focus();
      return;
    }
  }
  if (action === "open-2-side") {
    const tpRaw = el("tpPrice").value.trim();
    if (tpRaw) {
      const tp = Number(tpRaw);
      if (!Number.isFinite(tp) || tp <= 0) {
        alert("Take profit là khoảng cách > 0 (ví dụ 50), hoặc để trống.");
        el("tpPrice").focus();
        return;
      }
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
    // Chỉ làm mới trạng thái lệnh mở/chờ. Không điền lại quote/TP/SL —
    // ghi đè form sẽ làm lệch snapshot → mất nút xác nhận và kéo giá cũ vào.
    try {
      if (actionNeedsOpenPositions()) {
        await checkOpenPositionsForAction({ fillLevels: false });
      } else if (actionNeedsPendingOrders()) {
        await checkPendingOrdersForAction({ lockButtons: false });
        await refreshOpenPositionWarn();
      } else {
        await refreshOpenPositionWarn();
      }
    } catch (refreshErr) {
      setPriceHint(`Không làm mới danh sách lệnh: ${refreshErr.message || refreshErr}`, { asError: true });
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
  refreshOpenPositionWarn();

  el("themeToggle").addEventListener("click", toggleTheme);
  el("action").addEventListener("change", () => {
    invalidatePreview();
    if (actionIsTwoSide()) setTpSl("", "");
    updateParamsVisibility();
    autofillTpSl();
  });
  el("symbol").addEventListener("change", () => {
    invalidatePreview();
    if (actionUsesQuote() || actionIsModifyIf() || actionIsClose() || actionIsTwoSide()) autofillTpSl();
  });
  el("symbol").addEventListener("blur", () => {
    invalidatePreview();
    if (actionUsesQuote() || actionIsModifyIf() || actionIsClose() || actionIsTwoSide()) autofillTpSl();
  });
  el("pendingType").addEventListener("change", () => {
    invalidatePreview();
    if (el("action").value === "pending") autofillTpSl();
  });
  ["price", "lot", "tpPrice", "slPrice", "comment", "copy", "zoneLow", "zoneHigh"].forEach((id) => {
    const node = el(id);
    if (!node) return;
    node.addEventListener("input", () => {
      invalidatePreview();
      if ((id === "slPrice" || id === "tpPrice") && actionIsTwoSide()) updateTwoSideHint();
      if (id === "lot" && actionIsClose() && lastFetchedPositions.length) {
        const hint = formatCloseHint(lastFetchedPositions);
        actionHasPositions = hint.ok;
        setPriceHint(hint.text, { asError: !hint.ok });
        syncExecuteForAction();
      }
    });
    node.addEventListener("change", invalidatePreview);
  });
  el("account").addEventListener("change", invalidatePreview);
  document.querySelectorAll("#sideToggle [data-side]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = btn.dataset.side;
      if (next === getSide()) return;
      setSide(next);
      invalidatePreview();
      if (actionUsesQuote() || actionIsClose()) autofillTpSl();
    });
  });
  el("btnReloadAccounts").addEventListener("click", reloadAccounts);
  el("btnPreview").addEventListener("click", (e) => submitAction(false, e.target));
  el("btnConfirm").addEventListener("click", (e) => submitAction(true, e.target));

  onVisibleRefresh(() => {
    loadAccounts({ silent: true, useCache: true });
    refreshOpenPositionWarn();
  }, { minIntervalMs: 20000 });
});
