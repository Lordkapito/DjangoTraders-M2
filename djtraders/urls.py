"""
URL configuration for the djtraders app.

Each Django *app* gets its own urls.py so its routes stay self-contained;
the project-level urls.py (DjangoTraders/urls.py) "includes" this file
under a prefix. Every route below is a path() call bound to a name --
templates/views reverse() a URL by that name (e.g.
"djtraders:customer_detail") instead of hard-coding the path string, so
a path can change here without hunting down every place it's linked
from.

Path converters (<str:customer_id>, <int:order_id>, ...) capture a
segment of the URL and pass it to the view as a keyword argument, typed
to match that model's primary key -- <str:...> for Customer's
CharField id, <int:...> for the AutoField ids (Product, Order,
Employee).

A few routes need a specific order in urlpatterns below: customer_create_url
must come before customer_detail_url, since <str:customer_id> would
otherwise happily match the literal word "create" as a customer_id
(Django tries patterns top to bottom and stops at the first match).

order_build/order_add_line/order_commit are keyed by customer_id, not
an order_id -- an in-progress order is only ever session state
(request.session["cart"], see views.py) until order_commit writes it
to the database, so there's no Order row yet to key a URL by. order_
detail/order_delete act on a real, already-placed Order row, so they
stay keyed by order_id.
"""
from django.urls import path

from . import views

# NAMESPACE for every route below -- lets templates/reverse() use
# "djtraders:customer_list" instead of a bare "customer_list", avoiding
# name collisions as more apps are added.
app_name = "djtraders"

# GET /djtraders/ -> views.home. An empty path means "the root of
# whatever prefix this urls.py was include()'d under" (djtraders/).
home_url = path("", views.home, name="home")

# GET /djtraders/customers/ -> views.customer_list
customer_list_url = path("customers/", views.customer_list, name="customer_list")

# GET /djtraders/products/ -> views.product_list
product_list_url = path("products/", views.product_list, name="product_list")

# GET/POST /djtraders/customers/create/ -> views.customer_create
# Must come before customer_detail_url below in urlpatterns (see this
# file's own docstring).
customer_create_url = path("customers/create/", views.customer_create, name="customer_create")

# "<str:customer_id>" is a path converter: matches a non-slash segment
# and passes it to the view as customer_id (str, matching Customer's
# CharField primary key -- an int converter would reject "ALFKI").
customer_detail_url = path(
    "customers/<str:customer_id>/", views.customer_detail, name="customer_detail"
)

# <int:order_id> -- Order.order_id is an integer PK.
order_detail_url = path(
    "orders/<int:order_id>/", views.order_detail, name="order_detail"
)

# GET/POST /djtraders/login/ -> views.login_view
login_url = path("login/", views.login_view, name="login")

# GET /djtraders/logout/ -> views.logout_view
logout_url = path("logout/", views.logout_view, name="logout")

# <int:product_id> -- Product.product_id is an integer PK.
product_detail_url = path(
    "products/<int:product_id>/", views.product_detail, name="product_detail"
)

# GET/POST /djtraders/customer-login/ -> views.customer_login_view
customer_login_url = path(
    "customer-login/", views.customer_login_view, name="customer_login"
)

# GET /djtraders/customer-logout/ -> views.customer_logout_view
customer_logout_url = path(
    "customer-logout/", views.customer_logout_view, name="customer_logout"
)

# GET/POST /djtraders/customers/<customer_id>/edit-form/ -> views.customer_edit_form
customer_edit_form_url = path(
    "customers/<str:customer_id>/edit-form/", views.customer_edit_form, name="customer_edit_form"
)

# GET/POST /djtraders/customers/<customer_id>/edit/ -> views.customer_edit
customer_edit_url = path(
    "customers/<str:customer_id>/edit/",
    views.customer_edit,
    name="customer_edit",
)

# POST /djtraders/customers/<customer_id>/delete/ -> views.customer_delete
customer_delete_url = path(
    "customers/<str:customer_id>/delete/", views.customer_delete, name="customer_delete"
)

