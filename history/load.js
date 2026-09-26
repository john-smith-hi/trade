(function () {
  "use strict";
  var version = window.HISTORY_ASSET_VER;
  if (typeof version !== "string" || !/^\d+$/.test(version)) version = "0";

  function fail(src) {
    var el = document.getElementById("importError");
    if (!el) return;
    el.textContent = "Không tải được " + src + ".";
    el.classList.remove("hidden");
  }

  function add(src, next) {
    var script = document.createElement("script");
    script.src = src + "?v=" + version;
    script.onerror = function () { fail(src); };
    if (next) {
      script.onload = function () { add(next); };
    }
    document.body.appendChild(script);
  }

  add("analyze.js", "app.js");
})();
