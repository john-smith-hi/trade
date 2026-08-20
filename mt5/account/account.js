// Trang Accounts — load paths + accounts song song.
const {
  el, initTheme, toggleTheme, apiGet, apiPost, apiPut,
  withBusy, loadWithRetry, onVisibleRefresh, markApiOk, markApiError, clearApiCache,
} = window.MT5;

let lastAccounts = [];
let lastPaths = [];

function fillPathSelects(selectedEdit, selectedNew) {
  const editSelect = el("editPath");
  const newSelect = el("newPath");
  const keepEdit = selectedEdit !== undefined ? selectedEdit : editSelect.value;
  const keepNew = selectedNew !== undefined ? selectedNew : newSelect.value;

  const buildOptions = (select, current) => {
    select.innerHTML = "";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "(không chọn path)";
    select.appendChild(empty);
    for (const p of lastPaths) {
      const opt = document.createElement("option");
      opt.value = p.name;
      opt.textContent = `${p.name} — ${p.exe || "(chưa có exe)"}`;
      select.appendChild(opt);
    }
    if (current && [...select.options].some((o) => o.value === current)) {
      select.value = current;
    } else {
      select.value = "";
    }
  };

  buildOptions(editSelect, keepEdit);
  buildOptions(newSelect, keepNew);
}

function clearEditForm() {
  el("editLogin").value = "";
  el("editServer").value = "";
  el("editPath").value = "";
  el("editSuffix").value = "";
  el("editMulti").value = "1";
  el("editDefaultLot").value = "0.01";
  el("editMaxLoss").value = "";
  el("editAutoCopyEnabled").value = "false";
  el("editAutoCopyTargets").value = "";
}

function fillEditForm(accounts) {
  const acc = accounts.find((a) => a.name === el("account").value);
  if (!acc) {
    clearEditForm();
    return;
  }
  el("editLogin").value = acc.login ?? "";
  el("editServer").value = acc.server ?? "";
  fillPathSelects(acc.path || "", el("newPath").value);
  el("editSuffix").value = acc.suffix ?? "";
  el("editMulti").value = acc.multi ?? 1;
  el("editDefaultLot").value = acc.default_lot ?? 0.01;
  el("editMaxLoss").value = acc.xauusd_max_loss == null ? "" : acc.xauusd_max_loss;
  el("editAutoCopyEnabled").value = acc.auto_copy_enabled ? "true" : "false";
  el("editAutoCopyTargets").value = (acc.auto_copy_targets || []).join(",");
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
  const pathLabel = acc.path
    ? `${acc.path}${acc.path_exe ? ` → ${acc.path_exe}` : ""}`
    : "(không chọn)";
  el("accountInfo").textContent =
    `login: ${acc.login} | server: ${acc.server} | path: ${pathLabel} | suffix: "${acc.suffix}" | multi: ${acc.multi} | default_lot: ${defaultLot} | max_loss: ${maxLoss} | ${autoCopy}`;
}

