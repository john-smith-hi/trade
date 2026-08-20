const {
  el,
  initTheme,
  toggleTheme,
  apiGet,
  apiPost,
  withBusy,
  markApiOk,
  markApiError,
  loadPriceAlerts,
  savePriceAlerts,
  getPriceAlertSchedule,
} = window.MT5;

const ACCOUNT_KEY = "setup-quote-account";
const DEFAULT_QUOTE_ACCOUNT = "real";

function uid() {
  return `a${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

function setQuoteHint(text, asError = false) {
  const hint = el("quoteHint");
  hint.textContent = text || "";
  hint.classList.toggle("hint-error", !!asError && !!text);
}

function statusLabel(alert) {
  if (alert.fired) return { text: "Đã chạm", cls: "fired" };
  if (!alert.enabled) return { text: "Tắt", cls: "waiting" };
  if (!alert.primed) return { text: "Đang chờ giá", cls: "waiting" };
  if (alert.inside) return { text: "Đang trong vùng", cls: "armed" };
  return { text: "Đang theo dõi", cls: "armed" };
}

function formatCountdown(ms) {
  if (ms <= 0) return "0:00";
  const total = Math.ceil(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function nextPollLabel() {
  const schedule = getPriceAlertSchedule ? getPriceAlertSchedule() : null;
  if (!schedule) return "--";
  if (schedule.busy) return "đang lấy...";
  if (!schedule.nextAt) return "--";
  const remain = schedule.nextAt - Date.now();
  if (remain <= 0) return "sắp lấy...";
  return formatCountdown(remain);
}

function updateNextPollCells() {
  const label = nextPollLabel();
  const hint = el("nextPollHint");
  if (hint) {
    const schedule = getPriceAlertSchedule ? getPriceAlertSchedule() : null;
    if (schedule && schedule.nextAt) {
      const at = new Date(schedule.nextAt).toLocaleTimeString("vi-VN", { hour12: false });
      hint.textContent =
        `Server poll nến ~${Math.round((schedule.intervalMs || 30000) / 1000)}s (Telegram). ` +
        `Lần lấy tiếp: còn ${label} (lúc ${at})`;
    } else {
      hint.textContent =
        "Cảnh báo Telegram do server (start_server.bat). Chưa có lần poll — chạy API rồi đợi ~30s.";
    }
  }
  document.querySelectorAll(".next-poll-cell").forEach((node) => {
    const enabled = node.dataset.enabled === "1";
    node.textContent = enabled ? label : "--";
  });
}

function formatQuote(alert) {
  if (alert.lastError) {
    const t = alert.lastAt
      ? new Date(alert.lastAt).toLocaleTimeString("vi-VN", { hour12: false })
      : "";
    return t ? `${alert.lastError} · ${t}` : alert.lastError;
  }
  if (alert.lastClose != null) {
    const candle = alert.lastCandleTime || "";
    return (
      `M1 ${candle} C=${alert.lastClose}` +
      (alert.lastHigh != null ? ` H=${alert.lastHigh}` : "") +
      (alert.lastLow != null ? ` L=${alert.lastLow}` : "")
    );
  }
  if (alert.lastBid == null || alert.lastAsk == null) return "--";
  const t = alert.lastAt
    ? new Date(alert.lastAt).toLocaleTimeString("vi-VN", { hour12: false })
    : "";
  return t
    ? `bid ${alert.lastBid} / ask ${alert.lastAsk} · ${t}`
    : `bid ${alert.lastBid} / ask ${alert.lastAsk}`;
}

function renderTable() {
  const body = el("alertTableBody");
  const alerts = loadPriceAlerts();
  body.innerHTML = "";
  if (!alerts.length) {
    body.innerHTML = '<tr class="empty-row"><td colspan="7">Chưa có báo thức nào</td></tr>';
    updateNextPollCells();
    return;
  }
  const countdown = nextPollLabel();
  alerts.forEach((alert) => {
    const tr = document.createElement("tr");
    const low = Math.min(Number(alert.zoneLow), Number(alert.zoneHigh));
    const high = Math.max(Number(alert.zoneLow), Number(alert.zoneHigh));
    const st = statusLabel(alert);
    const noteHtml = alert.note
      ? `<div class="hint">${String(alert.note).replace(/&/g, "&amp;").replace(/</g, "&lt;")}</div>`
      : "";
    const nextText = alert.enabled ? countdown : "--";
    tr.innerHTML =
      `<td>${alert.account}</td>` +
      `<td>${alert.symbol}</td>` +
      `<td>${low} – ${high}${noteHtml}</td>` +
      `<td>${formatQuote(alert)}</td>` +
      `<td class="next-poll-cell" data-enabled="${alert.enabled ? "1" : "0"}">${nextText}</td>` +
      `<td><span class="timer-status ${st.cls}">${st.text}</span></td>` +
      `<td class="row-actions"></td>`;

    const actions = tr.querySelector(".row-actions");

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "btn btn-secondary";
    toggle.textContent = alert.enabled ? "Tắt" : "Bật";
    toggle.addEventListener("click", () => {
      const next = loadPriceAlerts().map((item) => {
        if (item.id !== alert.id) return item;
        return {
          ...item,
          enabled: !item.enabled,
          fired: false,
          primed: false,
          inside: false,
        };
      });
      savePriceAlerts(next);
      renderTable();
    });

    const del = document.createElement("button");
    del.type = "button";
    del.className = "btn-danger-outline";
    del.textContent = "Xóa";
    del.addEventListener("click", () => {
      savePriceAlerts(loadPriceAlerts().filter((item) => item.id !== alert.id));
      renderTable();
    });

    actions.appendChild(toggle);
    actions.appendChild(del);
    body.appendChild(tr);
  });
  updateNextPollCells();
}

async function loadAccounts() {
  const data = await apiGet("/api/accounts", { useCache: true });
  const accounts = data.accounts || [];
  const select = el("account");
  const saved = localStorage.getItem(ACCOUNT_KEY) || "";
  select.innerHTML = "";
  if (!accounts.length) {
    select.innerHTML = '<option value="">-- chưa có account --</option>';
    setQuoteHint("Chưa có account trong accounts.xml.", true);
    return;
  }
  accounts.forEach((acc) => {
    const opt = document.createElement("option");
    opt.value = acc.name;
    opt.textContent = acc.name + (acc.server ? ` (${acc.server})` : "");
    select.appendChild(opt);
  });
  let chosen = "";
  if (accounts.some((a) => a.name === DEFAULT_QUOTE_ACCOUNT)) chosen = DEFAULT_QUOTE_ACCOUNT;
  if (saved && saved !== "fake" && accounts.some((a) => a.name === saved)) chosen = saved;
  if (!chosen) chosen = accounts[0].name;
  select.value = chosen;
  localStorage.setItem(ACCOUNT_KEY, chosen);
}

async function fetchQuote() {
  const account = el("account").value;
  const symbol = (el("symbol").value || "").trim();
  if (!account || !symbol) {
    setQuoteHint("Chọn account và nhập symbol.", true);
    return;
  }
  try {
    const q = new URLSearchParams({ account, symbol, side: "buy" });
    const data = await withBusy(
      () => apiGet(`/api/quote?${q}`, { useCache: false, timeoutMs: 30000 }),
      "Đang lấy giá...",
      { block: false },
    );
    setQuoteHint(`Quote ${data.symbol}: bid=${data.bid} ask=${data.ask}`);
    if (el("zoneLow").value === "" && el("zoneHigh").value === "") {
      el("zoneLow").value = data.bid;
      el("zoneHigh").value = data.ask;
    }
    markApiOk("Đã lấy giá thị trường");
  } catch (err) {
    setQuoteHint(`Không lấy được giá: ${err.message || err}`, true);
  }
}

function setNotifyHint(text, asError = false) {
  const hint = el("notifyHint");
  if (!hint) return;
  hint.textContent = text || "";
  hint.classList.toggle("hint-error", !!asError && !!text);
}

async function addAlert() {
  const account = el("account").value;
  const symbol = (el("symbol").value || "").trim().toUpperCase();
  let low = parseFloat(el("zoneLow").value);
  let high = parseFloat(el("zoneHigh").value);
  if (!account) {
    setQuoteHint("Chọn account.", true);
    return;
  }
  if (!symbol) {
    setQuoteHint("Nhập symbol.", true);
    return;
  }
  if (!Number.isFinite(low) && !Number.isFinite(high)) {
    setQuoteHint("Nhập vùng giá (từ / đến). Một mức cũng được — điền một ô.", true);
    return;
  }
  if (!Number.isFinite(low)) low = high;
  if (!Number.isFinite(high)) high = low;

  const alert = {
    id: uid(),
    account,
    symbol,
    zoneLow: Math.min(low, high),
    zoneHigh: Math.max(low, high),
    note: (el("note").value || "").trim(),
    enabled: true,
    fired: false,
    primed: false,
    inside: false,
  };
  savePriceAlerts([alert, ...loadPriceAlerts()]);
  el("note").value = "";
  setQuoteHint(
    `Đã thêm ${symbol} ${alert.zoneLow}–${alert.zoneHigh}. ` +
      "Server poll nến M1 và gửi Telegram khi chạm vùng (cần start_server.bat / API đang chạy).",
  );
  renderTable();
}

async function testTelegram() {
  setNotifyHint("Đang gửi tin thử Telegram...");
  try {
    await apiPost("/api/setup/telegram-test", {});
    setNotifyHint("Đã gửi thử — kiểm tra app Telegram trên điện thoại / máy.");
  } catch (err) {
    setNotifyHint(err.message || String(err), true);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  el("themeToggle").addEventListener("click", toggleTheme);
  el("btnFetchQuote").addEventListener("click", fetchQuote);
  el("btnAdd").addEventListener("click", addAlert);
  if (el("btnTestNotify")) el("btnTestNotify").addEventListener("click", testTelegram);
  el("account").addEventListener("change", () => {
    localStorage.setItem(ACCOUNT_KEY, el("account").value);
  });
  window.addEventListener("setup-alerts-updated", renderTable);
  window.addEventListener("setup-alerts-schedule", updateNextPollCells);
  setInterval(updateNextPollCells, 1000);
  renderTable();
  updateNextPollCells();
  setNotifyHint("Cảnh báo: Telegram (xml/telegram.xml). Nút Thử gửi 1 tin kiểm tra bot.");
  try {
    await loadAccounts();
    markApiOk();
  } catch (err) {
    markApiError(err);
  }
});
