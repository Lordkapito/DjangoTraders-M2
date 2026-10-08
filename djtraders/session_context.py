"""
Template context processors for the djtraders app -- functions Django
runs for every template render, adding whatever they return into every
template's context automatically (see settings.py's TEMPLATES
OPTIONS['context_processors'], where this module is registered).

This file could be named anything -- Django finds a context processor by
the full dotted path given in settings.py (e.g.
"djtraders.session_context.current_employee"), not by filename or
location, unlike models.py/admin.py/apps.py, which Django's app loading
looks for by that exact name. "context_processors.py" is Django's own
common convention for this (django.template.context_processors,
django.contrib.auth.context_processors), but session_context.py names
what these two functions actually do here: read who's logged in back out
of request.session.

current_employee reads "current_user" (an employee_id) back out of
request.session -- set by views.login_view on a successful login -- so
base.html's navbar can show who's logged in without every view having
to look it up and pass it in its own context by hand. current_customer
is the same idea for the customer-facing login, reading "customer_id"
(set by views.customer_login_view). Only one of the two is ever set at
a time, since login_view/customer_login_view each clear both keys on
landing (djtraders/views.py).
"""
from .models import Customer, Employee


def current_employee(request):
    """
    Looks up the Employee matching request.session["current_user"], if
    any employee is currently logged in. Returns {"current_employee": None}
    when nobody is logged in, so base.html can safely check
    {% if current_employee %} on every page, logged in or not.
    """
    employee_id = request.session.get("current_user")
    employee = Employee.objects.filter(pk=employee_id).first() if employee_id else None
    return {"current_employee": employee}


def current_customer(request):
    """
    Looks up the Customer matching request.session["customer_id"], if
    any customer is currently logged in. Returns {"current_customer": None}
    when nobody is logged in, so base.html can safely check
    {% if current_customer %} on every page, logged in or not -- same
    shape as current_employee above, for the customer-facing side.
    """
    customer_id = request.session.get("customer_id")
    customer = Customer.objects.filter(pk=customer_id).first() if customer_id else None
    return {"current_customer": customer}

def cart_summary(request):
    """
    Extra Credit C: makes the logged-in customer's in-progress cart
    available to every template (base.html's navbar dropdown), not
    just order_build.html. Returns real line summaries (product name,
    quantity, line total) and a grand total, not just a bare count --
    the navbar dropdown shows these directly. This runs once per page
    load from the server side; AddOrderLineItem/RemoveOrderLineItem
    (DjangoTraders.js) separately patch the already-rendered navbar in
    place after an AJAX add/remove, since this context processor has
    no way to re-run mid-page.
    """
    cart = request.session.get("cart")
    customer_id = request.session.get("customer_id")
    if not cart or not customer_id or cart.get("customer_id") != customer_id:
        return {"cart_item_count": 0, "cart_customer_id": None, "cart_lines_summary": [], "cart_grand_total": 0}

    from .models import Product

    lines = cart.get("lines", {})
    product_ids = [int(pid) for pid in lines]
    products_by_id = Product.objects.in_bulk(product_ids)

    summary = []
    grand_total = 0
    for product_id_str, line_data in lines.items():
        product = products_by_id.get(int(product_id_str))
        if product is None:
            continue
        unit_price = product.unit_price or 0.0
        quantity = line_data["quantity"]
        discount = line_data.get("discount", 0.0)
        line_total = unit_price * quantity * (1 - discount)
        grand_total += line_total
        summary.append({
            "name": product.product_name,
            "quantity": quantity,
            "line_total": line_total,
        })

    return {
        "cart_item_count": len(summary),
        "cart_customer_id": customer_id,
        "cart_lines_summary": summary,
        "cart_grand_total": grand_total,
    }

def current_supplier(request):
    """Mirrors current_employee/current_customer, for a logged-in supplier."""
    supplier_id = request.session.get("supplier_id")
    if not supplier_id:
        return {"current_supplier": None}
    from .models import Supplier
    try:
        return {"current_supplier": Supplier.objects.get(pk=supplier_id)}
    except Supplier.DoesNotExist:
        return {"current_supplier": None}
  