function renderAccounts(accounts) {
  const select = el("account");
  const previous = select.value;
  select.innerHTML = "";

  if (!accounts.length) {
    select.innerHTML = '<option value="">(không có account nào trong accounts.xml)</option>';
    el("accountInfo").textContent = "";
    clearEditForm();
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
  fillEditForm(accounts);
  select.onchange = () => {
    updateAccountInfo(accounts);
    fillEditForm(accounts);
  };
}

function parseTargetsCsv(text) {
  return String(text || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function buildEditPayload() {
  return {
    path: el("editPath").value.trim(),
    suffix: el("editSuffix").value,
    multi: el("editMulti").value,
    default_lot: el("editDefaultLot").value || "0.01",
    xauusd_max_loss: el("editMaxLoss").value,
    auto_copy_enabled: el("editAutoCopyEnabled").value === "true",
    auto_copy_targets: parseTargetsCsv(el("editAutoCopyTargets").value),
  };
}

function buildNewAccountPayload() {
  return {
    name: el("newName").value.trim(),
    login: el("newLogin").value,
    password: el("newPassword").value,
    server: el("newServer").value.trim(),
    path: el("newPath").value.trim(),
    suffix: el("newSuffix").value,
    multi: el("newMulti").value || "1",
    default_lot: el("newDefaultLot").value || "0.01",
    xauusd_max_loss: el("newMaxLoss").value,
    auto_copy_enabled: el("newAutoCopyEnabled").value === "true",
    auto_copy_targets: parseTargetsCsv(el("newAutoCopyTargets").value),
  };
}

function clearNewAccountForm() {
  el("newName").value = "";
  el("newLogin").value = "";
  el("newPassword").value = "";
  el("newServer").value = "";
  el("newPath").value = lastPaths[0]?.name || "";
  el("newSuffix").value = "";
  el("newMulti").value = "1";
  el("newDefaultLot").value = "0.01";
  el("newMaxLoss").value = "";
  el("newAutoCopyEnabled").value = "false";
  el("newAutoCopyTargets").value = "";
}

async function loadAll({ silent = false, useCache = true } = {}) {
  const run = async () => {
    // Song song: paths + accounts cùng lúc.
    const [pathsData, accountsData] = await Promise.all([
      apiGet("/api/paths", { useCache }),
      apiGet("/api/accounts", { useCache }),
    ]);
    lastPaths = pathsData.paths || [];
    lastAccounts = accountsData.accounts || [];
    fillPathSelects(el("editPath").value, el("newPath").value);
    renderAccounts(lastAccounts);
    markApiOk();
  };
  try {
    if (silent) await run();
    else await withBusy(run, "Đang tải accounts + paths...");
  } catch (err) {
    markApiError(err);
  }
}

async function reloadAccounts() {
  try {
    await withBusy(async () => {
      clearApiCache();
      const [reloadData, pathsData] = await Promise.all([
        apiPost("/api/reload-accounts"),
        apiGet("/api/paths", { useCache: false }),
      ]);
      lastAccounts = reloadData.accounts || [];
      lastPaths = pathsData.paths || [];
      fillPathSelects(el("editPath").value, el("newPath").value);
      renderAccounts(lastAccounts);
      markApiOk("Đã nạp lại");
    }, "Đang nạp lại...");
  } catch (err) {
    alert(`Lỗi tải lại: ${err.message}`);
  }
}

async function saveSelectedAccount() {
  const name = el("account").value;
  const status = el("editAccountStatus");
  if (!name) {
    alert("Chưa chọn account để sửa.");
    return;
  }
  const btn = el("btnSaveAccount");
  btn.disabled = true;
  status.textContent = "Đang lưu...";
  try {
    const data = await withBusy(
      () => apiPut(`/api/accounts/${encodeURIComponent(name)}`, buildEditPayload()),
      "Đang lưu account...",
      { block: true },
    );
    lastAccounts = data.accounts || [];
    renderAccounts(lastAccounts);
    try {
      await loadWithRetry(() => loadAll({ silent: true, useCache: false }));
    } catch (_) {
      /* đã có data từ PUT */
    }
    status.textContent = "Đã lưu vào accounts.xml.";
  } catch (err) {
    status.textContent = "";
    alert(`Lỗi lưu account: ${err.message}`);
  } finally {
    btn.disabled = false;
  }
}

async function addAccount() {
  const payload = buildNewAccountPayload();
  const status = el("addAccountStatus");
  if (!payload.name || !payload.login || !payload.password || !payload.server) {
    alert("Cần điền Name, Login, Password, Server.");
    return;
  }
  const btn = el("btnAddAccount");
  btn.disabled = true;
  status.textContent = "Đang thêm...";
  try {
    const data = await withBusy(
      () => apiPost("/api/accounts", payload),
      "Đang thêm account...",
      { block: true },
    );
    lastAccounts = data.accounts || [];
    renderAccounts(lastAccounts);
    el("account").value = payload.name;
    fillEditForm(lastAccounts);
    updateAccountInfo(lastAccounts);
    try {
      await loadWithRetry(() => loadAll({ silent: true, useCache: false }));
      el("account").value = payload.name;
      fillEditForm(lastAccounts);
      updateAccountInfo(lastAccounts);
    } catch (_) {
      /* ignore */
    }
    clearNewAccountForm();
    status.textContent = `Đã thêm '${payload.name}'.`;
  } catch (err) {
    status.textContent = "";
    alert(`Lỗi thêm account: ${err.message}`);
  } finally {
    btn.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  loadAll({ useCache: false });

  el("themeToggle").addEventListener("click", toggleTheme);
  el("btnReloadAccounts").addEventListener("click", reloadAccounts);
  el("btnSaveAccount").addEventListener("click", saveSelectedAccount);
  el("btnAddAccount").addEventListener("click", addAccount);

  onVisibleRefresh(() => loadAll({ silent: true, useCache: true }), { minIntervalMs: 20000 });
});
