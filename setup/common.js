/**
 * Tiện ích dùng chung cho các trang MT5 web.
 * Trước khi load file này, set: window.MT5_PROXY = "proxy.php" | "../proxy.php"
 */
(function (global) {
  const PROXY_URL = global.MT5_PROXY || "proxy.php";
  const THEME_STORAGE_KEY = "mt5-theme";

  function el(id) {
    return document.getElementById(id);
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    const btn = el("themeToggle");
    if (btn) btn.textContent = theme === "dark" ? "Chế độ sáng" : "Chế độ tối";
  }

  function initTheme() {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    applyTheme(saved === "dark" ? "dark" : "light");
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    const next = current === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_STORAGE_KEY, next);
    applyTheme(next);
  }

  // --- Loading bar / overlay (không để kẹt) ---
  let busyCount = 0;
  let blockCount = 0;
  let busyWatchdog = null;

  function ensureBusyDom() {
    let bar = document.getElementById("mt5BusyBar");
    let overlay = document.getElementById("mt5BusyOverlay");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "mt5BusyBar";
      bar.className = "mt5-busy-bar hidden";
      document.body.appendChild(bar);
    }
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "mt5BusyOverlay";
      overlay.className = "mt5-busy-overlay hidden";
      overlay.innerHTML = '<div class="mt5-busy-card"><div class="mt5-spinner"></div><p id="mt5BusyText">Đang tải...</p></div>';
      document.body.appendChild(overlay);
    }
    return { bar, overlay };
  }

  function clearBusyHard() {
    busyCount = 0;
    blockCount = 0;
    const { bar, overlay } = ensureBusyDom();
    bar.classList.add("hidden");
    bar.classList.remove("active");
    overlay.classList.add("hidden");
    if (busyWatchdog) {
      clearTimeout(busyWatchdog);
      busyWatchdog = null;
    }
  }

  function armBusyWatchdog() {
    if (busyWatchdog) clearTimeout(busyWatchdog);
    // Không để UI đứng quá 20s nếu request treo.
    busyWatchdog = setTimeout(() => {
      clearBusyHard();
      const node = el("apiStatus");
      if (node && !node.classList.contains("ok")) {
        node.textContent = "Hết thời gian chờ API — thử Tải lại.";
        node.className = "api-status error";
      }
    }, 20000);
  }

  function setBusy(on, message, { block = false } = {}) {
    const { bar, overlay } = ensureBusyDom();
    if (on) {
      busyCount += 1;
      if (block) blockCount += 1;
      bar.classList.remove("hidden");
      bar.classList.add("active");
      if (blockCount > 0) {
        overlay.classList.remove("hidden");
        const text = document.getElementById("mt5BusyText");
        if (text) text.textContent = message || "Đang xử lý...";
      }
      if (message && el("apiStatus")) {
        el("apiStatus").textContent = message;
        el("apiStatus").className = "api-status";
      }
      armBusyWatchdog();
    } else {
      busyCount = Math.max(0, busyCount - 1);
      if (block) blockCount = Math.max(0, blockCount - 1);
      if (blockCount === 0) {
        overlay.classList.add("hidden");
      }
      if (busyCount === 0) {
        bar.classList.add("hidden");
        bar.classList.remove("active");
        if (busyWatchdog) {
          clearTimeout(busyWatchdog);
          busyWatchdog = null;
        }
      }
    }
  }

  async function withBusy(fn, message, opts = {}) {
    setBusy(true, message, opts);
    try {
      return await fn();
    } finally {
      setBusy(false, null, opts);
    }
  }

  // --- API + in-flight dedupe + short cache ---
  const inflight = new Map();
  const getCache = new Map();
  const GET_CACHE_MS = 15000;

  async function apiRequest(method, path, body, { useCache = false, timeoutMs = 12000 } = {}) {
    const cacheKey = `${method}:${path}`;
    if (method === "GET" && useCache) {
      const hit = getCache.get(cacheKey);
      if (hit && Date.now() - hit.at < GET_CACHE_MS) {
        return hit.data;
      }
    }

    if (method === "GET" && inflight.has(cacheKey)) {
      return inflight.get(cacheKey);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    const options = {
      method,
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    };
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }

    const promise = (async () => {
      try {
        const res = await fetch(`${PROXY_URL}?path=${encodeURIComponent(path)}`, options);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.error || `HTTP ${res.status}`);
        }
        if (method === "GET") {
          getCache.set(cacheKey, { at: Date.now(), data });
        } else {
          for (const key of [...getCache.keys()]) {
            if (key.startsWith("GET:/api/")) getCache.delete(key);
          }
        }
        return data;
      } catch (err) {
        if (err && err.name === "AbortError") {
          throw new Error("API timeout — kiểm tra start_api.bat");
        }
        throw err;
      } finally {
        clearTimeout(timer);
      }
    })();

    if (method === "GET") {
      inflight.set(cacheKey, promise);
      try {
        return await promise;
      } finally {
        inflight.delete(cacheKey);
      }
    }
    return promise;
  }

  function apiGet(path, opts) {
    return apiRequest("GET", path, undefined, opts);
  }

  function apiPost(path, body, opts) {
    return apiRequest("POST", path, body || {}, opts);
  }

  function apiPut(path, body, opts) {
    return apiRequest("PUT", path, body || {}, opts);
  }

  function apiDelete(path, opts) {
    return apiRequest("DELETE", path, undefined, opts);
  }

  function clearApiCache() {
    getCache.clear();
  }

  async function loadWithRetry(loader, attempts = 3, delayMs = 300) {
    let lastErr;
    for (let i = 0; i < attempts; i += 1) {
      try {
        return await loader();
      } catch (err) {
        lastErr = err;
        await new Promise((r) => setTimeout(r, delayMs * (i + 1)));
      }
    }
    throw lastErr || new Error("Không tải lại được dữ liệu");
  }

  function debounce(fn, ms) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  }

  function onVisibleRefresh(fn, { minIntervalMs = 20000 } = {}) {
    let lastRun = Date.now();
    const run = () => {
      const now = Date.now();
      if (now - lastRun < minIntervalMs) return;
      lastRun = now;
      fn();
    };
    const debounced = debounce(run, 250);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") debounced();
    });
    window.addEventListener("focus", debounced);
  }

  function markApiOk(msg) {
    const node = el("apiStatus");
    if (!node) return;
    node.textContent = msg || "Đã kết nối API (qua proxy.php)";
    node.className = "api-status ok";
  }

  function markApiError(err) {
    clearBusyHard();
    const node = el("apiStatus");
    if (!node) return;
    node.textContent = `Không kết nối được api.py (${err.message || err}). Hãy chạy start_api.bat.`;
    node.className = "api-status error";
  }

  const PRICE_ALERT_KEY = "setup-price-alerts";
  const PRICE_ALERT_SCHEDULE_KEY = "setup-price-alert-schedule";
  const PRICE_ALERT_POLL_MS = 60000;
  let priceAlertBusy = false;
  let priceAlertTimer = null;
  let lastPriceAlertAt = 0;
  let nextPriceAlertAt = 0;

  function loadPriceAlertScheduleState() {
    try {
      const raw = localStorage.getItem(PRICE_ALERT_SCHEDULE_KEY);
      const data = raw ? JSON.parse(raw) : null;
      if (!data || typeof data !== "object") return;
      const lastAt = Number(data.lastAt || 0);
      const nextAt = Number(data.nextAt || 0);
      if (Number.isFinite(lastAt) && lastAt > 0) {
        lastPriceAlertAt = lastAt;
      }
      if (Number.isFinite(nextAt) && nextAt > 0) {
        nextPriceAlertAt = nextAt;
      }
    } catch (err) {
      /* ignore */
    }
  }

  function savePriceAlertScheduleState() {
    try {
      localStorage.setItem(
        PRICE_ALERT_SCHEDULE_KEY,
        JSON.stringify({
          lastAt: lastPriceAlertAt || 0,
          nextAt: nextPriceAlertAt || 0,
        }),
      );
    } catch (err) {
      /* ignore */
    }
  }

  function getPriceAlertSchedule() {
    return {
      intervalMs: PRICE_ALERT_POLL_MS,
      lastAt: lastPriceAlertAt,
      nextAt: nextPriceAlertAt,
      busy: priceAlertBusy,
    };
  }

  function markPriceAlertSchedule() {
    lastPriceAlertAt = Date.now();
    nextPriceAlertAt = lastPriceAlertAt + PRICE_ALERT_POLL_MS;
    savePriceAlertScheduleState();
    window.dispatchEvent(new CustomEvent("setup-alerts-schedule"));
  }

  function loadPriceAlerts() {
    try {
      const raw = localStorage.getItem(PRICE_ALERT_KEY);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (err) {
      return [];
    }
  }

  function savePriceAlerts(list) {
    localStorage.setItem(PRICE_ALERT_KEY, JSON.stringify(list));
    window.dispatchEvent(new CustomEvent("setup-alerts-updated"));
  }

  function ensureToastStack() {
    let stack = document.getElementById("setupToastStack");
    if (!stack) {
      stack = document.createElement("div");
      stack.id = "setupToastStack";
      stack.className = "setup-toast-stack";
      document.body.appendChild(stack);
    }
    return stack;
  }

  function playAlertBeep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      gain.gain.value = 0.08;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.35);
    } catch (err) {
      /* ignore */
    }
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showCornerToast({ title, body }) {
    const stack = ensureToastStack();
    const toast = document.createElement("div");
    toast.className = "setup-toast";
    toast.innerHTML =
      `<strong>${escapeHtml(title)}</strong>` +
      (body ? `<p>${escapeHtml(body)}</p>` : "") +
      `<button type="button" class="setup-toast-close" aria-label="Đóng">×</button>`;
    const close = () => toast.remove();
    toast.querySelector(".setup-toast-close").addEventListener("click", close);
    stack.appendChild(toast);
    setTimeout(close, 20000);
  }

  function showChromeNotification(title, body, { tag } = {}) {
    if (!("Notification" in window)) {
      console.log("[Timer] trinh duyet khong ho tro Notification API");
      return false;
    }
    if (Notification.permission !== "granted") {
      console.log(
        `[Timer] chua co quyen Chrome notification (permission=${Notification.permission})`,
      );
      return false;
    }
    try {
      const note = new Notification(title, {
        body: body || "",
        requireInteraction: true,
        silent: false,
        tag: tag || `setup-timer-${Date.now()}`,
      });
      note.onclick = () => {
        try {
          window.focus();
        } catch (err) {
          /* ignore */
        }
        note.close();
      };
      console.log(`[Timer ${formatPollTime()}] da gui Chrome notification: ${title}`);
      return true;
    } catch (err) {
      console.log(`[Timer] loi gui Chrome notification: ${err.message || err}`);
      return false;
    }
  }

  async function ensureChromeNotifyPermission() {
    if (!("Notification" in window)) return "unsupported";
    if (Notification.permission === "granted") return "granted";
    if (Notification.permission === "denied") return "denied";
    try {
      return await Notification.requestPermission();
    } catch (err) {
      return Notification.permission || "denied";
    }
  }

  function notifyPriceAlert(alert, quote) {
    const title = "Setup Key Level";
    const body = "";

    playAlertBeep();
    const sent = showChromeNotification(title, body, { tag: `setup-alert-${alert.id}` });
    // Toast trong trang chỉ là dự phòng khi chưa cho phép Chrome notification.
    if (!sent) {
      showCornerToast({
        title,
        body: "Bấm \"Bật thông báo Chrome\" trên trang Timer để nhận popup hệ thống.",
      });
    }
  }

  function quoteHitsZone(quote, alert) {
    const low = Math.min(Number(alert.zoneLow), Number(alert.zoneHigh));
    const high = Math.max(Number(alert.zoneLow), Number(alert.zoneHigh));
    if (!Number.isFinite(low) || !Number.isFinite(high)) return false;
    // Nến M1: chạm vùng nếu high/low của nến giao với [low, high].
    if (quote.high != null && quote.low != null) {
      return !(Number(quote.high) < low || Number(quote.low) > high);
    }
    return !(quote.ask < low || quote.bid > high);
  }

  function formatPollTime(date = new Date()) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }

  async function pollPriceAlerts() {
    if (priceAlertBusy || document.visibilityState === "hidden") return;
    const now = new Date();
    const timeLabel = formatPollTime(now);
    const alerts = loadPriceAlerts();
    // Luôn cập nhật giá cho mọi alert đang bật (kể cả đã fired).
    const enabled = alerts.filter((a) => a.enabled);
    if (!enabled.length) {
      console.log(`[Timer ${timeLabel}] dang chay — chua co bao thuc nao dang bat`);
      markPriceAlertSchedule();
      return;
    }

    priceAlertBusy = true;
    window.dispatchEvent(new CustomEvent("setup-alerts-schedule"));
    try {
      const keys = [...new Set(enabled.map((a) => `${a.account}\t${a.symbol}`))];
      const quotes = {};
      for (const key of keys) {
        const [account, symbol] = key.split("\t");
        try {
          // Nến M1 đã đóng gần nhất — không dùng tick live của /api/quote.
          const q = new URLSearchParams({ account, symbol, closed: "1" });
          const data = await apiGet(`/api/candle?${q}`, { useCache: false, timeoutMs: 30000 });
          quotes[key] = data;
          console.log(
            `[Timer ${timeLabel}] nen M1 da dong ${account} ${data.symbol || symbol}` +
              ` @ ${data.time_str}: O=${data.open} H=${data.high} L=${data.low} C=${data.close}`,
          );
        } catch (err) {
          const msg = String(err.message || err);
          quotes[key] = { error: msg };
          console.log(`[Timer ${timeLabel}] loi lay nen M1 ${account} ${symbol}: ${msg}`);
        }
      }

      const next = loadPriceAlerts().map((alert) => {
        if (!alert.enabled) return alert;
        const quote = quotes[`${alert.account}\t${alert.symbol}`];
        if (!quote || quote.error) {
          return { ...alert, lastError: quote ? quote.error : "no quote", lastAt: now.getTime() };
        }
        const inside = quoteHitsZone(quote, alert);
        const updated = {
          ...alert,
          lastBid: quote.close != null ? quote.close : quote.bid,
          lastAsk: quote.close != null ? quote.close : quote.ask,
          lastOpen: quote.open,
          lastHigh: quote.high,
          lastLow: quote.low,
          lastClose: quote.close,
          lastCandleTime: quote.time_str || "",
          lastSymbol: quote.symbol,
          lastAt: now.getTime(),
          lastError: "",
          inside,
        };
        // Da bao roi: van cap nhat gia, khong thong bao lai.
        if (alert.fired) return updated;
        if (!alert.primed) {
          updated.primed = true;
          return updated;
        }
        if (inside && !alert.inside) {
          updated.fired = true;
          updated.firedAt = now.getTime();
          console.log(
            `[Timer ${timeLabel}] CHAM VUNG ${alert.symbol} ` +
              `${alert.zoneLow}-${alert.zoneHigh} (M1 ${quote.time_str}` +
              ` H=${quote.high} L=${quote.low} C=${quote.close})`,
          );
          notifyPriceAlert(updated, {
            bid: quote.close,
            ask: quote.close,
            high: quote.high,
            low: quote.low,
            time_str: quote.time_str,
          });
        }
        return updated;
      });
      savePriceAlerts(next);
    } finally {
      priceAlertBusy = false;
      markPriceAlertSchedule();
    }
  }

  function startPriceAlertWatcher() {
    if (priceAlertTimer) return;
    loadPriceAlertScheduleState();
    console.log(
      `[Timer ${formatPollTime()}] bat dau theo doi gia (moi ${PRICE_ALERT_POLL_MS / 1000}s)`,
    );
    if (!nextPriceAlertAt || nextPriceAlertAt <= 0) {
      nextPriceAlertAt = Date.now() + PRICE_ALERT_POLL_MS;
      savePriceAlertScheduleState();
    }
    window.dispatchEvent(new CustomEvent("setup-alerts-schedule"));
    priceAlertTimer = setInterval(pollPriceAlerts, PRICE_ALERT_POLL_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") pollPriceAlerts();
    });
    pollPriceAlerts();
  }

  global.MT5 = {
    PROXY_URL,
    el,
    initTheme,
    toggleTheme,
    setBusy,
    withBusy,
    clearBusyHard,
    apiGet,
    apiPost,
    apiPut,
    apiDelete,
    clearApiCache,
    loadWithRetry,
    debounce,
    onVisibleRefresh,
    markApiOk,
    markApiError,
    loadPriceAlerts,
    savePriceAlerts,
    startPriceAlertWatcher,
    showCornerToast,
    showChromeNotification,
    ensureChromeNotifyPermission,
    getPriceAlertSchedule,
  };
})(window);

document.addEventListener("DOMContentLoaded", () => {
  if (window.MT5 && window.MT5.startPriceAlertWatcher) {
    window.MT5.startPriceAlertWatcher();
  }
});
