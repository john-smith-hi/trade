// Fibonacci retracement — tính trên trình duyệt; đỉnh/đáy lưu xml/fibo.xml qua API.
const {
  el,
  initTheme,
  toggleTheme,
  apiGet,
  apiPut,
  debounce,
  markApiOk,
  markApiError,
} = window.MT5;

const {
  LEVELS,
  ROLES,
  SIDE_HINT,
  priceDigits,
  roundTo,
  formatPrice,
  priceAt,
  rowClass,
} = window.FiboCalc;

const LEGACY_STORAGE_KEY = "setup-fibo";

let hydrated = false;
let saveBusy = false;
let saveQueued = false;

function zonesFor(side, fmt, at) {
  const band = "Bao gồm Fibo 0.500, 0.618 và 0.786. Vùng có tỷ lệ R:R an toàn và tối ưu nhất.";
  const scalp = "Bao gồm Fibo 0.236 và 0.382. Phù hợp đánh phản ứng nhanh khi xuất hiện nến đảo chiều.";
  if (side === "sell") {
    return [
      {
        title: "Vùng Premium (Giá cao — ưu tiên canh SELL)",
        range: `${fmt(at(0.5))} – ${fmt(at(0.786))}`,
        detail: band,
      },
      {
        title: "Vùng Cân Trung Hạn (Scalp ngắn H1/M15)",
        range: `${fmt(at(0.236))} – ${fmt(at(0.382))}`,
        detail: scalp,
      },
      {
        title: "Vùng Discount (Giá thấp — hạn chế SELL đuổi)",
        range: `Dưới ${fmt(at(0.236))}`,
        detail: `Giá nằm quá gần đáy ${fmt(at(0))}. Chỉ vào lệnh Sell nếu giá đóng nến đục thủng đáy (kịch bản Break & Retest).`,
      },
    ];
  }
  return [
    {
      title: "Vùng Discount (Giá thấp — ưu tiên canh BUY)",
      range: `${fmt(at(0.786))} – ${fmt(at(0.5))}`,
      detail: band,
    },
    {
      title: "Vùng Cân Trung Hạn (Scalp ngắn H1/M15)",
      range: `${fmt(at(0.382))} – ${fmt(at(0.236))}`,
      detail: scalp,
    },
    {
      title: "Vùng Premium (Giá cao — hạn chế BUY đuổi)",
      range: `Trên ${fmt(at(0.236))}`,
      detail: `Giá nằm quá gần đỉnh ${fmt(at(0))}. Chỉ vào lệnh Buy nếu giá đóng nến đục thủng đỉnh (kịch bản Break & Retest).`,
    },
  ];
}

function gapText(side, fmt, at) {
  if (side === "sell") {
    return `Khoảng ${fmt(at(0.382))} – ${fmt(at(0.5))} nằm giữa scalp và Premium. Trên ${fmt(at(0.786))} đến đỉnh ${fmt(at(1))}: vượt 78.6% thì kịch bản giảm dễ hết hiệu lực.`;
  }
  return `Khoảng ${fmt(at(0.5))} – ${fmt(at(0.382))} nằm giữa Discount và scalp. Dưới ${fmt(at(0.786))} đến đáy ${fmt(at(1))}: vượt 78.6% thì kịch bản tăng dễ hết hiệu lực.`;
}

