// Trang lịch sử — bảng + busy + refresh throttle.
const { el, initTheme, toggleTheme, apiGet, withBusy, onVisibleRefresh, markApiOk, markApiError } = window.MT5;

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

function renderHistoryTable(rows) {
  const body = el("historyBody");
  const count = el("historyCount");

  if (!rows.length) {
    body.innerHTML = '<tr class="empty-row"><td colspan="9">Chưa có lịch sử lệnh nào.</td></tr>';
    count.textContent = "0 dòng";
    return;
  }

  count.textContent = `${rows.length} dòng`;
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

async function loadHistory({ silent = false, useCache = true } = {}) {
  const body = el("historyBody");
  const limitRaw = Number(el("historyLimit").value);
  const limit = Number.isFinite(limitRaw) && limitRaw > 0 ? Math.min(500, Math.floor(limitRaw)) : 50;
  el("historyLimit").value = String(limit);

  const run = async () => {
    if (!silent) {
      body.innerHTML = '<tr class="empty-row"><td colspan="9">Đang tải...</td></tr>';
    }
    const data = await apiGet(`/api/history?limit=${limit}`, { useCache });
    renderHistoryTable(data.rows || []);
    markApiOk();
  };

  try {
    if (silent) await run();
    else await withBusy(run, "Đang tải lịch sử...");
  } catch (err) {
    body.innerHTML = `<tr class="empty-row"><td colspan="9">Lỗi tải lịch sử: ${escapeHtml(err.message)}</td></tr>`;
    el("historyCount").textContent = "";
    markApiError(err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  loadHistory({ useCache: false });

  el("themeToggle").addEventListener("click", toggleTheme);
  el("btnHistory").addEventListener("click", () => loadHistory({ useCache: false }));

  onVisibleRefresh(() => loadHistory({ silent: true, useCache: true }), { minIntervalMs: 20000 });
});
