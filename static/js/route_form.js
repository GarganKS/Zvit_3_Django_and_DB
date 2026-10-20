/* Сторінка маршруту: додавання, видалення та зміна порядку зупинок.
   Номери (stop_sequence) завжди рахуються за порядком рядків на сторінці. */
(function () {
    var list = document.getElementById("stop-list");
    if (!list) return;

    var form = document.getElementById("route-form");
    var total = form.querySelector('[name$="-TOTAL_FORMS"]');
    var template = document.getElementById("stop-row-template");
    var titleEl = document.getElementById("route-title");

    function allRows() {
        return Array.prototype.slice.call(list.querySelectorAll(".stop-row"));
    }

    function activeRows() {
        return allRows().filter(function (row) {
            return !row.classList.contains("is-deleted");
        });
    }

    function field(row, suffix) {
        return row.querySelector('[name$="-' + suffix + '"]');
    }

    function selectedText(row) {
        var select = field(row, "stop");
        if (!select || !select.value) return "";
        return select.options[select.selectedIndex].text;
    }

    function refresh() {
        var rows = activeRows();
        rows.forEach(function (row, i) {
            field(row, "stop_sequence").value = i + 1;
            row.querySelector(".stop-num").textContent = i + 1;
            var role = "";
            if (i === 0) role = "Початок";
            else if (i === rows.length - 1) role = "Кінець";
            row.querySelector(".stop-role").textContent = role;
            row.querySelector('[data-action="up"]').disabled = i === 0;
            row.querySelector('[data-action="down"]').disabled = i === rows.length - 1;
        });

        var first = rows.length ? selectedText(rows[0]) : "";
        var last = rows.length ? selectedText(rows[rows.length - 1]) : "";
        if (first && last) {
            titleEl.textContent = first === last ? first : first + " - " + last;
        } else if (first) {
            titleEl.textContent = first;
        } else {
            titleEl.textContent = "Новий маршрут";
        }
    }

    function move(row, step) {
        var rows = activeRows();
        var target = rows[rows.indexOf(row) + step];
        if (!target) return;
        if (step < 0) list.insertBefore(row, target);
        else list.insertBefore(target, row);
        refresh();
        var button = row.querySelector('[data-action="' + (step < 0 ? "up" : "down") + '"]');
        if (button && !button.disabled) button.focus();
    }

    function remove(row) {
        // Рядок лише позначається на видалення: сервер видалить його після збереження.
        field(row, "DELETE").checked = true;
        row.classList.add("is-deleted");
        refresh();
    }

    function addRow() {
        var index = parseInt(total.value, 10);
        var holder = document.createElement("ol");
        holder.innerHTML = template.innerHTML.replace(/__prefix__/g, index).trim();
        var row = holder.firstElementChild;
        list.appendChild(row);
        total.value = index + 1;
        refresh();
        field(row, "stop").focus();
    }

    list.addEventListener("click", function (event) {
        var button = event.target.closest("[data-action]");
        if (!button) return;
        var row = button.closest(".stop-row");
        var action = button.getAttribute("data-action");
        if (action === "up") move(row, -1);
        else if (action === "down") move(row, 1);
        else if (action === "delete") remove(row);
    });

    list.addEventListener("change", function (event) {
        if (event.target.matches('[name$="-stop"]')) refresh();
    });

    document.getElementById("add-stop").addEventListener("click", addRow);
    form.addEventListener("submit", refresh);

    // Початковий стан: приховати позначені на видалення (після помилки валідації)
    // і розставити рядки за збереженим порядком.
    allRows().forEach(function (row) {
        if (field(row, "DELETE").checked) row.classList.add("is-deleted");
    });
    var sorted = allRows()
        .map(function (row, i) {
            var n = parseInt(field(row, "stop_sequence").value, 10);
            return { row: row, key: isNaN(n) ? Infinity : n, i: i };
        })
        .sort(function (a, b) {
            return a.key === b.key ? a.i - b.i : a.key - b.key;
        });
    sorted.forEach(function (item) { list.appendChild(item.row); });
    refresh();
})();