function readNumber(id) {
  const raw = el(id).value.trim();
  if (raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function showError(message) {
  const node = el("fiboError");
  if (!message) {
    node.textContent = "";
    node.classList.add("hidden");
    return;
  }
  node.textContent = message;
  node.classList.remove("hidden");
}

function setView(mode) {
  el("resultCard").classList.toggle("hidden", mode !== "result");
  el("emptyCard").classList.toggle("hidden", mode !== "empty");
}

function applySettings(settings) {
  const high = settings && settings.high;
  const low = settings && settings.low;
  const side = settings && settings.side;
  el("swingHigh").value = high === null || high === undefined ? "" : String(high);
  el("swingLow").value = low === null || low === undefined ? "" : String(low);
  el("side").value = side === "buy" ? "buy" : "sell";
}

function payloadFromForm() {
  const highRaw = el("swingHigh").value.trim();
  const lowRaw = el("swingLow").value.trim();
  return {
    high: highRaw === "" ? null : readNumber("swingHigh"),
    low: lowRaw === "" ? null : readNumber("swingLow"),
    side: el("side").value === "buy" ? "buy" : "sell",
  };
}

function restoreFromLocalStorage() {
  try {
    const raw = localStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) return false;
    const data = JSON.parse(raw);
    if (!data || (typeof data.high !== "string" && typeof data.low !== "string")) return false;
    applySettings({
      high: data.high === "" ? null : Number(data.high),
      low: data.low === "" ? null : Number(data.low),
      side: data.side,
    });
    return !!(data.high || data.low);
  } catch (err) {
    return false;
  }
}

function clearLegacyStorage() {
  try {
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch (err) { /* ignore */ }
}

function hasSavedLevels(settings) {
  if (!settings) return false;
  return (settings.high !== null && settings.high !== undefined)
    || (settings.low !== null && settings.low !== undefined);
}

async function migrateFromLocalStorage(serverSettings) {
  if (hasSavedLevels(serverSettings)) {
    clearLegacyStorage();
    return false;
  }
  if (!restoreFromLocalStorage()) return false;
  try {
    await apiPut("/api/setup/fibo", payloadFromForm());
    clearLegacyStorage();
    markApiOk("Đã chuyển đỉnh/đáy lên server");
    return true;
  } catch (err) {
    markApiError(err);
    return false;
  }
}

async function persistToServer() {
  if (!hydrated) return;
  if (saveBusy) {
    saveQueued = true;
    return;
  }
  saveBusy = true;
  try {
    await apiPut("/api/setup/fibo", payloadFromForm());
    markApiOk("Đã lưu đỉnh/đáy");
  } catch (err) {
    markApiError(err);
  } finally {
    saveBusy = false;
    if (saveQueued) {
      saveQueued = false;
      persistToServer();
    }
  }
}

const scheduleSave = debounce(() => {
  persistToServer();
}, 400);

function render(high, low, side) {
  const digits = priceDigits(high, low);
  const at = (ratio) => roundTo(priceAt(high, low, ratio, side), digits);
  const fmt = (value) => formatPrice(value, digits);
  const roles = ROLES[side];

  const rows = LEVELS.map((level) => ({
    ...level,
    price: at(level.ratio),
    role: roles[level.ratio],
  })).sort((a, b) => b.price - a.price);

  el("fiboBody").innerHTML = rows.map((row) => (
    `<tr class="${rowClass(row.ratio)}">` +
      `<td class="level">${row.label}</td>` +
      `<td class="price">${fmt(row.price)}</td>` +
      `<td class="role">${row.role}</td>` +
    "</tr>"
  )).join("");

  const range = roundTo(high - low, digits);
  const anchor = side === "sell"
    ? `100% = đỉnh ${fmt(high)}, 0% = đáy ${fmt(low)}`
    : `100% = đáy ${fmt(low)}, 0% = đỉnh ${fmt(high)}`;
  el("rangeHint").textContent = `Biên độ ${fmt(range)}. ${anchor}. Bảng xếp từ giá cao xuống giá thấp.`;

  el("zoneList").innerHTML = zonesFor(side, fmt, at).map((zone) => (
    "<li>" +
      `<strong>${zone.title}:</strong> ${zone.range}` +
      `<ul><li>${zone.detail}</li></ul>` +
    "</li>"
  )).join("");
  el("gapHint").textContent = gapText(side, fmt, at);
  setView("result");
}

function update({ save = false } = {}) {
  const side = el("side").value === "buy" ? "buy" : "sell";
  el("sideHint").textContent = SIDE_HINT[side];
  const high = readNumber("swingHigh");
  const low = readNumber("swingLow");

  if (hydrated && save) scheduleSave();

  if (high === null || low === null) {
    showError("");
    setView("empty");
    return;
  }
  if (high <= low) {
    showError("Đỉnh phải lớn hơn đáy.");
    setView("error");
    return;
  }
  showError("");
  render(high, low, side);
}

async function loadSettings() {
  let migrated = false;
  try {
    const data = await apiGet("/api/setup/fibo", { useCache: false });
    applySettings(data.settings || {});
    migrated = await migrateFromLocalStorage(data.settings || {});
    if (!migrated) markApiOk("Đã tải đỉnh/đáy từ server");
  } catch (err) {
    if (restoreFromLocalStorage()) {
      markApiError(new Error(`${err.message || err} — đang dùng bản trình duyệt tạm.`));
    } else {
      markApiError(err);
    }
  } finally {
    hydrated = true;
    update({ save: false });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  el("themeToggle").addEventListener("click", toggleTheme);
  ["swingHigh", "swingLow", "side"].forEach((id) => {
    el(id).addEventListener("input", () => update({ save: true }));
    el(id).addEventListener("change", () => update({ save: true }));
  });
  loadSettings();
});
