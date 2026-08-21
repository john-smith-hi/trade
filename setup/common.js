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
          throw new Error(
            "API timeout — trên ĐÚNG máy đang chạy ngrok/WAMP: chạy start_server.bat và xem có dòng Running on 127.0.0.1:5001",
          );
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
    node.textContent = `Không kết nối được api.py (${err.message || err}). WAMP+ngrok+API phải cùng máy — chạy start_server.bat trên máy đó.`;
    node.className = "api-status error";
  }

  const PRICE_ALERT_KEY = "setup-price-alerts";
  const PRICE_ALERT_POLL_MS = 30000;
  const PRICE_ALERT_REFRESH_MS = 15000;
  let priceAlertTimer = null;
  let priceAlertsCache = [];
  let persistBusy = false;
  let persistSeq = 0;
  let priceAlertsHydrated = false;
  let priceAlertsDirty = false;

  function getPriceAlertSchedule() {
    const lastAt = priceAlertsCache.reduce((max, alert) => {
      const value = Number(alert && alert.lastAt) || 0;
      return value > max ? value : max;
    }, 0);
    return {
      intervalMs: PRICE_ALERT_POLL_MS,
      lastAt,
      nextAt: lastAt > 0 ? lastAt + PRICE_ALERT_POLL_MS : 0,
      busy: false,
      server: true,
    };
  }

  function loadPriceAlertsFromLocal() {
    try {
      const raw = localStorage.getItem(PRICE_ALERT_KEY);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (err) {
      return [];
    }
  }

  function loadPriceAlerts() {
    return priceAlertsCache;
  }

  async function persistPriceAlertsToXml() {
    if (!priceAlertsHydrated) return;
    persistSeq += 1;
    if (persistBusy) return;
    persistBusy = true;
    try {
      while (true) {
        const seq = persistSeq;
        const snapshot = priceAlertsCache;
        try {
          await apiPut("/api/setup/timer", { alerts: snapshot });
          priceAlertsDirty = false;
        } catch (err) {
          console.log(
            `[Timer ${formatPollTime()}] loi luu xml/timer.xml: ${err.message || err}`,
          );
          try {
            localStorage.setItem(PRICE_ALERT_KEY, JSON.stringify(snapshot));
          } catch (storeErr) {
            /* ignore */
          }
        }
        if (seq === persistSeq) break;
      }
    } finally {
      persistBusy = false;
    }
  }

  function savePriceAlerts(list) {
    priceAlertsCache = Array.isArray(list) ? list : [];
    priceAlertsDirty = true;
    window.dispatchEvent(new CustomEvent("setup-alerts-updated"));
    persistPriceAlertsToXml();
  }

  function mergeAlertLists(localFirst, serverList) {
    const seen = new Set();
    const merged = [];
    for (const alert of localFirst) {
      if (!alert || !alert.id || seen.has(alert.id)) continue;
      merged.push(alert);
      seen.add(alert.id);
    }
    for (const alert of serverList) {
      if (!alert || !alert.id || seen.has(alert.id)) continue;
      merged.push(alert);
      seen.add(alert.id);
    }
    return merged;
  }

  async function hydratePriceAlerts() {
    const data = await apiGet("/api/setup/timer", { useCache: false });
    let list = Array.isArray(data.alerts) ? data.alerts : [];
    if (!list.length) {
      const local = loadPriceAlertsFromLocal();
      if (local.length) {
        list = local;
        priceAlertsDirty = true;
      }
    }
    if (priceAlertsDirty && priceAlertsCache.length) {
      list = mergeAlertLists(priceAlertsCache, list);
    }
    priceAlertsCache = list;
    priceAlertsHydrated = true;
    try {
      localStorage.removeItem(PRICE_ALERT_KEY);
    } catch (err) {
      /* ignore */
    }
    window.dispatchEvent(new CustomEvent("setup-alerts-updated"));
    if (priceAlertsDirty) {
      persistPriceAlertsToXml();
    }
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

  function formatPollTime(date = new Date()) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }

  async function refreshPriceAlertsFromServer() {
    if (priceAlertsDirty || persistBusy) return;
    try {
      const data = await apiGet("/api/setup/timer", { useCache: false });
      if (priceAlertsDirty) return;
      priceAlertsCache = Array.isArray(data.alerts) ? data.alerts : [];
      window.dispatchEvent(new CustomEvent("setup-alerts-updated"));
      window.dispatchEvent(new CustomEvent("setup-alerts-schedule"));
    } catch (err) {
      console.log(`[Timer ${formatPollTime()}] khong tai xml/timer.xml: ${err.message || err}`);
    }
  }

  async function startPriceAlertWatcher() {
    if (priceAlertTimer) return;
    try {
      await hydratePriceAlerts();
    } catch (err) {
      const local = loadPriceAlertsFromLocal();
      if (local.length) {
        priceAlertsCache = local;
        priceAlertsDirty = true;
        window.dispatchEvent(new CustomEvent("setup-alerts-updated"));
      }
      priceAlertsHydrated = true;
      console.log(`[Timer ${formatPollTime()}] khong tai xml/timer.xml: ${err.message || err}`);
      if (priceAlertsDirty) persistPriceAlertsToXml();
    }
    window.dispatchEvent(new CustomEvent("setup-alerts-schedule"));
    priceAlertTimer = setInterval(refreshPriceAlertsFromServer, PRICE_ALERT_REFRESH_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") refreshPriceAlertsFromServer();
    });
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
    getPriceAlertSchedule,
  };
})(window);

document.addEventListener("DOMContentLoaded", () => {
  if (window.MT5 && window.MT5.startPriceAlertWatcher) {
    window.MT5.startPriceAlertWatcher();
  }
});
