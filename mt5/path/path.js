// Trang Path — busy indicator + refresh có throttle.
const {
  el, initTheme, toggleTheme, apiGet, apiPost, apiPut,
  withBusy, loadWithRetry, onVisibleRefresh, markApiOk, markApiError,
} = window.MT5;

let lastPaths = [];

function renderPathsList() {
  const box = el("pathsList");
  box.innerHTML = "";
  if (!lastPaths.length) {
    box.innerHTML = '<p class="hint">Chưa có path nào trong paths.xml.</p>';
    return;
  }

  for (const p of lastPaths) {
    const row = document.createElement("div");
    row.className = "path-row";
    row.innerHTML = `
      <div class="field">
        <label>Name</label>
        <input type="text" value="${p.name}" readonly class="readonly" />
      </div>
      <div class="field field-wide">
        <label>Exe</label>
        <input type="text" class="path-exe-input" data-name="${p.name}" value="${p.exe || ""}" />
      </div>
      <div class="field path-row-actions">
        <label>&nbsp;</label>
        <button type="button" class="btn btn-secondary btn-save-path" data-name="${p.name}">Lưu</button>
      </div>
    `;
    box.appendChild(row);
  }

  box.querySelectorAll(".btn-save-path").forEach((btn) => {
    btn.addEventListener("click", () => {
      const name = btn.dataset.name;
      const input = box.querySelector(`.path-exe-input[data-name="${name}"]`);
      savePathExe(name, input.value);
    });
  });
}

async function loadPaths({ silent = false, useCache = true } = {}) {
  const run = async () => {
    const data = await apiGet("/api/paths", { useCache });
    lastPaths = data.paths || [];
    renderPathsList();
    markApiOk();
  };
  try {
    if (silent) await run();
    else await withBusy(run, "Đang tải paths...");
  } catch (err) {
    markApiError(err);
  }
}

async function savePathExe(name, exe) {
  try {
    const data = await withBusy(
      () => apiPut(`/api/paths/${encodeURIComponent(name)}`, { exe: exe.trim() }),
      `Đang lưu path ${name}...`,
      { block: true },
    );
    lastPaths = data.paths || [];
    renderPathsList();
    try {
      await loadWithRetry(() => loadPaths({ silent: true, useCache: false }));
    } catch (_) {
      /* ignore */
    }
  } catch (err) {
    alert(`Lỗi lưu path '${name}': ${err.message}`);
  }
}

async function addPath() {
  const name = el("newPathName").value.trim();
  const exe = el("newPathExe").value.trim();
  const status = el("addPathStatus");
  if (!name || !exe) {
    alert("Cần điền Name và Exe.");
    return;
  }
  const btn = el("btnAddPath");
  btn.disabled = true;
  status.textContent = "Đang thêm...";
  try {
    const data = await withBusy(
      () => apiPost("/api/paths", { name, exe }),
      "Đang thêm path...",
      { block: true },
    );
    lastPaths = data.paths || [];
    renderPathsList();
    el("newPathName").value = "";
    el("newPathExe").value = "";
    status.textContent = `Đã thêm path '${name}'.`;
    try {
      await loadWithRetry(() => loadPaths({ silent: true, useCache: false }));
    } catch (_) {
      /* ignore */
    }
  } catch (err) {
    status.textContent = "";
    alert(`Lỗi thêm path: ${err.message}`);
  } finally {
    btn.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  loadPaths({ useCache: false });

  el("themeToggle").addEventListener("click", toggleTheme);
  el("btnAddPath").addEventListener("click", addPath);
  el("btnReloadPaths").addEventListener("click", () => loadPaths({ useCache: false }));

  onVisibleRefresh(() => loadPaths({ silent: true, useCache: true }), { minIntervalMs: 20000 });
});
