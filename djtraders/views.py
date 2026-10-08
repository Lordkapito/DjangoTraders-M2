"""
View functions for the djtraders app.

Browsing (open to anyone): home, customer_list/product_list (search
handled by each model's own search() classmethod, djtraders/models.py),
customer_detail/product_detail, order_detail.

Two logins, each hand-rolled with plain sessions instead of Django's
own auth system: login_view/logout_view (employee, session key
"current_user") and customer_login_view/customer_logout_view (customer,
session key "customer_id"). Only one of the two can be logged in at a
time -- landing on either login page logs out whoever was there before.

Self-service access rule: a logged-in customer may only view/edit their
own record; an employee may act on any customer's. The helpers at the
top of this file (_own_customer_redirect, _own_employee_redirect,
_customer_edit_denied, _order_access_denied, _cart_access_denied)
enforce that rule wherever it applies, instead of repeating the same
session checks in every view.

Customer edit/create: customer_edit_form and customer_edit render the
identical fields two ways -- hand-written <input> tags vs. a Django
ModelForm (CustomerEditForm, djtraders/forms.py) rendered through
django-crispy-forms -- to compare the two approaches side by side.
customer_create reuses customer_edit's own template and form for a
Customer that doesn't exist yet. customer_delete marks a customer
inactive instead of deleting the row; customer_reactivate reverses it.

Ordering: a customer's in-progress order lives in
request.session["cart"] (a plain dict, no database row) until
order_commit writes it out as a real Order plus its OrderDetail rows,
inside one transaction. order_create/order_build/order_add_line/
order_commit walk through that flow; order_delete cancels an
already-placed order on the same day it was placed. Cart lines store
{str(product_id): {"quantity": int, "discount": float}} -- see
_cart_lines below.

Cart access (_cart_access_denied) allows either the cart's own
logged-in customer OR any logged-in employee -- an employee can build
and commit a cart on behalf of any customer (enhancement 7), while a
different customer is still blocked from touching someone else's cart.
allow_high_discount in order_add_line is True exactly when an employee
session is operating the cart, so an employee processing a line can
apply a discount above the ordinary 10% customer cap.

order_commit re-checks each line's stock at commit time (stock may
have moved since the line was added) and decrements
Product.units_in_stock atomically inside the same transaction as the
Order/OrderDetail writes (enhancement 5). ShipToForm (djtraders/forms.py)
is a separate, validated address form shown alongside the commit
fields -- its cleaned data, not the customer's raw on-file address, is
what actually gets written onto the Order's ship_* columns
(enhancement 6). order_add_line/order_remove_line also return enough
cart summary data (cart_item_count/cart_lines_summary/cart_customer_id)
for the navbar's cart dropdown (base.html, UpdateNavCart in
DjangoTraders.js) to update live, without a page reload.
"""

from types import SimpleNamespace

from django.db import models, transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from .forms import (CustomerEditForm, OrderCommitForm, OrderDetailForm,
                    ProductEditForm, ShipToForm, default_required_date,
                    default_shipped_date)
from .models import Category, Customer, Employee, Order, OrderDetail, Product, Supplier


def _own_customer_redirect(request, customer_id):
    """
    If a logged-in customer (request.session["customer_id"]) is asking
    for a different customer_id than their own, returns a redirect to
    their own customer_detail page instead. Returns None (proceed
    normally) for an employee, an anonymous visitor, or a customer
    already looking at their own page.
    """
    logged_in_customer_id = request.session.get("customer_id")
    if logged_in_customer_id and logged_in_customer_id != customer_id:
        return redirect("djtraders:customer_detail", customer_id=logged_in_customer_id)
    return None


def _own_employee_redirect(request, employee_id):
    """
    Same idea as _own_customer_redirect above, for the employee side --
    if a logged-in employee (request.session["current_user"]) is asking
    for a different employee_id than their own, returns a redirect to
    their own employee_detail page instead; None otherwise.
    """
    logged_in_employee_id = request.session.get("current_user")
    if logged_in_employee_id and logged_in_employee_id != employee_id:
        return redirect("djtraders:employee_detail", employee_id=logged_in_employee_id)
    return None


def _order_access_denied(request, order):
    """
    True if the current session may NOT view/build/commit this order --
    neither an employee (who can act on any order) nor the order's own
    logged-in customer.
    """
    logged_in_employee = request.session.get("current_user")
    if logged_in_employee:
        return False
    if order.customer_id is None:
        return True
    logged_in_customer_id = request.session.get("customer_id")
    return order.customer_id != logged_in_customer_id


