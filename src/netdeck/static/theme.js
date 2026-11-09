// Applied before first paint to avoid a flash of the wrong theme.
(function () {
  var pref = "system", accent = null;
  try {
    pref = JSON.parse(localStorage.getItem("netdeck.theme")) || "system";
    accent = JSON.parse(localStorage.getItem("netdeck.accent"));
  } catch (e) { /* storage blocked or malformed */ }
  var dark = pref === "dark" || (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  if (accent && /^#[0-9a-f]{6}$/i.test(accent)) document.documentElement.style.setProperty("--accent", accent);
})();
