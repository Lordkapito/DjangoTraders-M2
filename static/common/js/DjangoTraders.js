/*
    Project-wide custom JavaScript.

    Lives in static/common/js/ (project-root static/ folder, registered
    via STATICFILES_DIRS in settings.py), parallel to templates/common/
    holding the project-wide base.html. Loaded from base.html after
    jQuery, DataTables, and Bootstrap's JS bundle, so anything here can
    rely on all three already being present.

    Each Make*DataTable(tableId) function below applies DataTables to
    one named table by id -- pageLength/lengthMenu raise DataTables'
    own default of 10 rows per page and the choices in its "Show N
    entries" dropdown. Kept as one function per table, repeating the
    same settings, rather than a shared helper -- simple beats DRY
    here: a table with its own quirk (an unsortable icon column, a
    custom sort order) just sets that option in its own function
    instead of a generic helper needing extra parameters to handle
    every table's special case.

    MakeCustomersDataTable (customer_list.html) also disables sorting
    on its Actions column (an icon, not sortable data), and swaps the
    entries-per-page dropdown and "Showing X of Y" positions.
    MakeProductsDataTable (product_list.html) also disables sorting on
    its Actions column. MakeOrdersDataTable (customer_detail.html) and
    MakeProductOrdersDataTable (product_detail.html) both default to
    sorting by Order Date, descending, instead of DataTables' own
    default (first column, ascending). MakeOrderDetailsDataTable
    (order_detail.html) uses the plain defaults -- no special options
    needed.

    ValidateCustomerEditForm (customer_edit.html) is a hand-written
    jQuery illustration of client-side validation, alongside (not
    instead of) the HTML5 pattern= attributes and Django's own
    clean_<field>() methods (djtraders/forms.py) already doing the
    real work -- see its own comment below.

    AddOrderLineItem/RemoveOrderLineItem/FilterProductOptions/
    ShowLowStockBadge (order_build.html) support the shopping cart --
    see each one's own comment below. ShowToast/UpdateNavCart
    (base.html) are shared helpers those two cart functions call on
    success, keeping the navbar's cart dropdown and a toast
    notification live without a page reload.
*/

// #region DataTables activation functions
function MakeCustomersDataTable(tableId) {
    $(tableId).DataTable({
        pageLength: 20,
        lengthMenu: [ [10, 20, 25, 50, -1], [10, 20, 25, 50, "All"] ],
        columnDefs: [
            { targets: -1, orderable: false }
        ],
        layout: {
            topStart: 'info',
            topEnd: 'search',
            bottomStart: 'pageLength',
            bottomEnd: 'paging'
        },
    });
}

function MakeProductsDataTable(tableId) {
    $(tableId).DataTable({
        pageLength: 20,
        lengthMenu: [ [10, 20, 25, 50, -1], [10, 20, 25, 50, "All"] ],
        columnDefs: [
            { targets: -1, orderable: false }
        ],
        layout: {
            topStart: 'info',
            topEnd: 'search',
            bottomStart: 'pageLength',
            bottomEnd: 'paging'
        }
    });
}

function MakeOrdersDataTable(tableId) {
    $(tableId).DataTable({
        pageLength: 20,
        lengthMenu: [ [10, 20, 25, 50, -1], [10, 20, 25, 50, "All"] ],
        // Column 1 is Order Date; 'desc' shows the most recent order first
        // by default, instead of DataTables' own default (column 0, asc).
        order: [[1, 'desc']]
    });
}

function MakeOrderDetailsDataTable(tableId) {
    $(tableId).DataTable({
        pageLength: 20,
        lengthMenu: [ [10, 20, 25, 50, -1], [10, 20, 25, 50, "All"] ]
    });
}

function MakeProductOrdersDataTable(tableId) {
    $(tableId).DataTable({
        pageLength: 20,
        lengthMenu: [ [10, 20, 25, 50, -1], [10, 20, 25, 50, "All"] ],
        // Column 1 is Order Date; 'desc' shows the most recent order first
        // by default, instead of DataTables' own default (column 0, asc).
        order: [[1, 'desc']]
    });
}
// #endregion