def _customer_edit_denied(request, customer_id):
    """
    True if the current session may NOT edit this customer_id -- neither
    an employee (who can edit any customer) nor this customer's own
    logged-in session.
    """
    logged_in_employee = request.session.get("current_user")
    logged_in_customer_id = request.session.get("customer_id")
    return not logged_in_employee and logged_in_customer_id != customer_id


def _cart_access_denied(request, customer_id):
    """
    True if the current session may NOT operate this customer_id's
    cart -- neither an employee (who may build/commit a cart for any
    customer, enhancement 7) nor this customer's own logged-in session.
    Same shape as _customer_edit_denied above, used by every cart view
    below instead of each one comparing
    request.session["customer_id"] != customer_id directly, which would
    never let an employee through.
    """
    logged_in_employee = request.session.get("current_user")
    logged_in_customer_id = request.session.get("customer_id")
    return not logged_in_employee and logged_in_customer_id != customer_id


def home(request):
    """Landing page for the djtraders app. No database access."""
    return render(request, "djtraders/home.html")


def customer_list(request):
    """
    Display a list of customers, searchable by company name, contact
    name, contact title, city, and country.
    """
    redirect_response = _own_customer_redirect(request, customer_id=None)
    if redirect_response:
        return redirect_response

    search_company_name = request.GET.get("company_name", "")
    search_contact_name = request.GET.get("contact_name", "")
    search_contact_title = request.GET.get("contact_title", "")
    search_city = request.GET.get("city", "")
    search_country = request.GET.get("country", "")

    cities_queryset = Customer.objects.exclude(city__isnull=True).exclude(city__exact="")
    if search_country:
        cities_queryset = cities_queryset.filter(country=search_country)
    cities = cities_queryset.order_by("city").values_list("city", flat=True).distinct()

    countries = (
        Customer.objects.exclude(country__isnull=True)
        .exclude(country__exact="")
        .order_by("country")
        .values_list("country", flat=True)
        .distinct()
    )

    contact_titles = (
        Customer.objects.exclude(contact_title__isnull=True)
        .exclude(contact_title__exact="")
        .order_by("contact_title")
        .values_list("contact_title", flat=True)
        .distinct()
    )

    if search_city and search_city not in cities:
        search_city = ""

    customers = Customer.search(
        company_name=search_company_name,
        contact_name=search_contact_name,
        contact_title=search_contact_title,
        city=search_city,
        country=search_country,
    )

    context = {
        "customers": customers,
        "cities": cities,
        "countries": countries,
        "contact_titles": contact_titles,
        "search_company_name": search_company_name,
        "search_contact_name": search_contact_name,
        "search_contact_title": search_contact_title,
        "search_city": search_city,
        "search_country": search_country,
    }
    return render(request, "djtraders/customer_list.html", context)


def product_list(request):
    """
    Display a list of products, searchable by product name and category,
    with an option to include discontinued products.
    """
    search_product_name = request.GET.get("product_name", "")
    search_category_id = request.GET.get("category", "")
    show_all = request.GET.get("show_all") == "on"

    products = Product.search(
        product_name=search_product_name,
        category_id=search_category_id,
        show_all=show_all,
    )

    categories = Category.objects.order_by("category_name")

    context = {
        "products": products,
        "categories": categories,
        "search_product_name": search_product_name,
        "search_category_id": search_category_id,
        "show_all": show_all,
    }
    return render(request, "djtraders/product_list.html", context)


def product_detail(request, product_id):
    """
    Display a single product's full record: its own fields, plus every
    order line it's appeared on (product.orderdetail_set).
    """
    product = get_object_or_404(Product, pk=product_id)
    order_lines = product.orderdetail_set.select_related("order").order_by("-order__order_date")
    context = {"product": product, "order_lines": order_lines}
    return render(request, "djtraders/product_detail.html", context)


def customer_detail(request, customer_id):
    """
    Display a single customer's full record.

    can_start_order uses _cart_access_denied instead of a direct
    session["customer_id"] == customer_id check -- an employee viewing
    any customer's page also gets the "Start New Order" button
    (enhancement 7), not just that customer viewing their own page.
    """
    redirect_response = _own_customer_redirect(request, customer_id)
    if redirect_response:
        return redirect_response

    customer = get_object_or_404(Customer, pk=customer_id)

    orders = customer.order_set.filter(order_date__isnull=False).order_by("-order_date")
    total_quantity = sum(
        line.quantity for order in orders for line in order.orderdetail_set.all()
    )
    total_revenue = sum(order.order_total for order in orders)

    can_start_order = not _cart_access_denied(request, customer.customer_id)

    context = {
        "customer": customer,
        "total_quantity": total_quantity,
        "total_revenue": total_revenue,
        "orders": orders,
        "can_start_order": can_start_order,
    }
    return render(request, "djtraders/customer_detail.html", context)


