/* BusFlow: тема, мобільне меню, іконки, повідомлення, таблиці (сортування й швидкий пошук). */
(function () {
    "use strict";

    var root = document.documentElement;

    function icons() {
        if (window.lucide && typeof window.lucide.createIcons === "function") {
            window.lucide.createIcons();
        }
    }
    window.busflowIcons = icons;

    /* ---------- Тема ---------- */
    document.addEventListener("click", function (event) {
        var toggle = event.target.closest("[data-theme-toggle]");
        if (!toggle) return;
        var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        try {
            localStorage.setItem("busflow-theme", next);
        } catch (e) {}
    });

    /* ---------- Мобільне меню ---------- */
    document.addEventListener("click", function (event) {
        var button = event.target.closest("[data-nav-toggle]");
        var header = document.getElementById("site-header");
        if (!header) return;
        if (button) {
            var open = header.classList.toggle("nav-open");
            button.setAttribute("aria-expanded", open ? "true" : "false");
            return;
        }
        if (header.classList.contains("nav-open") && !event.target.closest(".nav-links")) {
            header.classList.remove("nav-open");
        }
    });

    /* ---------- Повідомлення ---------- */
    document.addEventListener("click", function (event) {
        var close = event.target.closest("[data-dismiss]");
        if (!close) return;
        var item = close.closest("li");
        if (item) item.remove();
    });

    /* ---------- Таблиці ---------- */
    function cellValue(row, index) {
        var cell = row.cells[index];
        if (!cell) return "";
        var raw = cell.getAttribute("data-sort-value");
        return (raw !== null ? raw : cell.textContent).trim();
    }

    function initTable(table) {
        var body = table.tBodies[0];
        if (!body || !table.tHead) return;

        var rows = Array.prototype.slice.call(body.rows).filter(function (row) {
            return !row.classList.contains("empty-row");
        });
        rows.forEach(function (row, i) {
            row.setAttribute("data-original-index", i);
        });

        var headers = Array.prototype.slice.call(table.tHead.rows[0].cells);
        var emptyRow = body.querySelector(".empty-row");

        function sortBy(index, type, direction) {
            var sorted = rows.slice().sort(function (a, b) {
                if (!direction) {
                    return a.getAttribute("data-original-index") - b.getAttribute("data-original-index");
                }
                var x = cellValue(a, index);
                var y = cellValue(b, index);
                var xEmpty = x === "" || x === "-";
                var yEmpty = y === "" || y === "-";
                if (xEmpty || yEmpty) return xEmpty === yEmpty ? 0 : xEmpty ? 1 : -1;
                var result;
                if (type === "num") {
                    result = parseFloat(x.replace(",", ".")) - parseFloat(y.replace(",", "."));
                } else {
                    result = x.localeCompare(y, "uk", { numeric: true, sensitivity: "base" });
                }
                return direction === "ascending" ? result : -result;
            });
            sorted.forEach(function (row) {
                body.insertBefore(row, emptyRow || null);
            });
        }

        headers.forEach(function (th, index) {
            var type = th.getAttribute("data-sort");
            if (!type) return;
            th.setAttribute("tabindex", "0");
            th.setAttribute("role", "columnheader");
            function activate() {
                var current = th.getAttribute("aria-sort");
                var next = current === "ascending" ? "descending" : current === "descending" ? null : "ascending";
                headers.forEach(function (other) {
                    other.removeAttribute("aria-sort");
                });
                if (next) th.setAttribute("aria-sort", next);
                sortBy(index, type, next);
            }
            th.addEventListener("click", activate);
            th.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    activate();
                }
            });
        });

        /* Швидкий пошук по вже завантажених рядках */
        var id = table.id;
        if (!id) return;
        var input = document.querySelector('[data-table-filter="' + id + '"]');
        var counter = document.querySelector('[data-table-count="' + id + '"]');
        var columns = table.tHead.rows[0].cells.length;
        var noMatch = document.createElement("tr");
        noMatch.className = "no-match";
        noMatch.hidden = true;
        noMatch.innerHTML = '<td class="empty" colspan="' + columns + '">Нічого не знайдено. Змініть запит.</td>';
        body.appendChild(noMatch);

        function update() {
            var query = input ? input.value.trim().toLowerCase() : "";
            var visible = 0;
            rows.forEach(function (row) {
                var show = !query || row.textContent.toLowerCase().indexOf(query) !== -1;
                row.hidden = !show;
                if (show) visible += 1;
            });
            noMatch.hidden = !(rows.length && visible === 0);
            if (counter) {
                counter.textContent = rows.length
                    ? (query ? "Знайдено " + visible + " з " + rows.length : "Усього: " + rows.length)
                    : "";
            }
        }
        if (input) input.addEventListener("input", update);
        update();
    }

    document.addEventListener("DOMContentLoaded", function () {
        icons();
        Array.prototype.forEach.call(document.querySelectorAll("table.data-table"), initTable);
    });
})();