/*
    ValidateCustomerEditForm -- client-side validation for customer_edit.html,
    layered alongside (not instead of) the HTML5 pattern= attributes
    CustomerEditForm's __init__ sets AND Django's own server-side check
    (clean_phone()/clean_company_name()/clean_city(), djtraders/forms.py).
    The server-side check is the one that actually enforces the rule --
    this only improves the browser experience.

    Its three regexes are hand-copied from forms.py's PHONE_PATTERN/
    NO_DIGITS_PATTERN. A static .js file can't import from a Python
    module, so the two copies have to be kept in sync by hand; if they
    ever drift apart, the server-side check still wins because it runs
    last and is the actual gate.

    Uses a plain 'submit' event listener with preventDefault() on
    failure, not AJAX -- the page still does a full POST/redirect on
    success. Note: a script that calls a form's native .submit()
    method (rather than a real click or Enter key) does not fire the
    'submit' event at all, so this validation -- like the HTML5
    pattern= attributes -- can be bypassed that way. That's inherent
    to client-side validation generally, not a gap specific to this
    function.
*/
function ValidateCustomerEditForm(formId) {
    const PHONE_PATTERN = /^[0-9()\-\s]{7,20}$/;
    const NO_DIGITS_PATTERN = /^[^0-9]*$/;

    function setFieldError(fieldId, message) {
        const field = document.getElementById(fieldId);
        let feedback = field.parentElement.querySelector(".js-invalid-feedback");
        if (!feedback) {
            feedback = document.createElement("div");
            feedback.className = "invalid-feedback js-invalid-feedback";
            field.insertAdjacentElement("afterend", feedback);
        }
        if (message) {
            field.classList.add("is-invalid");
            feedback.textContent = message;
            feedback.style.display = "block";
        } else {
            field.classList.remove("is-invalid");
            feedback.style.display = "none";
        }
    }

    $(formId).on("submit", function (event) {
        let valid = true;

        const companyName = $("#id_company_name").val().trim();
        if (companyName && !NO_DIGITS_PATTERN.test(companyName)) {
            setFieldError("id_company_name", "Company name can't contain numbers.");
            valid = false;
        } else {
            setFieldError("id_company_name", null);
        }

        const phone = $("#id_phone").val().trim();
        if (phone && !PHONE_PATTERN.test(phone)) {
            setFieldError("id_phone", "Enter a valid phone number (digits, spaces, parentheses, and dashes only, 7-20 characters).");
            valid = false;
        } else {
            setFieldError("id_phone", null);
        }

        const city = $("#id_city").val().trim();
        if (city && !NO_DIGITS_PATTERN.test(city)) {
            setFieldError("id_city", "City can't contain numbers.");
            valid = false;
        } else {
            setFieldError("id_city", null);
        }

        if (!valid) {
            event.preventDefault();
        }
    });
}

/*
    ShowToast -- pops the shared Bootstrap toast (#dtToast, base.html)
    with a short success message. Bootstrap's own JS bundle (loaded in
    base.html) provides bootstrap.Toast; this wraps "find it, set its
    text, show it" into one call so every AJAX success handler can fire
    a consistent notification without repeating the boilerplate.
    Present on every page (the toast container lives in base.html), so
    it works regardless of which page happens to call it.
*/
function ShowToast(message) {
    const toastEl = document.getElementById("dtToast");
    if (!toastEl) return;
    document.getElementById("dtToastBody").textContent = message;
    const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 2500 });
    toast.show();
}

/*
    UpdateNavCart -- patches the navbar's cart dropdown (base.html) in
    place after a successful AJAX add/remove (AddOrderLineItem/
    RemoveOrderLineItem below), so the badge count and dropdown
    contents reflect the change immediately -- without this, the
    navbar stays exactly as it was server-rendered at page load until a
    full reload, since nothing else ever touches it again.

    itemCount/linesSummary/customerId come straight from order_add_line/
    order_remove_line's own JSON response (views.py), which already
    computes them from the same _cart_lines() the rest of the cart
    uses -- this never recomputes anything itself, just renders what
    the server already decided. Does nothing if the navbar's cart
    elements aren't on the page (e.g. an employee building someone
    else's cart sees no cart dropdown of their own, since it's
    customer-only -- base.html's own current_customer gate).
*/
function UpdateNavCart(itemCount, linesSummary, customerId) {
    const $badge = $("#navCartBadge");
    if ($badge.length === 0) return;

    const $content = $("#navCartContent");
    const $viewLink = $("#navCartViewLink");

    if (itemCount > 0) {
        $badge.text(itemCount).removeClass("d-none");
    } else {
        $badge.addClass("d-none");
    }

    $content.empty();
    if (linesSummary && linesSummary.length > 0) {
        let grandTotal = 0;
        linesSummary.forEach(function (line) {
            grandTotal += parseFloat(line.line_total);
            $content.append(
                `<li class="px-2 py-1 d-flex justify-content-between small">
                    <span>${line.quantity} &times; ${line.name}</span>
                    <span>$${line.line_total}</span>
                </li>`
            );
        });
        $content.append('<li><hr class="dropdown-divider"></li>');
        $content.append(
            `<li class="px-2 py-1 d-flex justify-content-between fw-bold">
                <span>Total</span>
                <span>$${grandTotal.toFixed(2)}</span>
            </li>`
        );
        if (customerId) {
            $viewLink.attr("href", `/djtraders/customers/${customerId}/orders/build/`).removeClass("d-none");
        }
    } else {
        $content.append('<li class="px-2 py-1 small text-muted">Your cart is empty.</li>');
        $viewLink.addClass("d-none");
    }
}

