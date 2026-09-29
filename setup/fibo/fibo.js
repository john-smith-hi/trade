// Fibonacci retracement — tính trên trình duyệt, không gọi API.
const THEME_KEY = "mt5-theme";
const STORAGE_KEY = "setup-fibo";

const LEVELS = [
  { ratio: 1, label: "1.000 (100%)" },
  { ratio: 0.786, label: "0.786 (78.6%)" },
  { ratio: 0.618, label: "0.618 (61.8%)" },
  { ratio: 0.5, label: "0.500 (50.0%)" },
  { ratio: 0.382, label: "0.382 (38.2%)" },
  { ratio: 0.236, label: "0.236 (23.6%)" },
  { ratio: 0, label: "0.000 (0%)" },
];

const ROLES = {
  sell: {
    1: "Đỉnh gốc sóng giảm chính",
    0.786: "Giới hạn cuối cùng để duy trì xu hướng giảm",
    0.618: "Golden Zone (Vùng kháng cự chính mạnh nhất)",
    0.5: "Equilibrium (Mức giá cân bằng sóng)",
    0.382: "Cản hồi phục nhẹ đầu tiên",
    0.236: "Vùng Flip Zone (cựu hỗ trợ đã bị đâm thủng)",
    0: "Đáy thấp nhất hiện tại",
  },
  buy: {
    1: "Đáy gốc sóng tăng chính",
    0.786: "Giới hạn cuối cùng để duy trì xu hướng tăng",
    0.618: "Golden Zone (Vùng hỗ trợ chính mạnh nhất)",
    0.5: "Equilibrium (Mức giá cân bằng sóng)",
    0.382: "Hỗ trợ hồi nhẹ đầu tiên",
    0.236: "Vùng Flip Zone (cựu kháng cự đã bị phá)",
    0: "Đỉnh cao nhất hiện tại",
  },
};

const SIDE_HINT = {
  sell: "SELL: 100% tại đỉnh, 0% tại đáy. Giá hồi từ đáy lên — ưu tiên Sell ở Premium (50%–78.6%).",
  buy: "BUY: 100% tại đáy, 0% tại đỉnh. Giá hồi từ đỉnh xuống — ưu tiên Buy ở Discount (50%–78.6%).",
};

function el(id) {
  return document.getElementById(id);
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const btn = el("themeToggle");
  if (btn) btn.textContent = theme === "dark" ? "Chế độ sáng" : "Chế độ tối";
}

function initTheme() {
  let saved = "light";
  try {
    saved = localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
  } catch (err) {
    saved = "light";
  }
  applyTheme(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  const next = current === "dark" ? "light" : "dark";
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch (err) { /* ignore */ }
  applyTheme(next);
}

function priceDigits(high, low) {
  const mag = Math.max(Math.abs(high), Math.abs(low));
  if (mag >= 100) return 2;
  if (mag >= 10) return 3;
  return 5;
}

function roundTo(value, digits) {
  const stabilized = Number(value.toFixed(digits + 6));
  const factor = 10 ** digits;
  return Math.round(stabilized * factor) / factor;
}

function formatPrice(value, digits) {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function priceAt(high, low, ratio, side) {
  const range = high - low;
  return side === "sell" ? low + range * ratio : high - range * ratio;
}

function rowClass(ratio) {
  const classes = [];
  if (ratio === 0.618 || ratio === 0.5) classes.push("is-key");
  if (ratio === 0.786 || ratio === 0.618 || ratio === 0.5) classes.push("is-best");
  if (ratio === 0.382 || ratio === 0.236) classes.push("is-scalp");
  return classes.join(" ");
}

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

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      high: el("swingHigh").value,
      low: el("swingLow").value,
      side: el("side").value,
    }));
  } catch (err) { /* ignore */ }
}

function restore() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (data && typeof data.high === "string") el("swingHigh").value = data.high;
    if (data && typeof data.low === "string") el("swingLow").value = data.low;
    if (data && (data.side === "buy" || data.side === "sell")) el("side").value = data.side;
  } catch (err) { /* ignore */ }
}

function update() {
  const side = el("side").value === "buy" ? "buy" : "sell";
  el("sideHint").textContent = SIDE_HINT[side];
  const high = readNumber("swingHigh");
  const low = readNumber("swingLow");
  persist();

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

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  el("themeToggle").addEventListener("click", toggleTheme);
  restore();
  ["swingHigh", "swingLow", "side"].forEach((id) => {
    el(id).addEventListener("input", update);
    el(id).addEventListener("change", update);
  });
  update();
});
