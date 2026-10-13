(function () {
  "use strict";

  const state = {
    bid: [],
    ask: [],
    count: 0,
    viewMin: 0,
    viewMax: 60,
    drag: null,
    meta: null,
  };

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function setStatus(msg, kind) {
    const el = $("status");
    el.textContent = msg;
    el.className = "status" + (kind ? " " + kind : "");
  }

  function setError(msg) {
    const el = $("loadError");
    if (!msg) {
      el.textContent = "";
      el.classList.add("hidden");
      return;
    }
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  function resetView() {
    if (!state.bid.length) {
      state.viewMin = 0;
      state.viewMax = 60;
      return;
    }
    const last = state.bid[state.bid.length - 1][0];
    state.viewMin = 0;
    state.viewMax = Math.max(last, 1);
  }

  async function loadData() {
    setError("");
    setStatus("Đang đọc CSV…", "busy");
    const qs = new URLSearchParams({
      date: $("filterDate").value.trim(),
      from: $("filterFrom").value.trim(),
      to: $("filterTo").value.trim(),
    });
    const res = await fetch("query.php?" + qs.toString());
    const data = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
    state.bid = data.bid || [];
    state.ask = data.ask || [];
    state.count = data.count || 0;
    state.meta = data;
    resetView();
    const m = $("meta");
    if (state.count === 0) {
      m.textContent = "Không có tick trong khoảng đã chọn.";
      setStatus("Không có dữ liệu", "warn");
    } else {
      m.textContent = data.file + " · " + state.count + " tick · " + data.from_vn + " → " + data.to_vn
        + (state.bid.length < state.count ? " (đồ thị " + state.bid.length + " điểm)" : "");
      setStatus("Sẵn sàng · " + state.count + " tick", "ok");
    }
    renderTable(data.rows || []);
    drawChart();
  }

  function renderTable(rows) {
    const card = $("tableCard");
    const wrap = $("tableWrap");
    if (!rows.length) {
      card.classList.add("hidden");
      wrap.innerHTML = "";
      return;
    }
    card.classList.remove("hidden");
    let html = "<table><thead><tr><th>Giờ VN</th><th>Bid</th><th>Ask</th><th>Spread</th></tr></thead><tbody>";
    rows.forEach(function (r) {
      html += "<tr><td>" + esc(r.ts_vn) + "</td><td>" + esc(r.bid) + "</td><td>" + esc(r.ask)
        + "</td><td>" + esc(r.spread) + "</td></tr>";
    });
    html += "</tbody></table>";
    wrap.innerHTML = html;
  }

  function chartGeom() {
    const canvas = $("chart");
    const wrap = canvas.parentElement;
    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(320, wrap.clientWidth);
    const h = Math.max(220, Math.min(420, Math.round(w * 0.45)));
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const pad = { l: 52, r: 16, t: 12, b: 32 };
    return { ctx, w, h, pad };
  }

  function yRange(viewMin, viewMax) {
    let ymin = Infinity;
    let ymax = -Infinity;
    function scan(arr) {
      for (let i = 0; i < arr.length; i++) {
        const x = arr[i][0];
        if (x < viewMin || x > viewMax) continue;
        const y = arr[i][1];
        if (y < ymin) ymin = y;
        if (y > ymax) ymax = y;
      }
    }
    scan(state.bid);
    scan(state.ask);
    if (!Number.isFinite(ymin)) {
      ymin = 0;
      ymax = 1;
    }
    const pad = (ymax - ymin) * 0.06 || 1;
    return [ymin - pad, ymax + pad];
  }

  function drawChart(hoverX) {
    const canvas = $("chart");
    const g = chartGeom();
    const ctx = g.ctx;
    ctx.clearRect(0, 0, g.w, g.h);
    const plotW = g.w - g.pad.l - g.pad.r;
    const plotH = g.h - g.pad.t - g.pad.b;
    const vmin = state.viewMin;
    const vmax = state.viewMax;
    const span = Math.max(vmax - vmin, 0.001);
    const yr = yRange(vmin, vmax);

    function xPx(x) { return g.pad.l + ((x - vmin) / span) * plotW; }
    function yPx(y) { return g.pad.t + (1 - (y - yr[0]) / (yr[1] - yr[0])) * plotH; }

    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--border") || "#ccc";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = g.pad.t + (plotH * i) / 5;
      ctx.beginPath();
      ctx.moveTo(g.pad.l, y);
      ctx.lineTo(g.w - g.pad.r, y);
      ctx.stroke();
    }
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--muted") || "#666";
    ctx.font = "11px Segoe UI, sans-serif";
    ctx.textAlign = "right";
    for (let i = 0; i <= 5; i++) {
      const val = yr[0] + ((yr[1] - yr[0]) * (5 - i)) / 5;
      const y = g.pad.t + (plotH * i) / 5;
      ctx.fillText(val.toFixed(2), g.pad.l - 6, y + 4);
    }
    ctx.textAlign = "center";
    for (let i = 0; i <= 5; i++) {
      const t = vmin + (span * i) / 5;
      const x = g.pad.l + (plotW * i) / 5;
      ctx.fillText(t.toFixed(1) + "s", x, g.h - 8);
    }

    function line(arr, color) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < arr.length; i++) {
        const x = arr[i][0];
        if (x < vmin || x > vmax) continue;
        const px = xPx(x);
        const py = yPx(arr[i][1]);
        if (!started) {
          ctx.moveTo(px, py);
          started = true;
        } else {
          ctx.lineTo(px, py);
        }
      }
      ctx.stroke();
    }
    line(state.bid, "#2563eb");
    line(state.ask, "#dc2626");

    if (hoverX != null && hoverX >= vmin && hoverX <= vmax) {
      const hx = xPx(hoverX);
      ctx.strokeStyle = "rgba(100,116,139,0.6)";
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(hx, g.pad.t);
      ctx.lineTo(hx, g.h - g.pad.b);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  function nearestX(clientX) {
    const canvas = $("chart");
    const rect = canvas.getBoundingClientRect();
    const g = chartGeom();
    const plotW = g.w - g.pad.l - g.pad.r;
    const rel = (clientX - rect.left - g.pad.l) / plotW;
    const vmin = state.viewMin;
    const vmax = state.viewMax;
    return vmin + rel * (vmax - vmin);
  }

  function showTip(clientX, clientY) {
    const tip = $("chartTip");
    if (!state.bid.length) {
      tip.classList.add("hidden");
      return;
    }
    const x = nearestX(clientX);
    let best = null;
    let bestD = Infinity;
    function scan(arr, kind) {
      for (let i = 0; i < arr.length; i++) {
        const d = Math.abs(arr[i][0] - x);
        if (d < bestD) {
          bestD = d;
          best = { sec: arr[i][0], price: arr[i][1], kind: kind };
        }
      }
    }
    scan(state.bid, "Bid");
    scan(state.ask, "Ask");
    if (!best || bestD > (state.viewMax - state.viewMin) / 40) {
      tip.classList.add("hidden");
      drawChart();
      return;
    }
    drawChart(best.sec);
    tip.classList.remove("hidden");
    tip.style.left = Math.min(clientX + 12, window.innerWidth - 160) + "px";
    tip.style.top = (clientY - 8) + "px";
    tip.innerHTML = "<strong>" + best.kind + "</strong> " + best.price.toFixed(3)
      + "<br><span class=" + '"muted">+' + best.sec.toFixed(3) + "s từ đầu khoảng</span>";
  }

  function bindChart() {
    const canvas = $("chart");
    canvas.addEventListener("mousemove", function (ev) {
      if (state.drag) return;
      showTip(ev.clientX, ev.clientY);
    });
    canvas.addEventListener("mouseleave", function () {
      $("chartTip").classList.add("hidden");
      drawChart();
    });
    canvas.addEventListener("wheel", function (ev) {
      if (!state.bid.length) return;
      ev.preventDefault();
      const x = nearestX(ev.clientX);
      const factor = ev.deltaY > 0 ? 1.12 : 0.88;
      const vmin = state.viewMin;
      const vmax = state.viewMax;
      const span = vmax - vmin;
      const newSpan = Math.max(span * factor, 0.05);
      const ratio = (x - vmin) / span;
      state.viewMin = x - newSpan * ratio;
      state.viewMax = state.viewMin + newSpan;
      drawChart();
    }, { passive: false });
    canvas.addEventListener("mousedown", function (ev) {
      if (!state.bid.length) return;
      state.drag = { x0: ev.clientX, vmin: state.viewMin, vmax: state.viewMax };
    });
    window.addEventListener("mousemove", function (ev) {
      if (!state.drag) return;
      const g = chartGeom();
      const plotW = g.w - g.pad.l - g.pad.r;
      const dx = ev.clientX - state.drag.x0;
      const span = state.drag.vmax - state.drag.vmin;
      const shift = (-dx / plotW) * span;
      state.viewMin = state.drag.vmin + shift;
      state.viewMax = state.drag.vmax + shift;
      drawChart();
    });
    window.addEventListener("mouseup", function () {
      state.drag = null;
    });
  }

  function applyPreset(btn) {
    $("filterDate").value = btn.getAttribute("data-date") || "";
    $("filterFrom").value = btn.getAttribute("data-from") || "";
    $("filterTo").value = btn.getAttribute("data-to") || "";
    loadData().catch(function (err) {
      setError(err.message || String(err));
      setStatus("Lỗi", "error");
    });
  }

  function initTheme() {
    let theme = "light";
    try {
      const saved = localStorage.getItem("mt5-theme");
      if (saved === "dark" || saved === "light") theme = saved;
    } catch (e) {}
    document.documentElement.setAttribute("data-theme", theme);
    $("themeToggle").textContent = theme === "dark" ? "Chế độ sáng" : "Chế độ tối";
  }

  function bind() {
    $("themeToggle").addEventListener("click", function () {
      const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      const next = cur === "dark" ? "light" : "dark";
      try { localStorage.setItem("mt5-theme", next); } catch (e) {}
      document.documentElement.setAttribute("data-theme", next);
      $("themeToggle").textContent = next === "dark" ? "Chế độ sáng" : "Chế độ tối";
      drawChart();
    });
    $("btnLoad").addEventListener("click", function () {
      loadData().catch(function (err) {
        setError(err.message || String(err));
        setStatus("Lỗi", "error");
      });
    });
    $("btnResetZoom").addEventListener("click", function () {
      resetView();
      drawChart();
    });
    document.querySelectorAll(".preset").forEach(function (btn) {
      btn.addEventListener("click", function () { applyPreset(btn); });
    });
    bindChart();
    window.addEventListener("resize", function () { drawChart(); });
    fetch("query.php?files=1").then(function (r) { return r.json(); }).then(function (d) {
      if (d.dir) setStatus("Dữ liệu: " + d.dir, "ok");
    }).catch(function () {
      setStatus("Chưa kiểm tra được folder CSV", "warn");
    });
    applyPreset(document.querySelector(".preset"));
  }

  initTheme();
  bind();
})();