def customer_edit_form(request, customer_id):
    """
    Edit a customer's own record by hand-reading each request.POST field
    onto the Customer instance -- no Django Form class involved.
    """
    customer = get_object_or_404(Customer, pk=customer_id)

    if _customer_edit_denied(request, customer_id):
        return redirect("djtraders:customer_detail", customer_id=customer_id)

    error = None
    if request.method == "POST":
        company_name = request.POST.get("company_name", "").strip()
        if not company_name:
            error = "Company Name is required."
        else:
            customer.company_name = company_name
            customer.contact_name = request.POST.get("contact_name", "")
            customer.contact_title = request.POST.get("contact_title", "")
            customer.address = request.POST.get("address", "")
            customer.city = request.POST.get("city", "")
            customer.region = request.POST.get("region", "")
            customer.postal_code = request.POST.get("postal_code", "")
            customer.country = request.POST.get("country", "")
            customer.phone = request.POST.get("phone", "")
            customer.fax = request.POST.get("fax", "")
            customer.password = request.POST.get("password", "")
            customer.save()
            return redirect("djtraders:customer_detail", customer_id=customer.customer_id)

    context = {"customer": customer, "error": error}
    return render(request, "djtraders/customer_edit_form.html", context)


def customer_edit(request, customer_id):
    """
    Same edit as customer_edit_form above, built the Django Form way
    instead.
    """
    customer = get_object_or_404(Customer, pk=customer_id)

    if _customer_edit_denied(request, customer_id):
        return redirect("djtraders:customer_detail", customer_id=customer_id)

    if request.method == "POST":
        form = CustomerEditForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            return redirect("djtraders:customer_detail", customer_id=customer.customer_id)
    else:
        form = CustomerEditForm(instance=customer)

    confirm_delete = request.GET.get("confirm_delete") == "1"
    confirm_reactivate = request.GET.get("confirm_reactivate") == "1"

    context = {
        "customer": customer,
        "form": form,
        "confirm_delete": confirm_delete,
        "confirm_reactivate": confirm_reactivate,
    }

    return render(request, "djtraders/customer_edit.html", context)


def customer_create(request):
    """
    "Create Empty and Edit": renders the exact same page as
    customer_edit above for a Customer that doesn't exist yet.
    """
    if not request.session.get("current_user"):
        return redirect("djtraders:customer_list")

    if request.method == "POST":
        form = CustomerEditForm(request.POST, instance=Customer())
        if form.is_valid():
            form.instance.customer_id = Customer.generate_customer_id(
                form.cleaned_data["company_name"]
            )
            form.save()
            return redirect("djtraders:customer_list")
    else:
        form = CustomerEditForm(instance=Customer())

    context = {"customer": form.instance, "form": form, "new_customer": True}
    return render(request, "djtraders/customer_edit.html", context)


def customer_delete(request, customer_id):
    """
    Marks a customer inactive (sets inactive_date to today) instead of
    actually deleting the row.
    """
    if not request.session.get("current_user"):
        return redirect("djtraders:customer_list")

    if request.method == "POST":
        customer = get_object_or_404(Customer, pk=customer_id)
        customer.inactive_date = timezone.now().date()
        customer.save()

    return redirect("djtraders:customer_list")


def customer_reactivate(request, customer_id):
    """Clears inactive_date. Employee-only, POST-only, like customer_delete."""
    if not request.session.get("current_user"):
        return redirect("djtraders:customer_list")

    if request.method == "POST":
        customer = get_object_or_404(Customer, pk=customer_id)
        customer.inactive_date = None
        customer.save()

    return redirect("djtraders:customer_list")


def order_detail(request, order_id):
    """
    Display a single order: who placed it, who processed/shipped it, and
    every product line item on it.
    """
    order = get_object_or_404(Order, pk=order_id)

    order_lines = order.orderdetail_set.select_related("product__supplier")

    can_cancel_order = order.order_date == timezone.now().date() and not _order_access_denied(
        request, order
    )

    context = {
        "order": order,
        "order_lines": order_lines,
        "can_cancel_order": can_cancel_order,
    }
    return render(request, "djtraders/order_detail.html", context)


def login_view(request):
    """Employee login."""
    request.session.pop("current_user", None)
    request.session.pop("customer_id", None)

    error = None
    if request.method == "POST":
        employee_id = request.POST.get("employee_id", "")
        password = request.POST.get("password", "")
        employee = Employee.authenticate(employee_id, password)
        if employee is not None:
            request.session["current_user"] = employee.employee_id
            return redirect("djtraders:employee_detail", employee_id=employee.employee_id)
        error = "Incorrect employee/password combination."

    employees = Employee.objects.order_by("last_name", "first_name")
    context = {"employees": employees, "error": error}
    return render(request, "djtraders/login.html", context)