/*
    AddOrderLineItem -- intercepts order_build.html's Add Line Item
    form and POSTs to order_add_line (djtraders/views.py) via AJAX,
    patching the page in place instead of reloading it. This is the
    project's one AJAX-driven view: a customer (or an employee building
    a cart on their behalf, enhancement 7) can add several products in
    a row without the page reloading each time, then commit the whole
    order at once.

    Checks the bare minimum client-side before submitting -- a product
    is selected, quantity is a positive number, and (enhancement 5)
    quantity doesn't exceed the selected product's own data-stock
    attribute (ProductSelectWidget, djtraders/forms.py). None of these
    are a substitute for OrderDetailForm's own server-side checks,
    which are the real, unbypassable gate.

    On success: the newly added/updated row gets a brief highlight
    flash (dt-row-added, DjangoTraders.css), a toast notification pops
    (ShowToast), the navbar cart dropdown updates live (UpdateNavCart),
    and a second toast fires if Extra Credit A's volume discount kicked
    in automatically.

    formId: the Add Line Item <form>'s own id ("#order-detail-form"),
    passed in from order_build.html's {% block scripts %} rather than
    hard-coded, the same way ValidateCustomerEditForm takes its form id
    as an argument.
*/
function AddOrderLineItem(formId) {
    const $form = $(formId);
    const $errorBox = $form.find("#order-detail-form-error");

    function showError(message) {
        $errorBox.text(message).removeClass("d-none");
    }

    function clearError() {
        $errorBox.text("").addClass("d-none");
    }

    $form.on("submit", function (event) {
        event.preventDefault();
        clearError();

        const $productSelect = $("#id_product");
        const productId = $productSelect.val();
        const quantity = parseInt($("#id_quantity").val(), 10);

        if (!productId) {
            showError("Select a product.");
            return;
        }
        if (!quantity || quantity < 1) {
            showError("Quantity must be at least 1.");
            return;
        }

        const stock = parseInt($productSelect.find("option:selected").attr("data-stock"), 10);
        if (!isNaN(stock) && quantity > stock) {
            showError(`Only ${stock} in stock -- reduce the quantity.`);
            return;
        }

        function messagesFrom(errors) {
            return Object.values(errors || {})
                .flat()
                .map((error) => (typeof error === "string" ? error : error.message));
        }

        $.ajax({
            url: $form.attr("action"),
            method: "POST",
            data: $form.serialize(),
            dataType: "json",
        }).done(function (response) {
            if (!response.success) {
                showError(messagesFrom(response.errors).join(" ") || "Couldn't add that to your cart.");
                return;
            }

            $("#order-lines-empty-row").remove();
            const $existingRow = $(`#order-lines-body tr[data-product-id="${response.product_id}"]`);
            if ($existingRow.length) {
                $existingRow.replaceWith(response.row_html);
            } else {
                $("#order-lines-body").append(response.row_html);
            }
            // Flash the row that was just added or updated (Requirement 4).
            const $newRow = $(`#order-lines-body tr[data-product-id="${response.product_id}"]`);
            $newRow.addClass("dt-row-added");
            $newRow.one("animationend", function () {
                $(this).removeClass("dt-row-added");
            });
            $("#order-total").text("$" + response.order_total);

            ShowToast(`Added ${response.product_name} to your cart.`);
            if (response.volume_discount_applied) {
                setTimeout(function () {
                    ShowToast("Volume discount applied (10% automatic at high quantity).");
                }, 600);
            }
            UpdateNavCart(response.cart_item_count, response.cart_lines_summary, response.cart_customer_id);

            $("#id_quantity").val(1);
            $productSelect.val("");
        }).fail(function (xhr) {
            // A validation failure (order_add_line's own 400/403 JsonResponse,
            // views.py) lands here, not in .done() above -- jQuery treats
            // any non-2xx HTTP status as a failure regardless of the
            // response body, so the real error message has to be read
            // from xhr.responseJSON. Fall back to a generic message only
            // when there's no JSON to read (a network failure or 500).
            const messages = xhr.responseJSON ? messagesFrom(xhr.responseJSON.errors) : [];
            showError(messages.join(" ") || "Something went wrong adding that to your cart -- try again.");
        });
    });
}

