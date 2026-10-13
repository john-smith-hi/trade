(function () {
  "use strict";
  try {
    var theme = localStorage.getItem("mt5-theme");
    if (theme === "dark" || theme === "light") {
      document.documentElement.setAttribute("data-theme", theme);
    }
  } catch (e) {}
})();