def logout_view(request):
    """Clears "current_user" from the session, logging the employee out."""
    request.session.pop("current_user", None)
    return redirect("djtraders:home")


def customer_login_view(request):
    """Customer login."""
    request.session.pop("current_user", None)
    request.session.pop("customer_id", None)

    error = None
    if request.method == "POST":
        customer_id = request.POST.get("customer_id", "")
        password = request.POST.get("password", "")
        customer = Customer.authenticate(customer_id, password)
        if customer is not None:
            request.session["customer_id"] = customer.customer_id
            return redirect("djtraders:customer_detail", customer_id=customer.customer_id)
        error = "Incorrect customer/password combination."

    customers = Customer.objects.order_by("company_name")
    context = {"customers": customers, "error": error}
    return render(request, "djtraders/customer_login.html", context)


def customer_logout_view(request):
    """Clears "customer_id" from the session, logging the customer out."""
    request.session.pop("customer_id", None)
    return redirect("djtraders:home")


def employee_detail(request, employee_id):
    """Display a single employee's own record."""
    redirect_response = _own_employee_redirect(request, employee_id)
    if redirect_response:
        return redirect_response

    employee = get_object_or_404(Employee, pk=employee_id)
    context = {"employee": employee}
    return render(request, "djtraders/employee_detail.html", context)


def _cart_lines(cart):
    """
    Turns a session cart's "lines" dict ({str(product_id): {"quantity":
    int, "discount": float}}, no database row backing any of it) into a
    list of lightweight, OrderDetail-shaped objects: .product,
    .unit_price, .quantity, .discount, .line_total. A plain
    types.SimpleNamespace, not a real model instance -- there might
    never be a real OrderDetail row, if this cart is abandoned -- but
    shaped so _order_line_row.html and the running total can be built
    exactly the same way as when these are real rows, with no template
    changes needed either way.

    unit_price is each product's *current* price, looked up fresh every
    time this runs (including at commit), not frozen at the moment a
    line was added -- there's nothing to freeze it onto before an Order
    row exists. discount is read straight off each line's own stored
    value (set at add-time, order_add_line below) -- not recomputed
    here.

    A cart line whose product_id no longer resolves to a real product
    (e.g. deleted) is silently skipped rather than raising -- nothing
    here enforces referential integrity the way a real ForeignKey would.
    """
    product_ids = [int(product_id) for product_id in cart.get("lines", {})]
    products_by_id = Product.objects.in_bulk(product_ids)

    lines = []
    for product_id_str, line_data in cart.get("lines", {}).items():
        product = products_by_id.get(int(product_id_str))
        if product is None:
            continue
        unit_price = product.unit_price or 0.0
        quantity = line_data["quantity"]
        discount = line_data.get("discount", 0.0)
        line_total = unit_price * quantity * (1 - discount)
        lines.append(
            SimpleNamespace(
                product=product,
                unit_price=unit_price,
                quantity=quantity,
                discount=discount,
                line_total=line_total,
            )
        )
    return lines


def _cart_lines_summary_json(cart_lines):
    """
    Shared helper: turns a list of _cart_lines() output into the plain
    {name, quantity, line_total} dicts order_add_line/order_remove_line
    both return for the navbar's cart dropdown (UpdateNavCart,
    DjangoTraders.js) to render -- extracted here so the two views don't
    each repeat the same list comprehension.
    """
    return [
        {"name": line.product.product_name, "quantity": line.quantity, "line_total": f"{line.line_total:.2f}"}
        for line in cart_lines
    ]


def order_create(request, customer_id):
    """
    Starts (or resumes) this customer's shopping cart in
    request.session["cart"] -- no database row at all until commit
    (order_commit below). Access: the customer's own session, or an
    employee building a cart on this customer's behalf
    (_cart_access_denied, enhancement 7).
    """
    if _cart_access_denied(request, customer_id):
        return redirect("djtraders:customer_detail", customer_id=customer_id)

    if request.method != "POST":
        return redirect("djtraders:customer_detail", customer_id=customer_id)

    cart = request.session.get("cart")
    if not cart or cart.get("customer_id") != customer_id:
        request.session["cart"] = {"customer_id": customer_id, "lines": {}}

    return redirect("djtraders:order_build", customer_id=customer_id)


