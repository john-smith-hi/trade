(function () {
  "use strict";
  var raw = window.HISTORY_ASSET_VER;
  var version = "0";
  if (typeof raw === "number" && isFinite(raw) && raw >= 0) version = String(Math.floor(raw));
  else if (typeof raw === "string" && /^\d+$/.test(raw)) version = raw;
  window.HISTORY_ASSET_VER = version;
  var link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "style.css?v=" + version;
  document.head.appendChild(link);
})();
