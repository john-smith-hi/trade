(function () {
  "use strict";

  var WEEKDAY_LABELS = {
    1: "Thứ 2", 2: "Thứ 3", 3: "Thứ 4", 4: "Thứ 5",
    5: "Thứ 6", 6: "Thứ 7", 7: "Chủ nhật",
  };

  var state = {
    week: null,
    weekday: null,
    canTrade: false,
    editingSetupId: null,
    quoteSeq: 0,
  };

  var ACCOUNT_KEY = "setup-quote-account";

  var el = {};

  function $(id) {
    return document.getElementById(id);
  }

  function cacheEls() {
    [
      "apiStatus", "weekBanner", "weekendCard", "mainCard",
      "mondayNotice", "closedNotice",
      "mondayHigh", "mondayLow", "prevHigh", "prevLow",
      "trendD1", "trendH4", "newsNotes", "btnSaveWeek", "weekSaveHint",
      "setupFormTitle", "account", "symbol", "side", "tradeRangeField", "tradeRange",
      "zoneConfirmed", "noChase", "structureBreak", "structurePatternHint",
      "entry", "btnFetchEntry", "entryHint", "sl", "tp", "rrHint", "newsOk", "commitClose",
      "btnCheck", "btnReset", "resultBox", "resultTitle", "resultFails",
      "setupTableBody", "themeToggle",
    ].forEach(function (id) { el[id] = $(id); });
  }

  function setApiStatus(text, ok) {
    el.apiStatus.textContent = text;
    el.apiStatus.style.color = ok === true ? "var(--ok)" : ok === false ? "var(--error)" : "";
  }

  function formatDate(iso) {
    if (!iso) return "--";
    var parts = iso.split("-");
    if (parts.length !== 3) return iso;
    return parts[2] + "/" + parts[1];
  }

  function api(path, options) {
    options = options || {};
    var opts = {
      method: options.method || "GET",
      headers: { "Content-Type": "application/json" },
    };
    if (options.body !== undefined) {
      opts.body = JSON.stringify(options.body);
    }
    return fetch(path, opts).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) {
          throw new Error(data.error || ("Lỗi HTTP " + res.status));
        }
        return data;
      });
    });
  }

  function numOrEmpty(value) {
    return value === null || value === undefined ? "" : value;
  }

  function computeRR(side, entry, sl, tp) {
    if ([entry, sl, tp].some(function (v) { return v === null || v === "" || Number.isNaN(v); })) {
      return null;
    }
    var risk, reward;
    if (side === "buy") {
      risk = entry - sl;
      reward = tp - entry;
    } else {
      risk = sl - entry;
      reward = entry - tp;
    }
    if (risk <= 0 || reward <= 0) return null;
    return reward / risk;
  }

  function updateStructureHint() {
    var side = el.side.value;
    var expected = side === "buy" ? "HL (Higher Low)" : "LH (Lower High)";
    el.structurePatternHint.textContent = "Cần thấy " + expected + " hình thành trước khi vào " + side.toUpperCase() + ".";
  }

  function updateTradeRangeVisibility() {
    var isSideway = (state.week && state.week.trend_d1) === "sideway";
    el.tradeRangeField.classList.toggle("hidden", !isSideway);
  }

  function updateRRPreview() {
    var side = el.side.value;
    var entry = parseFloat(el.entry.value);
    var sl = parseFloat(el.sl.value);
    var tp = parseFloat(el.tp.value);
    var rr = computeRR(side, entry, sl, tp);
    if (rr === null) {
      el.rrHint.textContent = "RR: -- (cần Entry/SL/TP hợp lệ theo hướng lệnh)";
      el.rrHint.classList.remove("hint-error");
    } else {
      el.rrHint.textContent = "RR: 1 : " + rr.toFixed(2) + (rr >= 2 ? "  ✓ đạt tối thiểu 1:2" : "  ✗ chưa đạt 1:2");
    }
  }

  function renderWeekBanner() {
    var week = state.week;
    if (!week) {
      el.weekBanner.textContent = "Chưa có tuần nào đang hoạt động.";
      return;
    }
    var statusLabel = week.status === "active" ? "Đang hoạt động" : "Đã đóng";
    var pillClass = week.status === "active" ? "pill-active" : "pill-closed";
    el.weekBanner.innerHTML =
      week.id + " · " + WEEKDAY_LABELS[state.weekday] + " · Thứ 2 " + formatDate(week.week_start) +
      " – Thứ 6 " + formatDate(week.week_end) +
      ' <span class="pill ' + pillClass + '">' + statusLabel + "</span>";
  }

  function fillObservationForm(week) {
    el.mondayHigh.value = numOrEmpty(week.monday_high);
    el.mondayLow.value = numOrEmpty(week.monday_low);
    el.prevHigh.value = numOrEmpty(week.prev_week_high);
    el.prevLow.value = numOrEmpty(week.prev_week_low);
    el.trendD1.value = week.trend_d1 || "";
    el.trendH4.value = week.trend_h4 || "";
    el.newsNotes.value = week.news_notes || "";
  }

  function setFormDisabled(disabled) {
    [
      el.mondayHigh, el.mondayLow, el.prevHigh, el.prevLow, el.trendD1, el.trendH4, el.newsNotes,
      el.btnSaveWeek, el.account, el.symbol, el.side, el.tradeRange, el.zoneConfirmed, el.noChase,
      el.structureBreak, el.entry, el.btnFetchEntry, el.sl, el.tp, el.newsOk, el.commitClose,
      el.btnCheck, el.btnReset,
    ].forEach(function (node) { if (node) node.disabled = disabled; });
    document.querySelectorAll(".reaction").forEach(function (node) { node.disabled = disabled; });
  }

  function setEntryHint(text, asError) {
    el.entryHint.textContent = text || "";
    el.entryHint.classList.toggle("hint-error", !!asError && !!text);
  }

  function loadAccounts() {
    return api("/api/accounts").then(function (data) {
      var accounts = data.accounts || [];
      var saved = localStorage.getItem(ACCOUNT_KEY) || "";
      el.account.innerHTML = "";
      if (!accounts.length) {
        el.account.innerHTML = '<option value="">-- chưa có account --</option>';
        setEntryHint("Chưa có account trong accounts.xml — không lấy được giá.", true);
        return;
      }
      accounts.forEach(function (acc) {
        var opt = document.createElement("option");
        opt.value = acc.name;
        opt.textContent = acc.name + (acc.server ? " (" + acc.server + ")" : "");
        el.account.appendChild(opt);
      });
      if (saved && accounts.some(function (a) { return a.name === saved; })) {
        el.account.value = saved;
      }
    }).catch(function (err) {
      setEntryHint("Không tải được danh sách account: " + err.message, true);
    });
  }

  function fetchEntryQuote() {
    var account = el.account.value;
    var symbol = (el.symbol.value || "").trim();
    var side = el.side.value;
    if (!account) {
      setEntryHint("Chọn account để lấy giá.", true);
      return;
    }
    if (!symbol) {
      setEntryHint("Nhập symbol để lấy giá.", true);
      return;
    }

    var seq = ++state.quoteSeq;
    setEntryHint("Đang lấy giá thị trường...");
    el.btnFetchEntry.disabled = true;

    var q = "/api/quote?account=" + encodeURIComponent(account)
      + "&symbol=" + encodeURIComponent(symbol)
      + "&side=" + encodeURIComponent(side);

    api(q).then(function (data) {
      if (seq !== state.quoteSeq) return;
      el.entry.value = data.entry;
      updateRRPreview();
      setEntryHint(
        "Quote " + data.symbol + ": bid=" + data.bid + " ask=" + data.ask
        + " → entry " + side.toUpperCase() + "=" + data.entry
      );
    }).catch(function (err) {
      if (seq !== state.quoteSeq) return;
      setEntryHint("Không lấy được giá: " + err.message, true);
    }).then(function () {
      if (seq !== state.quoteSeq) return;
      var closed = state.week && state.week.status !== "active";
      el.btnFetchEntry.disabled = !!closed;
    });
  }

  function renderSetupsTable(setups) {
    var body = el.setupTableBody;
    body.innerHTML = "";
    if (!setups || !setups.length) {
      body.innerHTML = '<tr class="empty-row"><td colspan="6">Chưa có setup nào trong tuần này</td></tr>';
      return;
    }
    setups.slice().reverse().forEach(function (setup) {
      var tr = document.createElement("tr");
      var time = (setup.created_at || "").replace("T", " ").slice(0, 16);
      var rrText = setup.rr === null || setup.rr === undefined ? "--" : setup.rr.toFixed(2);
      var statusClass = setup.result === "pass" ? "status-pass" : "status-fail";
      var statusText = setup.result === "pass" ? "PASS" : "FAIL";

      tr.innerHTML =
        "<td>" + time + "</td>" +
        "<td>" + setup.symbol + "</td>" +
        "<td>" + setup.side.toUpperCase() + "</td>" +
        "<td>" + rrText + "</td>" +
        '<td><span class="status-pill ' + statusClass + '">' + statusText + "</span></td>" +
        '<td class="row-actions"></td>';

      var actionsCell = tr.querySelector(".row-actions");
      if (state.week.status === "active") {
        var editBtn = document.createElement("button");
        editBtn.type = "button";
        editBtn.className = "btn btn-secondary";
        editBtn.textContent = "Sửa";
        editBtn.addEventListener("click", function () { loadSetupIntoForm(setup); });

        var delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "btn-danger-outline";
        delBtn.textContent = "Xóa";
        delBtn.addEventListener("click", function () { deleteSetup(setup.id); });

        actionsCell.appendChild(editBtn);
        actionsCell.appendChild(delBtn);
      }
      body.appendChild(tr);
    });
  }

  function render(data) {
    state.week = data.week;
    state.weekday = data.weekday;
    state.canTrade = data.can_trade;

    el.weekendCard.classList.toggle("hidden", !!data.week);
    el.mainCard.classList.toggle("hidden", !data.week);

    if (!data.week) {
      setApiStatus("Kết nối OK — cuối tuần, chưa có tuần mới.", true);
      return;
    }

    setApiStatus("Kết nối OK", true);
    renderWeekBanner();
    fillObservationForm(data.week);
    updateTradeRangeVisibility();
    renderSetupsTable(data.week.setups);

    var isClosed = data.week.status !== "active";
    var isMonday = data.weekday === 1;

    el.closedNotice.classList.toggle("hidden", !isClosed);
    el.mondayNotice.classList.toggle("hidden", isClosed || !isMonday);

    setFormDisabled(isClosed);
    el.btnCheck.disabled = isClosed || isMonday;
  }

  function loadWeek() {
    return api("/api/setup/week").then(render).catch(function (err) {
      setApiStatus("Không kết nối được API: " + err.message, false);
    });
  }

  function saveWeekObservations() {
    var payload = {
      monday_high: el.mondayHigh.value === "" ? null : parseFloat(el.mondayHigh.value),
      monday_low: el.mondayLow.value === "" ? null : parseFloat(el.mondayLow.value),
      prev_week_high: el.prevHigh.value === "" ? null : parseFloat(el.prevHigh.value),
      prev_week_low: el.prevLow.value === "" ? null : parseFloat(el.prevLow.value),
      trend_d1: el.trendD1.value,
      trend_h4: el.trendH4.value,
      news_notes: el.newsNotes.value,
    };
    el.weekSaveHint.textContent = "Đang lưu...";
    api("/api/setup/week/" + encodeURIComponent(state.week.id), { method: "PUT", body: payload })
      .then(function (data) {
        state.week = data.week;
        updateTradeRangeVisibility();
        el.weekSaveHint.textContent = "Đã lưu lúc " + new Date().toLocaleTimeString("vi-VN");
      })
      .catch(function (err) {
        el.weekSaveHint.textContent = "Lỗi: " + err.message;
      });
  }

  function collectSetupPayload() {
    var reactions = Array.prototype.slice.call(document.querySelectorAll(".reaction:checked"))
      .map(function (node) { return node.value; });
    return {
      week_id: state.week.id,
      symbol: el.symbol.value,
      side: el.side.value,
      trade_range: el.tradeRange.checked,
      zone_confirmed: el.zoneConfirmed.checked,
      no_chase: el.noChase.checked,
      reactions: reactions,
      structure_break: el.structureBreak.checked,
      entry: el.entry.value === "" ? null : parseFloat(el.entry.value),
      sl: el.sl.value === "" ? null : parseFloat(el.sl.value),
      tp: el.tp.value === "" ? null : parseFloat(el.tp.value),
      news_ok: el.newsOk.checked,
      commit_sl_tp_close: el.commitClose.checked,
    };
  }

  function showResult(setup) {
    el.resultBox.classList.remove("hidden", "pass", "fail");
    el.resultBox.classList.add(setup.result);
    el.resultTitle.textContent = setup.result === "pass"
      ? "✓ ĐỦ ĐIỀU KIỆN VÀO LỆNH"
      : "✗ CHƯA ĐỦ ĐIỀU KIỆN — xem lý do bên dưới";
    el.resultFails.innerHTML = "";
    (setup.fails || []).forEach(function (msg) {
      var li = document.createElement("li");
      li.textContent = msg;
      el.resultFails.appendChild(li);
    });
  }

  function submitSetup() {
    var payload = collectSetupPayload();
    var request = state.editingSetupId
      ? api("/api/setup/setups/" + encodeURIComponent(state.editingSetupId), { method: "PUT", body: payload })
      : api("/api/setup/setups", { method: "POST", body: payload });

    request.then(function (data) {
      state.week = data.week;
      showResult(data.setup);
      renderSetupsTable(data.week.setups);
      exitEditMode();
    }).catch(function (err) {
      el.resultBox.classList.remove("hidden", "pass");
      el.resultBox.classList.add("fail");
      el.resultTitle.textContent = "Lỗi";
      el.resultFails.innerHTML = "<li>" + err.message + "</li>";
    });
  }

  function loadSetupIntoForm(setup) {
    state.editingSetupId = setup.id;
    el.setupFormTitle.textContent = "Sửa setup #" + setup.id;
    el.btnCheck.textContent = "Chấm điểm & cập nhật setup";
    el.symbol.value = setup.symbol;
    el.side.value = setup.side;
    el.tradeRange.checked = !!setup.trade_range;
    var checklist = setup.checklist || {};
    el.zoneConfirmed.checked = !!(checklist["3"] && checklist["3"].ok);
    el.noChase.checked = !!(checklist["4"] && checklist["4"].ok);
    el.structureBreak.checked = !!(checklist["6"] && checklist["6"].ok);
    el.newsOk.checked = !!(checklist["8"] && checklist["8"].ok);
    el.commitClose.checked = !!(checklist["10"] && checklist["10"].ok);
    el.entry.value = numOrEmpty(setup.entry);
    el.sl.value = numOrEmpty(setup.sl);
    el.tp.value = numOrEmpty(setup.tp);
    document.querySelectorAll(".reaction").forEach(function (node) { node.checked = false; });
    // Reaction checkboxes bị gộp thành pass/fail khi lưu — không khôi phục lại lựa chọn cũ,
    // người dùng tick lại nếu vẫn còn đúng khi sửa.
    updateStructureHint();
    updateRRPreview();
    el.resultBox.classList.add("hidden");
    window.scrollTo({ top: el.setupFormTitle.offsetTop - 20, behavior: "smooth" });
  }

  function exitEditMode() {
    state.editingSetupId = null;
    el.setupFormTitle.textContent = "Chấm điểm setup trước khi vào lệnh";
    el.btnCheck.textContent = "Chấm điểm & lưu setup";
  }

  function deleteSetup(setupId) {
    if (!window.confirm("Xóa setup #" + setupId + "?")) return;
    api("/api/setup/setups/" + encodeURIComponent(setupId) + "?week_id=" + encodeURIComponent(state.week.id), { method: "DELETE" })
      .then(function (data) {
        state.week = data.week;
        renderSetupsTable(data.week.setups);
        if (state.editingSetupId === setupId) exitEditMode();
      })
      .catch(function (err) {
        window.alert("Lỗi xóa: " + err.message);
      });
  }

  function resetForm() {
    el.zoneConfirmed.checked = false;
    el.noChase.checked = false;
    el.structureBreak.checked = false;
    el.newsOk.checked = false;
    el.commitClose.checked = false;
    el.tradeRange.checked = false;
    document.querySelectorAll(".reaction").forEach(function (node) { node.checked = false; });
    el.entry.value = "";
    el.sl.value = "";
    el.tp.value = "";
    setEntryHint("");
    updateRRPreview();
    el.resultBox.classList.add("hidden");
    exitEditMode();
  }

  var THEME_KEY = "setup-theme";

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    if (el.themeToggle) {
      el.themeToggle.textContent = theme === "dark" ? "Chế độ sáng" : "Chế độ tối";
    }
  }

  function initTheme() {
    var saved = localStorage.getItem(THEME_KEY);
    applyTheme(saved === "dark" ? "dark" : "light");
  }

  function toggleTheme() {
    var current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    var next = current === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  }

  function bindEvents() {
    el.themeToggle.addEventListener("click", toggleTheme);
    el.btnSaveWeek.addEventListener("click", saveWeekObservations);
    el.btnCheck.addEventListener("click", submitSetup);
    el.btnReset.addEventListener("click", resetForm);
    el.btnFetchEntry.addEventListener("click", fetchEntryQuote);
    el.account.addEventListener("change", function () {
      localStorage.setItem(ACCOUNT_KEY, el.account.value);
      fetchEntryQuote();
    });
    el.side.addEventListener("change", function () {
      updateStructureHint();
      updateRRPreview();
      fetchEntryQuote();
    });
    el.symbol.addEventListener("change", fetchEntryQuote);
    [el.entry, el.sl, el.tp].forEach(function (input) {
      input.addEventListener("input", updateRRPreview);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    cacheEls();
    initTheme();
    bindEvents();
    updateStructureHint();
    updateRRPreview();
    loadAccounts().then(function () {
      loadWeek().then(function () {
        if (el.account.value && el.symbol.value.trim()) {
          fetchEntryQuote();
        }
      });
    });
  });
})();