def order_build(request, customer_id):
    """
    The shopping cart page. There is no Order row and no order_id at all
    until commit (order_commit below) -- everything here comes from
    request.session["cart"] and a fresh Customer/Product lookup, never
    a database Order. Access: the customer's own session, or an
    employee building a cart on this customer's behalf
    (_cart_access_denied, enhancement 7).

    ship_to_form (ShipToForm, djtraders/forms.py) is pre-filled from the
    customer's own current address but stays a real, independently
    editable/validated form -- see that form's own docstring.
    """
    if _cart_access_denied(request, customer_id):
        return redirect("djtraders:customer_detail", customer_id=customer_id)

    customer = get_object_or_404(Customer, pk=customer_id)

    cart = request.session.get("cart")
    if not cart or cart.get("customer_id") != customer_id:
        cart = {"customer_id": customer_id, "lines": {}}
        request.session["cart"] = cart

    cart_lines = _cart_lines(cart)
    cart_total = sum(line.line_total for line in cart_lines)
    detail_form = OrderDetailForm()
    # For the Category filter dropdown above the product select --
    # narrows the dropdown client-side only (FilterProductOptions,
    # DjangoTraders.js); OrderDetailForm's own queryset stays the
    # authoritative, server-side list regardless of what's picked here.
    categories = Category.objects.order_by("category_name")
    commit_form = OrderCommitForm(
        initial={
            "required_date": default_required_date(),
            "shipped_date": default_shipped_date(),
        }
    )
    ship_to_form = ShipToForm(
        initial={
            "ship_name": customer.company_name,
            "ship_address": customer.address,
            "ship_city": customer.city,
            "ship_region": customer.region,
            "ship_postal_code": customer.postal_code,
            "ship_country": customer.country,
        }
    )

    context = {
        "customer": customer,
        "cart_lines": cart_lines,
        "cart_total": cart_total,
        "detail_form": detail_form,
        "categories": categories,
        "commit_form": commit_form,
        "ship_to_form": ship_to_form,
    }
    return render(request, "djtraders/order_build.html", context)


def order_add_line(request, customer_id):
    """
    AJAX endpoint (order_build.html's Add Line Item form,
    DjangoTraders.js) -- adds a product/quantity/discount line to
    request.session["cart"]["lines"], or updates an already-existing
    line's quantity/discount instead of a second entry for the same
    product_id. OrderDetailForm's own clean() (forms.py) refuses a
    quantity greater than the product's current stock, and separately
    applies Extra Credit A's volume-based default discount -- this is
    the add-time check; order_commit below re-checks and decrements
    stock at commit, since stock can change between add and commit.

    Access: the customer's own session, or an employee building a cart
    on this customer's behalf (_cart_access_denied, enhancement 7).
    allow_high_discount is True exactly when an employee session is
    operating this cart -- an employee may apply a discount above the
    ordinary 10% customer cap (OrderDetailForm.clean_discount_percent).

    Adding more of an already-cart product sums the quantity with
    what's already there, but *replaces* that line's discount with the
    one just submitted.

    Returns cart_item_count/cart_lines_summary/cart_customer_id
    alongside the usual row_html/order_total, so the navbar's cart
    dropdown (UpdateNavCart, DjangoTraders.js) can update live without
    a page reload.
    """
    if _cart_access_denied(request, customer_id):
        return JsonResponse({"success": False, "errors": {"__all__": ["Not allowed."]}}, status=403)

    cart = request.session.get("cart")
    if not cart or cart.get("customer_id") != customer_id:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Your cart isn't open anymore -- reload the page."]}},
            status=400,
        )

    allow_high_discount = bool(request.session.get("current_user"))
    form = OrderDetailForm(request.POST, allow_high_discount=allow_high_discount)
    if not form.is_valid():
        return JsonResponse({"success": False, "errors": form.errors.get_json_data()}, status=400)

    product = form.cleaned_data["product"]
    quantity = form.cleaned_data["quantity"]
    discount = form.discount_fraction

    product_key = str(product.product_id)
    existing = cart["lines"].get(product_key)
    new_quantity = (existing["quantity"] if existing else 0) + quantity
    cart["lines"][product_key] = {"quantity": new_quantity, "discount": discount}
    # Session middleware only notices a *replaced* top-level key by
    # default -- mutating cart["lines"] in place doesn't trigger that
    # on its own, so this has to be set explicitly or the change is
    # silently dropped at the end of the request.
    request.session.modified = True

    cart_lines = _cart_lines(cart)
    line = next(line for line in cart_lines if line.product.product_id == product.product_id)
    row_html = render_to_string(
        "djtraders/_order_line_row.html", {"line": line}, request=request
    )
    cart_total = sum(line.line_total for line in cart_lines)
    return JsonResponse(
        {
            "success": True,
            "row_html": row_html,
            "product_id": product.product_id,
            "product_name": product.product_name,
            "order_total": f"{cart_total:,.2f}",
            "volume_discount_applied": getattr(form, "volume_discount_applied", False),
            "cart_item_count": len(cart_lines),
            "cart_lines_summary": _cart_lines_summary_json(cart_lines),
            "cart_customer_id": customer_id,
        }
    )


