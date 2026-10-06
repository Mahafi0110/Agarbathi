(function () {
  var menu = document.querySelector(".category-menu");
  if (!menu || !window.matchMedia) return;

  var mobile = window.matchMedia("(max-width: 800px)");
  var closeButtons = menu.querySelectorAll(".category-backdrop, .cats-close");

  function syncScrollLock() {
    document.body.style.overflow = mobile.matches && menu.open ? "hidden" : "";
  }

  function syncViewport(event) {
    menu.open = !event.matches;
    syncScrollLock();
  }

  closeButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      menu.open = false;
      syncScrollLock();
      menu.querySelector(".category-menu-toggle").focus();
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && mobile.matches && menu.open) {
      menu.open = false;
      syncScrollLock();
      menu.querySelector(".category-menu-toggle").focus();
    }
  });

  menu.addEventListener("toggle", syncScrollLock);
  syncViewport(mobile);
  if (mobile.addEventListener) mobile.addEventListener("change", syncViewport);
  else mobile.addListener(syncViewport);
})();
