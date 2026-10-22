(function () {
  "use strict";

  var INTERACTIVE = "a, button, input, select, textarea, label";

  function isInteractive(target) {
    return !!(target && target.closest && target.closest(INTERACTIVE));
  }

  function openTrip(row) {
    var url = row.getAttribute("data-trip-url");
    if (url) {
      window.location.href = url;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var rows = document.querySelectorAll("tr[data-trip-url]");

    rows.forEach(function (row) {
      row.addEventListener("click", function (event) {
        if (event.defaultPrevented || isInteractive(event.target)) {
          return;
        }
        openTrip(row);
      });

      // Клавіатура: рядок має tabindex, тож Enter/Space відкривають рейс.
      row.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") {
          return;
        }
        if (event.target !== row || isInteractive(event.target)) {
          return;
        }
        event.preventDefault();
        openTrip(row);
      });
    });
  });
})();