def order_remove_line(request, customer_id):
    """
    AJAX endpoint (order_build.html's per-row Remove button,
    DjangoTraders.js's RemoveOrderLineItem) -- removes one product line
    entirely from request.session["cart"]["lines"]. Access:
    _cart_access_denied, same as every other cart view.

    Returns the same cart_item_count/cart_lines_summary/cart_customer_id
    fields as order_add_line, so the navbar's cart dropdown stays live
    after a removal too, not just an addition.
    """
    if _cart_access_denied(request, customer_id):
        return JsonResponse({"success": False, "errors": {"__all__": ["Not allowed."]}}, status=403)

    cart = request.session.get("cart")
    if not cart or cart.get("customer_id") != customer_id:
        return JsonResponse(
            {"success": False, "errors": {"__all__": ["Your cart isn't open anymore -- reload the page."]}},
            status=400,
        )

    product_id = request.POST.get("product_id", "")
    cart["lines"].pop(product_id, None)
    request.session.modified = True

    cart_lines = _cart_lines(cart)
    cart_total = sum(line.line_total for line in cart_lines)
    return JsonResponse({
        "success": True,
        "product_id": product_id,
        "order_total": f"{cart_total:,.2f}",
        "cart_empty": len(cart_lines) == 0,
        "cart_item_count": len(cart_lines),
        "cart_lines_summary": _cart_lines_summary_json(cart_lines),
        "cart_customer_id": customer_id,
    })


def order_clear(request, customer_id):
    """
    Clears every line from the cart in one action, without committing
    anything -- a real POST, not AJAX. Access: _cart_access_denied,
    same as every other cart view.
    """
    if _cart_access_denied(request, customer_id):
        return redirect("djtraders:customer_detail", customer_id=customer_id)

    if request.method == "POST":
        cart = request.session.get("cart")
        if cart and cart.get("customer_id") == customer_id:
            cart["lines"] = {}
            request.session.modified = True

    return redirect("djtraders:order_build", customer_id=customer_id)


def order_commit(request, customer_id):
    """
    Places the cart -- the one point where any of it is written to the
    database at all. Access: _cart_access_denied, same as every other
    cart view (enhancement 7).

    Validates OrderCommitForm AND ShipToForm together -- both have to
    pass before anything is written. Re-checks every line's stock
    (stock can have moved since a line was added -- another customer's
    order may have committed in between), refusing the whole commit if
    any line now exceeds current stock rather than silently shipping a
    partial order (enhancement 5). Builds one real Order (its ship_*
    columns taken from ShipToForm's own cleaned data, not the
    customer's raw on-file address -- enhancement 6) and one real
    OrderDetail per cart line, then decrements each product's
    units_in_stock, all inside a single transaction. The session cart
    is only cleared after that succeeds.

    The stock decrement uses Product.objects.filter(...).update(...)
    with an F() expression rather than reading units_in_stock into
    Python and subtracting -- the subtraction happens inside the
    database itself, atomically, so two near-simultaneous commits can't
    both read the same stale stock value and both believe they
    succeeded.
    """
    if _cart_access_denied(request, customer_id):
        return redirect("djtraders:customer_detail", customer_id=customer_id)

    if request.method != "POST":
        return redirect("djtraders:order_build", customer_id=customer_id)

    cart = request.session.get("cart")
    if not cart or cart.get("customer_id") != customer_id or not cart.get("lines"):
        return redirect("djtraders:order_build", customer_id=customer_id)

    customer = get_object_or_404(Customer, pk=customer_id)
    cart_lines = _cart_lines(cart)
    if not cart_lines:
        return redirect("djtraders:order_build", customer_id=customer_id)

    form = OrderCommitForm(request.POST)
    ship_to_form = ShipToForm(request.POST)

    if form.is_valid() and ship_to_form.is_valid():
        # Re-check stock at commit time -- a line's stock may have
        # changed since it was added to the cart (clean() on
        # OrderDetailForm only checked at add-time). Refuses the whole
        # order if any line now exceeds what's actually in stock.
        stock_errors = []
        for line in cart_lines:
            current_stock = line.product.units_in_stock or 0
            if line.quantity > current_stock:
                stock_errors.append(
                    f"{line.product.product_name}: only {current_stock} in stock, "
                    f"{line.quantity} requested."
                )

        if stock_errors:
            cart_total = sum(line.line_total for line in cart_lines)
            detail_form = OrderDetailForm()
            categories = Category.objects.order_by("category_name")
            context = {
                "customer": customer,
                "cart_lines": cart_lines,
                "cart_total": cart_total,
                "detail_form": detail_form,
                "categories": categories,
                "commit_form": form,
                "ship_to_form": ship_to_form,
                "stock_errors": stock_errors,
            }
            return render(request, "djtraders/order_build.html", context)

        order = form.save(commit=False)
        order.customer = customer
        order.order_date = timezone.now().date()
        order.ship_name = ship_to_form.cleaned_data["ship_name"]
        order.ship_address = ship_to_form.cleaned_data["ship_address"]
        order.ship_city = ship_to_form.cleaned_data["ship_city"]
        order.ship_region = ship_to_form.cleaned_data["ship_region"]
        order.ship_postal_code = ship_to_form.cleaned_data["ship_postal_code"]
        order.ship_country = ship_to_form.cleaned_data["ship_country"]

        with transaction.atomic():
            order.save()
            OrderDetail.objects.bulk_create(
                OrderDetail(
                    order=order,
                    product=line.product,
                    unit_price=line.unit_price,
                    quantity=line.quantity,
                    discount=line.discount,
                )
                for line in cart_lines
            )
            # Atomic, database-side decrement -- see this view's own
            # docstring for why F() is used instead of a Python
            # read-then-subtract.
            for line in cart_lines:
                Product.objects.filter(pk=line.product.product_id).update(
                    units_in_stock=models.F("units_in_stock") - line.quantity
                )

        del request.session["cart"]
        return redirect("djtraders:customer_detail", customer_id=customer_id)

    cart_total = sum(line.line_total for line in cart_lines)
    detail_form = OrderDetailForm()
    categories = Category.objects.order_by("category_name")
    context = {
        "customer": customer,
        "cart_lines": cart_lines,
        "cart_total": cart_total,
        "detail_form": detail_form,
        "categories": categories,
        "commit_form": form,
        "ship_to_form": ship_to_form,
    }
    return render(request, "djtraders/order_build.html", context)


