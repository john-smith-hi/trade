// Công thức Fibonacci retracement — dùng chung UI và tests.
(function (root) {
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

  function levelsAt(high, low, side) {
    const digits = priceDigits(high, low);
    return LEVELS.map((level) => ({
      ratio: level.ratio,
      label: level.label,
      price: roundTo(priceAt(high, low, level.ratio, side), digits),
      role: ROLES[side][level.ratio],
    })).sort((a, b) => b.price - a.price);
  }

  function zoneRanges(high, low, side) {
    const digits = priceDigits(high, low);
    const at = (ratio) => roundTo(priceAt(high, low, ratio, side), digits);
    if (side === "sell") {
      return {
        premium: [at(0.5), at(0.786)],
        scalp: [at(0.236), at(0.382)],
        chaseBelow: at(0.236),
        extreme: at(0),
      };
    }
    return {
      discount: [at(0.786), at(0.5)],
      scalp: [at(0.382), at(0.236)],
      chaseAbove: at(0.236),
      extreme: at(0),
    };
  }

  const api = {
    LEVELS,
    ROLES,
    SIDE_HINT,
    priceDigits,
    roundTo,
    formatPrice,
    priceAt,
    rowClass,
    levelsAt,
    zoneRanges,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.FiboCalc = api;
})(typeof window !== "undefined" ? window : globalThis);
