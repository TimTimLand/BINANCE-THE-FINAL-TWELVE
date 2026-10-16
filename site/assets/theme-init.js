/* 在样式加载前把主题定下来，避免闪白。默认深色。 */
(function () {
  try {
    if (localStorage.getItem("b12h_theme") === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    }
  } catch (e) {}
})();