customer_reactivate_url = path(
    "customers/<str:customer_id>/reactivate/", views.customer_reactivate, name="customer_reactivate"
)
# <int:employee_id> -- Employee.employee_id is an integer PK.
employee_detail_url = path(
    "employees/<int:employee_id>/", views.employee_detail, name="employee_detail"
)

# POST /djtraders/customers/<customer_id>/orders/create/ -> views.order_create
order_create_url = path(
    "customers/<str:customer_id>/orders/create/", views.order_create, name="order_create"
)

# GET /djtraders/customers/<customer_id>/orders/build/ -> views.order_build
order_build_url = path(
    "customers/<str:customer_id>/orders/build/", views.order_build, name="order_build"
)

# POST /djtraders/customers/<customer_id>/orders/add-line/ -> views.order_add_line (AJAX)
order_add_line_url = path(
    "customers/<str:customer_id>/orders/add-line/", views.order_add_line, name="order_add_line"
)

# POST /djtraders/customers/<customer_id>/orders/commit/ -> views.order_commit
order_commit_url = path(
    "customers/<str:customer_id>/orders/commit/", views.order_commit, name="order_commit"
)

# POST /djtraders/orders/<order_id>/delete/ -> views.order_delete
order_delete_url = path(
    "orders/<int:order_id>/delete/", views.order_delete, name="order_delete"
)

product_create_url = path("products/create/", views.product_create, name="product_create")
product_edit_form_url = path(
    "products/<int:product_id>/edit-form/", views.product_edit_form, name="product_edit_form"
)
product_edit_url = path(
    "products/<int:product_id>/edit/", views.product_edit, name="product_edit"
)
product_discontinue_url = path(
    "products/<int:product_id>/discontinue/", views.product_discontinue, name="product_discontinue"
)
# POST /djtraders/customers/<customer_id>/orders/remove-line/ -> views.order_remove_line (AJAX)
order_remove_line_url = path(
    "customers/<str:customer_id>/orders/remove-line/", views.order_remove_line, name="order_remove_line"
)

# POST /djtraders/customers/<customer_id>/orders/clear/ -> views.order_clear
order_clear_url = path(
    "customers/<str:customer_id>/orders/clear/", views.order_clear, name="order_clear"
)

supplier_login_url = path("supplier-login/", views.supplier_login_view, name="supplier_login")
supplier_logout_url = path("supplier-logout/", views.supplier_logout_view, name="supplier_logout")
supplier_reorder_url = path("supplier/reorder/", views.supplier_reorder, name="supplier_reorder")
supplier_request_reorder_url = path(
    "supplier/reorder/<int:product_id>/request/", views.supplier_request_reorder, name="supplier_request_reorder"
)
# region [CONCEPT] why this list must be named "urlpatterns"
# urlpatterns is the one name Django's URL resolver actually looks for in
# this module -- it must be called exactly that (not e.g. "urls" or
# "routes") for the project-level urls.py's include("djtraders.urls") to
# find these routes at all. Each entry above is just a plain variable
# (home_url, customer_list_url, ...); this list is what turns them into
# the app's real, ordered set of routes.
# endregion
urlpatterns = [
    home_url,
    customer_list_url,
    product_list_url,
    customer_create_url,
    customer_detail_url,
    order_detail_url,
    login_url,
    logout_url,
    product_create_url,
    product_edit_form_url,
    product_edit_url,
    product_discontinue_url,
    product_detail_url,
    customer_login_url,
    customer_logout_url,
    customer_edit_form_url,
    customer_edit_url,
    employee_detail_url,
    customer_delete_url,
    customer_reactivate_url,
    order_create_url,
    order_build_url,
    order_add_line_url,
    order_commit_url,
    order_delete_url,
    order_remove_line_url,
    order_clear_url,
    supplier_login_url,
    supplier_logout_url,
    supplier_reorder_url,
    supplier_request_reorder_url,
]
