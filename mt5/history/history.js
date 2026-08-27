// Trang lịch sử — bảng + phân trang + busy + refresh throttle.
const { el, initTheme, toggleTheme, apiGet, apiDelete, withBusy, onVisibleRefresh, markApiOk, markApiError } = window.MT5;

let historyOffset = 0;

function statusClass(status) {
  const s = String(status || "").toUpperCase();
  if (s.includes("FAIL") || s.includes("ERROR")) return "status-fail";
  if (s.includes("SUCCESS") || s === "SUCCESS") return "status-ok";
  return "status-muted";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function getHistoryLimit() {
  const limitRaw = Number(el("historyLimit").value);
  const limit = Number.isFinite(limitRaw) && limitRaw > 0 ? Math.min(500, Math.floor(limitRaw)) : 50;
  el("historyLimit").value = String(limit);
  return limit;
}

function renderHistoryTable(rows) {
  const body = el("historyBody");

  if (!rows.length) {
    body.innerHTML = '<tr class="empty-row"><td colspan="9">Chưa có lịch sử lệnh nào.</td></tr>';
    return;
  }

  body.innerHTML = rows.map((row) => `
    <tr>
      <td class="col-time">${escapeHtml(row.time)}</td>
      <td>${escapeHtml(row.account)}</td>
      <td>${escapeHtml(row.symbol)}</td>
      <td class="col-num">${escapeHtml(row.lot)}</td>
      <td><span class="status-pill ${statusClass(row.status)}">${escapeHtml(row.status)}</span></td>
      <td class="col-num">${escapeHtml(row.ticket)}</td>
      <td class="col-num">${escapeHtml(row.retcode)}</td>
      <td>${escapeHtml(row.comment)}</td>
      <td class="col-detail">${escapeHtml(row.detail)}</td>
    </tr>
  `).join("");
}

function renderHistoryMeta({ total = 0, limit = 50, offset = 0 } = {}) {
  const count = el("historyCount");
  const pageInfo = el("historyPageInfo");
  const btnPrev = el("btnHistoryPrev");
  const btnNext = el("btnHistoryNext");

  if (total <= 0) {
    count.textContent = "0 dòng";
    pageInfo.textContent = "Trang 1 / 1";
    btnPrev.disabled = true;
    btnNext.disabled = true;
    return;
  }

  const page = Math.floor(offset / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / limit));
  const from = offset + 1;
  const to = Math.min(offset + limit, total);

  count.textContent = `${from}–${to} / ${total} dòng`;
  pageInfo.textContent = `Trang ${page} / ${pageCount}`;
  btnPrev.disabled = offset <= 0;
  btnNext.disabled = offset + limit >= total;
}

async function loadHistory({ silent = false, useCache = true, offset = historyOffset, resetPage = false } = {}) {
  const body = el("historyBody");
  const limit = getHistoryLimit();

  if (resetPage) {
    historyOffset = 0;
  } else {
    historyOffset = Math.max(0, offset);
  }

  const run = async () => {
    if (!silent) {
      body.innerHTML = '<tr class="empty-row"><td colspan="9">Đang tải...</td></tr>';
    }
    const data = await apiGet(`/api/history?limit=${limit}&offset=${historyOffset}`, { useCache });
    historyOffset = Number(data.offset) || historyOffset;
    renderHistoryTable(data.rows || []);
    renderHistoryMeta({
      total: Number(data.total) || 0,
      limit: Number(data.limit) || limit,
      offset: historyOffset,
    });
    markApiOk();
  };

  try {
    if (silent) await run();
    else await withBusy(run, "Đang tải lịch sử...");
  } catch (err) {
    body.innerHTML = `<tr class="empty-row"><td colspan="9">Lỗi tải lịch sử: ${escapeHtml(err.message)}</td></tr>`;
    el("historyCount").textContent = "";
    el("historyPageInfo").textContent = "—";
    el("btnHistoryPrev").disabled = true;
    el("btnHistoryNext").disabled = true;
    markApiError(err);
  }
}

async function clearHistory() {
  if (!window.confirm("Xóa toàn bộ lịch sử lệnh trong history_mt5.txt? Hành động này không thể hoàn tác.")) {
    return;
  }

  try {
    await withBusy(async () => {
      await apiDelete("/api/history");
      historyOffset = 0;
      renderHistoryTable([]);
      renderHistoryMeta({ total: 0, limit: getHistoryLimit(), offset: 0 });
      markApiOk("Đã xóa lịch sử");
    }, "Đang xóa lịch sử...");
  } catch (err) {
    markApiError(err);
    window.alert(`Lỗi xóa lịch sử: ${err.message || err}`);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  loadHistory({ useCache: false });

  el("themeToggle").addEventListener("click", toggleTheme);
  el("btnHistory").addEventListener("click", () => loadHistory({ useCache: false, resetPage: true }));
  el("btnClearHistory").addEventListener("click", clearHistory);
  el("btnHistoryPrev").addEventListener("click", () => {
    loadHistory({ useCache: false, offset: Math.max(0, historyOffset - getHistoryLimit()) });
  });
  el("btnHistoryNext").addEventListener("click", () => {
    loadHistory({ useCache: false, offset: historyOffset + getHistoryLimit() });
  });

  onVisibleRefresh(() => loadHistory({ silent: true, useCache: true }), { minIntervalMs: 20000 });
});