def order_delete(request, order_id):
    """
    Cancels a placed order -- a real, hard DELETE -- but only on the
    same calendar day it was placed.
    """
    order = get_object_or_404(Order, pk=order_id)

    if _order_access_denied(request, order):
        return redirect("djtraders:home")

    if request.method != "POST":
        return redirect("djtraders:order_detail", order_id=order.order_id)

    if order.order_date is None or order.order_date != timezone.now().date():
        return redirect("djtraders:order_detail", order_id=order.order_id)

    customer_id = order.customer_id
    order.delete()

    if customer_id:
        return redirect("djtraders:customer_detail", customer_id=customer_id)
    return redirect("djtraders:home")


def product_create(request):
    """
    Employee-only. Builds a blank, unsaved Product on GET and writes it
    only when a valid form is POSTed.
    """
    if not request.session.get("current_user"):
        return redirect("djtraders:product_list")

    if request.method == "POST":
        form = ProductEditForm(request.POST, instance=Product(discontinued=0))
        if form.is_valid():
            highest = Product.objects.aggregate(Max("product_id"))["product_id__max"]
            form.instance.product_id = (highest or 0) + 1
            form.save()
            return redirect("djtraders:product_list")
    else:
        form = ProductEditForm(instance=Product(discontinued=0))

    context = {"product": form.instance, "form": form, "new_product": True}
    return render(request, "djtraders/product_edit.html", context)


def product_edit(request, product_id):
    """Employee-only edit; ?confirm_discontinue=1 shows the in-page prompt."""
    product = get_object_or_404(Product, pk=product_id)

    if not request.session.get("current_user"):
        return redirect("djtraders:product_detail", product_id=product_id)

    if request.method == "POST":
        form = ProductEditForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect("djtraders:product_detail", product_id=product.product_id)
    else:
        form = ProductEditForm(instance=product)

    confirm_discontinue = request.GET.get("confirm_discontinue") == "1"
    context = {"product": product, "form": form, "confirm_discontinue": confirm_discontinue}
    return render(request, "djtraders/product_edit.html", context)


def product_discontinue(request, product_id):
    """Soft delete: flags the product discontinued. Employee-only, POST-only."""
    if not request.session.get("current_user"):
        return redirect("djtraders:product_list")

    if request.method == "POST":
        product = get_object_or_404(Product, pk=product_id)
        product.discontinued = 1
        product.date_discontinued = timezone.now().date()
        product.save()

    return redirect("djtraders:product_list")