/*
    RemoveOrderLineItem -- wires up every row's Remove button (the
    .remove-line-btn inside _order_line_row.html) to POST to
    order_remove_line (djtraders/views.py) via AJAX and delete that row
    in place, no page reload. Uses event delegation ($table.on("click",
    ".remove-line-btn", ...)) rather than binding to each button
    directly, since rows are added/replaced dynamically by
    AddOrderLineItem after this function has already run once on page
    load -- a direct binding would miss any row added afterward.

    On success, also updates the navbar's cart dropdown live
    (UpdateNavCart) -- without this, the badge count stayed stale after
    a removal until a full page reload.

    tableId: #order-lines-table's own id (order_build.html), whose
    data-remove-url attribute carries order_remove_line's URL -- same
    pattern AddOrderLineItem uses, reading its own form's action=
    attribute instead of hard-coding the URL here.

    Reuses the CSRF token already present on the page from the Add to
    Cart form's own {% csrf_token %} -- there is no separate <form> around
    each Remove button, so this reads that same hidden input by name
    rather than needing one of its own.
*/
function RemoveOrderLineItem(tableId) {
    const $table = $(tableId);
    const removeUrl = $table.data("remove-url");
    const csrfToken = $('[name=csrfmiddlewaretoken]').first().val();

    $table.on("click", ".remove-line-btn", function () {
        const $button = $(this);
        const $row = $button.closest("tr");
        const productId = $row.data("product-id");

        $button.prop("disabled", true);

        $.ajax({
            url: removeUrl,
            method: "POST",
            data: {
                product_id: productId,
                csrfmiddlewaretoken: csrfToken,
            },
            dataType: "json",
        }).done(function (response) {
            if (!response.success) {
                $button.prop("disabled", false);
                return;
            }

            $row.remove();
            $("#order-total").text("$" + response.order_total);
            UpdateNavCart(response.cart_item_count, response.cart_lines_summary, response.cart_customer_id);

            if (response.cart_empty && $("#order-lines-empty-row").length === 0) {
                $("#order-lines-body").append(
                    '<tr id="order-lines-empty-row"><td colspan="6">Your cart is empty -- add a product below.</td></tr>'
                );
            }
        }).fail(function () {
            $button.prop("disabled", false);
        });
    });
}

/*
    FilterProductOptions -- narrows order_build.html's Product dropdown
    to the category picked in its own Category filter dropdown.
    ProductSelectWidget's data-category-id attribute (djtraders/forms.py)
    on each <option> is what this reads. Purely a client-side
    convenience over the same full, non-discontinued list
    OrderDetailForm's queryset already allows server-side -- "All
    Categories" (or leaving the filter unset) shows every option again.

    Rebuilds the <select>'s own option list from a saved full copy on
    every filter change, rather than toggling the hidden/disabled
    properties on individual <option> elements -- hidden on <option> is
    inconsistently honored across browsers, so this is the more
    reliable approach. The placeholder ("Select a product...") option
    is always kept, since it has no data-category-id of its own.
*/
function FilterProductOptions(filterId, productSelectId) {
    const $filter = $(filterId);
    const $productSelect = $(productSelectId);

    const $allOptions = $productSelect.find("option").clone();

    $filter.on("change", function () {
        const categoryId = $filter.val();

        $productSelect.empty();

        $allOptions.each(function () {
            const $option = $(this);
            const rawValue = $option.attr("value");
            const isPlaceholder = !rawValue || rawValue === "";
            const optionCategoryId = $option.attr("data-category-id") || "";
            const matches = isPlaceholder || !categoryId || optionCategoryId === categoryId;

            if (matches) {
                $productSelect.append($option.clone());
            }
        });
    });
}

/*
    ShowLowStockBadge (Requirement 4) -- displays a small "Low Stock"
    badge next to the Product dropdown (order_build.html) whenever the
    currently selected product's data-stock (ProductSelectWidget,
    djtraders/forms.py) falls at or below threshold. Purely a display
    aid; OrderDetailForm's own clean() is the real stock enforcement,
    same as every other data-stock use in this project (see
    AddOrderLineItem's browser-layer check above).
*/
function ShowLowStockBadge(productSelectId, threshold) {
    const $productSelect = $(productSelectId);
    const $badge = $('<span class="dt-stock-badge dt-stock-low d-none">Low Stock</span>');
    $productSelect.after($badge);

    $productSelect.on("change", function () {
        const stock = parseInt($productSelect.find("option:selected").attr("data-stock"), 10);
        if (!isNaN(stock) && stock > 0 && stock <= threshold) {
            $badge.removeClass("d-none");
        } else {
            $badge.addClass("d-none");
        }
    });
}