(function () {
  "use strict";
  var version = window.TICK_ASSET_VER;
  if (typeof version !== "string" || !/^\d+$/.test(version)) version = "0";

  function fail(src) {
    var el = document.getElementById("loadError");
    if (!el) return;
    el.textContent = "Không tải được " + src + ".";
    el.classList.remove("hidden");
  }

  var script = document.createElement("script");
  script.src = "app.js?v=" + version;
  script.onerror = function () { fail("app.js"); };
  document.body.appendChild(script);
})();