def product_edit_form(request, product_id):
    """
    Hand-rolled plain-form edit, same approach as customer_edit_form.
    """
    product = get_object_or_404(Product, pk=product_id)

    if not request.session.get("current_user"):
        return redirect("djtraders:product_detail", product_id=product_id)

    error = None
    if request.method == "POST":
        product_name = request.POST.get("product_name", "").strip()
        if not product_name:
            error = "Product Name is required."
        else:
            product.product_name = product_name
            product.quantity_per_unit = request.POST.get("quantity_per_unit", "")
            product.supplier_id = request.POST.get("supplier") or None
            product.category_id = request.POST.get("category") or None
            product.unit_price = request.POST.get("unit_price") or None
            product.units_in_stock = request.POST.get("units_in_stock") or None
            product.units_on_order = request.POST.get("units_on_order") or None
            product.reorder_level = request.POST.get("reorder_level") or None
            product.save()
            return redirect("djtraders:product_detail", product_id=product.product_id)

    context = {
        "product": product,
        "error": error,
        "suppliers": Supplier.objects.order_by("company_name"),
        "categories": Category.objects.order_by("category_name"),
    }
    return render(request, "djtraders/product_edit_form.html", context)

def supplier_login_view(request):
    """
    Supplier login -- same hand-rolled plain-session pattern as
    customer_login_view/login_view. Supplier has no real password
    column (unlike Customer), so postal_code stands in as the
    credential, the same kind of stand-in Employee.authenticate uses
    (birth_date's year) for a model with no real password field.
    """
    request.session.pop("current_user", None)
    request.session.pop("customer_id", None)
    request.session.pop("supplier_id", None)

    error = None
    if request.method == "POST":
        supplier_id = request.POST.get("supplier_id", "")
        postal_code = request.POST.get("postal_code", "").strip()
        try:
            supplier = Supplier.objects.get(pk=supplier_id)
        except Supplier.DoesNotExist:
            supplier = None
        if supplier is not None and supplier.postal_code and supplier.postal_code.strip() == postal_code:
            request.session["supplier_id"] = supplier.supplier_id
            return redirect("djtraders:supplier_reorder")
        error = "Incorrect supplier/postal code combination."

    suppliers = Supplier.objects.order_by("company_name")
    context = {"suppliers": suppliers, "error": error}
    return render(request, "djtraders/supplier_login.html", context)


def supplier_logout_view(request):
    """Clears "supplier_id" from the session, logging the supplier out."""
    request.session.pop("supplier_id", None)
    return redirect("djtraders:home")


# Extra Credit B: one reorder unit = this many units added to
# units_on_order per "Request Reorder" click. Stated explicitly here
# and in the submission write-up.
REORDER_UNIT_QUANTITY = 50


def supplier_reorder(request):
    """
    Self-service page for a logged-in supplier: every product they
    supply, flagging which ones need reordering. A product is flagged
    when its units_in_stock is at or below its own reorder_level AND
    units_on_order doesn't already cover that gap -- units_on_order
    alone exceeding reorder_level means an order already in flight is
    expected to resolve the shortage, so it's not flagged again.
    """
    supplier_id = request.session.get("supplier_id")
    if not supplier_id:
        return redirect("djtraders:supplier_login")

    supplier = get_object_or_404(Supplier, pk=supplier_id)
    products = supplier.product_set.order_by("product_name")

    product_rows = []
    for product in products:
        reorder_level = product.reorder_level or 0
        in_stock = product.units_in_stock or 0
        on_order = product.units_on_order or 0
        needs_reorder = in_stock <= reorder_level and on_order <= reorder_level
        product_rows.append({
            "product": product,
            "needs_reorder": needs_reorder,
        })

    context = {
        "supplier": supplier,
        "product_rows": product_rows,
        "reorder_unit_quantity": REORDER_UNIT_QUANTITY,
    }
    return render(request, "djtraders/supplier_reorder.html", context)


def supplier_request_reorder(request, product_id):
    """
    POST-only: a supplier adds one reorder unit (REORDER_UNIT_QUANTITY)
    to a flagged product's units_on_order. Only lets a supplier act on
    their own products -- a product whose supplier doesn't match the
    logged-in session is refused.
    """
    supplier_id = request.session.get("supplier_id")
    if not supplier_id:
        return redirect("djtraders:supplier_login")

    if request.method == "POST":
        product = get_object_or_404(Product, pk=product_id)
        if str(product.supplier_id) == str(supplier_id):
            Product.objects.filter(pk=product_id).update(
                units_on_order=models.F("units_on_order") + REORDER_UNIT_QUANTITY
            )

    return redirect("djtraders:supplier_reorder")