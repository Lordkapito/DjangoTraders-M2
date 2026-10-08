"""
Django Forms for the djtraders app.

A Form (or ModelForm, below) is Django's own way of describing an HTML
form's fields, validation, and rendering as a Python class, instead of
hand-written <input> tags. customer_edit_form.html (the "plain" edit
page) skips this entirely -- it reads request.POST fields directly and
writes them onto the Customer instance itself. CustomerEditForm below
is the same edit, built the ModelForm way instead, rendered by
customer_edit.html through django-crispy-forms' {% crispy %} tag (see
settings.py's INSTALLED_APPS/CRISPY_* settings). Both pages render the
identical field grid on purpose, so the real difference stands out:
CustomerEditForm declares its fields and layout once as a class, and
gets validation Django builds in for free (a required field, a max
length) without any hand-written checks in the view.

CustomerEditForm's fields also carry a running example of Django's
three validation layers, each one enforcing the same rule a different
way:
  - Browser layer (courtesy only): an HTML5 pattern=/required/min=
    attribute on the widget, set in __init__ below. Blocks an obviously
    bad value before a request is even sent -- but proves nothing,
    since disabling JS or editing the request in DevTools skips it
    entirely.
  - Server layer (the real check): a clean_<field>() method (or the
    cross-field clean() on OrderCommitForm below) re-checks the same
    rule and raises ValidationError if it fails. This is the one layer
    that can't be bypassed from the browser.
  - Database layer (final backstop, when there is one): a column
    constraint like max_length that Postgres enforces regardless of
    the two layers above. Some rules (no digits in a company name, a
    required contact name) have no database layer behind them at all --
    the schema simply doesn't express that rule, so the form is the
    only thing enforcing it.
phone (clean_phone), company_name/city (clean_company_name/clean_city,
no-digits), and contact_name (required=True override in __init__) are
four small, independent examples of this pattern -- useful as a
template for writing a new business rule elsewhere in the app.
"""
import re

from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Layout, Row
from django import forms
from django.core.exceptions import ValidationError

from datetime import date, timedelta

from .models import Customer, Order, OrderDetail, Product

# Extra Credit A: once a single line's quantity reaches this many
# units, a 10% volume discount applies automatically, on top of
# (never replacing) whatever discount the customer entered manually
# (discount_percent, below) -- the larger of the two wins.
VOLUME_DISCOUNT_THRESHOLD = 20
VOLUME_DISCOUNT_PERCENT = 10
# Digits, spaces, parentheses, and dashes only, 7-20 characters -- loose
# enough to accept "(206) 555-9857" or "030-0074321", tight enough to
# reject obvious garbage. Shared by the widget's HTML5 pattern attribute
# (browser layer) and clean_phone() below (server layer), so the two
# can never quietly drift apart.
PHONE_PATTERN = r"[0-9()\-\s]{7,20}"

# No digit characters anywhere -- "[^0-9]*" reads as "zero or more
# non-digit characters," which as a FULL match (see clean_company_name/
# clean_city below, and the pattern= attribute __init__ sets) means "the
# whole string, and there's not a single digit in it." Shared the same
# way PHONE_PATTERN is, between the browser-layer widget attribute and
# the server-layer clean_<field>() checks.
NO_DIGITS_PATTERN = r"[^0-9]*"


class CustomerEditForm(forms.ModelForm):
    """
    Edits every Customer field except customer_id (the primary key --
    ModelForm never includes it unless told to) and inactive_date
    (deliberately left out of Meta.fields below, since it's not part of
    this edit page).

    self.helper (a crispy-forms FormHelper) is what {% crispy form %}
    (customer_edit.html) actually reads to render this form --
    without one, crispy still renders every field, but adds no submit
    button at all, and stacks every field one per row instead of the
    grid self.helper.layout describes below. The HTML(...) at the end
    of that layout is a real, hand-written <button> tag: crispy's own
    Submit/StrictButton layout objects both render a plain <input>,
    which can't hold the icon this project's buttons all carry.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].widget.attrs.update({
            "pattern": PHONE_PATTERN,
            "title": "Digits, spaces, parentheses, and dashes only (7-20 characters).",
        })
        self.fields["company_name"].widget.attrs.update({
            "pattern": NO_DIGITS_PATTERN,
            "title": "No numbers in a company name.",
        })
        self.fields["city"].widget.attrs.update({
            "pattern": NO_DIGITS_PATTERN,
            "title": "No numbers in a city name.",
        })
        self.fields["contact_name"].required = True
        self.helper = FormHelper()
        self.helper.form_id = "customer-edit-form"
        self.helper.layout = Layout(
            Row(
                Column("company_name", css_class="col-md-6"),
                Column("contact_name", css_class="col-md-6"),
            ),
            Row(
                Column("contact_title", css_class="col-md-6"),
                Column("phone", css_class="col-md-6"),
            ),
            Row(
                Column("fax", css_class="col-md-6"),
                Column("password", css_class="col-md-6"),
            ),
            Row(
                Column("address", css_class="col-md-8"),
                Column("city", css_class="col-md-4"),
            ),
            Row(
                Column("region", css_class="col-md-4"),
                Column("postal_code", css_class="col-md-4"),
                Column("country", css_class="col-md-4"),
            ),
            HTML(
                """
                <div class="d-flex gap-2 mt-3 justify-content-end">
                    <button type="submit" class="btn dt-btn-primary-customer w3-hover-shadow" title="Save changes">
                        <i class="fa-solid fa-floppy-disk me-1 dt-icon-success"></i>Save
                    </button>
                    <div class="dt-link-wrap btn dt-btn-secondary-customer w3-hover-shadow">
                        {% if new_customer %}
                            <a href="{% url 'djtraders:customer_list' %}" title="Cancel -- nothing has been saved yet">
                                <i class="fa-solid fa-xmark me-1 dt-icon-danger"></i>Cancel
                            </a>
                        {% else %}
                            <a href="{% url 'djtraders:customer_detail' customer.customer_id %}" title="Cancel and discard changes">
                                <i class="fa-solid fa-xmark me-1 dt-icon-danger"></i>Cancel
                            </a>
                        {% endif %}
                    </div>
                </div>
                """
            ),
        )

    class Meta:
        model = Customer
        fields = [
            "company_name",
            "contact_name",
            "contact_title",
            "address",
            "city",
            "region",
            "postal_code",
            "country",
            "phone",
            "fax",
            "password",
        ]
        widgets = {
            "password": forms.PasswordInput(render_value=True),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "")
        if phone and not re.fullmatch(PHONE_PATTERN, phone):
            raise ValidationError(
                "Enter a valid phone number (digits, spaces, parentheses, "
                "and dashes only, 7-20 characters)."
            )
        return phone

    def clean_company_name(self):
        name = self.cleaned_data.get("company_name", "")
        if not re.fullmatch(NO_DIGITS_PATTERN, name):
            raise ValidationError("Company name can't contain numbers.")
        return name

    def clean_city(self):
        city = self.cleaned_data.get("city", "")
        if city and not re.fullmatch(NO_DIGITS_PATTERN, city):
            raise ValidationError("City can't contain numbers.")
        return city


class ProductEditForm(forms.ModelForm):
    """
    Create/edit form for Product, the crispy-rendered counterpart to
    product_edit_form.html's hand-rolled version -- same field grid,
    same comparison customer_edit/customer_edit_form made for Customer.
    discontinued, date_discontinued and product_id are deliberately not
    fields here -- product_discontinue/product_create set those, not
    the user.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        supplier = self.fields["supplier"]
        supplier.queryset = supplier.queryset.order_by("company_name")
        supplier.label_from_instance = lambda s: s.company_name
        supplier.empty_label = "Select a supplier..."
        supplier.widget.attrs.update({"class": "form-select"})

        category = self.fields["category"]
        category.queryset = category.queryset.order_by("category_name")
        category.label_from_instance = lambda c: c.category_name
        category.empty_label = "Select a category..."
        category.widget.attrs.update({"class": "form-select"})

        self.fields["unit_price"].widget.attrs.update({"min": 0, "step": "0.01"})

        self.helper = FormHelper()
        self.helper.form_id = "product-edit-form"
        self.helper.layout = Layout(
            Row(
                Column("product_name", css_class="col-md-6"),
                Column("quantity_per_unit", css_class="col-md-6"),
            ),
            Row(
                Column("supplier", css_class="col-md-6"),
                Column("category", css_class="col-md-6"),
            ),
            Row(
                Column("unit_price", css_class="col-md-3"),
                Column("units_in_stock", css_class="col-md-3"),
                Column("units_on_order", css_class="col-md-3"),
                Column("reorder_level", css_class="col-md-3"),
            ),
            HTML(
                """
                <div class="d-flex gap-2 mt-3 justify-content-end">
                    <button type="submit" class="btn dt-btn-primary-supplier w3-hover-shadow" title="Save changes">
                        <i class="fa-solid fa-floppy-disk me-1 dt-icon-success"></i>Save
                    </button>
                    <div class="dt-link-wrap btn dt-btn-secondary-supplier w3-hover-shadow">
                        {% if new_product %}
                            <a href="{% url 'djtraders:product_list' %}" title="Cancel -- nothing has been saved yet">
                                <i class="fa-solid fa-xmark me-1 dt-icon-danger"></i>Cancel
                            </a>
                        {% else %}
                            <a href="{% url 'djtraders:product_detail' product.product_id %}" title="Cancel and discard changes">
                                <i class="fa-solid fa-xmark me-1 dt-icon-danger"></i>Cancel
                            </a>
                        {% endif %}
                    </div>
                </div>
                """
            ),
        )

    class Meta:
        model = Product
        fields = [
            "product_name", "quantity_per_unit", "supplier", "category",
            "unit_price", "units_in_stock", "units_on_order", "reorder_level",
        ]

    def clean_unit_price(self):
        """
        Server layer. PLACEHOLDER RULE -- replace with Assignment 2's
        actual Product rule once confirmed. Nothing in the schema stops
        a negative price, so this check is the only thing enforcing it.
        """
        price = self.cleaned_data.get("unit_price")
        if price is not None and price < 0:
            raise ValidationError("Unit price can't be negative.")
        return price


class ProductSelectWidget(forms.Select):
    """
    Adds data-category-id and data-stock to each rendered <option>,
    read by DjangoTraders.js's FilterProductOptions (category) and
    AddOrderLineItem's browser-layer stock warning. Purely a
    client-side convenience -- OrderDetailForm's own queryset and
    clean() (server-side, below) are the real, unbypassable gates
    regardless of what these attributes show.

    category_by_product_id/stock_by_product_id are both set by
    OrderDetailForm.__init__ below, from the same queryset already
    fetched for the dropdown -- no extra per-option database query here.

    value, as Django hands it to create_option for a ModelChoiceField
    (which "product" is -- a ForeignKey), is NOT a plain int: it's
    wrapped in Django's own ModelChoiceIteratorValue, which does not
    support int(value) directly. The real underlying value is read off
    its own .value attribute instead.
    """
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        category_by_product_id = getattr(self, "category_by_product_id", {})
        stock_by_product_id = getattr(self, "stock_by_product_id", {})

        category_id = ""
        stock = ""
        if value not in (None, ""):
            # ModelChoiceIteratorValue wraps the real pk in .value --
            # unwrap it before trying to use it as a product_id.
            raw_value = value.value if hasattr(value, "value") else value
            try:
                product_id = int(raw_value)
            except (TypeError, ValueError):
                product_id = None
            if product_id is not None:
                mapped_category = category_by_product_id.get(product_id)
                if mapped_category is not None:
                    category_id = str(mapped_category)
                stock = str(stock_by_product_id.get(product_id, ""))

        option["attrs"]["data-category-id"] = category_id
        option["attrs"]["data-stock"] = stock
        return option


class OrderDetailForm(forms.ModelForm):
    """
    Adds one line item (product + quantity + discount) to a draft Order.

    unit_price (required, non-null on OrderDetail -- djtraders/models.py)
    is set by the view from the chosen product's own unit_price, not
    asked for here. discount_percent is a plain, non-model field (0-100,
    a percentage) -- converted to the 0.0-1.0 fraction OrderDetail.discount
    actually stores by clean_discount_percent below, the same "form
    field isn't the database column" shape CustomerEditForm's
    required=True overrides already use elsewhere in this file.

    allow_high_discount (passed in by order_add_line, djtraders/views.py,
    based on whether an employee session is operating this cart) gates
    the >10% rule -- enhancement 7 (an employee building a cart for any
    customer) will flip this once that's built; until then it's always
    False for an ordinary customer session, so >10% is always refused.

    product uses ProductSelectWidget (above) instead of a plain Select,
    so each <option> carries data-category-id/data-stock for
    DjangoTraders.js to read.
    """
    discount_percent = forms.DecimalField(
        label="Discount %",
        min_value=0,
        max_value=100,
        decimal_places=2,
        initial=0,
        required=False,
    )

    def __init__(self, *args, allow_high_discount=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_high_discount = allow_high_discount

        # Only non-discontinued products are offered -- same reasoning
        # as Product.search's own show_all=False default (models.py).
        # select_related("category") avoids a query per row when
        # building category_by_product_id just below.
        products = self.fields["product"].queryset.filter(discontinued=0).select_related("category")
        self.fields["product"].queryset = products
        self.fields["product"].empty_label = "Select a product..."
        self.fields["product"].widget = ProductSelectWidget(attrs={"class": "form-select"})
        # Swapping in a new widget instance does not automatically carry
        # over the field's queryset-derived choices -- ModelChoiceField
        # normally keeps its widget's own .choices in sync only through
        # its original widget instance. Re-point the new widget's
        # .choices at the field's own ModelChoiceIterator explicitly, or
        # the <select> renders with zero <option> tags despite the field
        # itself correctly reporting choices when queried directly.
        self.fields["product"].widget.choices = self.fields["product"].choices
        self.fields["product"].widget.category_by_product_id = {
            product.product_id: product.category_id for product in products
        }
        self.fields["product"].widget.stock_by_product_id = {
            product.product_id: product.units_in_stock or 0 for product in products
        }
        # Product (models.py) has no __str__ of its own, so a plain
        # ModelChoiceField would render each <option> as the default
        # "Product object (5)" -- label_from_instance overrides that
        # per-choice display text (not the value actually submitted,
        # which is still just the product's pk) with something a
        # student picking from this dropdown can actually read.
        self.fields["product"].label_from_instance = (
            lambda product: f"{product.product_name} (${product.unit_price or 0:.2f})"
        )
        # Browser layer (courtesy): a real HTML5 min= on the rendered
        # <input>, blocking an obviously-bad quantity (zero or negative)
        # before a request is even sent. Not a guarantee -- same caveat
        # as every other pattern= attribute in this file.
        self.fields["quantity"].widget.attrs.update({"min": 1, "class": "form-control"})
        # Browser layer (courtesy only) for the discount rule below --
        # caps the field at 10 for an ordinary session; server-side
        # clean_discount_percent is the actual, unbypassable gate.
        self.fields["discount_percent"].widget.attrs.update({
            "min": 0,
            "max": 100 if allow_high_discount else 10,
            "step": "0.1",
            "class": "form-control",
        })

    class Meta:
        model = OrderDetail
        fields = ["product", "quantity"]

    def clean_quantity(self):
        """
        Server layer: quantity has to be a positive number.
        """
        quantity = self.cleaned_data.get("quantity")
        if quantity is not None and quantity < 1:
            raise ValidationError("Quantity must be at least 1.")
        return quantity

    def clean_discount_percent(self):
        """
        Server layer -- the real, unbypassable gate. A blank field is
        treated as 0% (no discount), same as every optional field
        elsewhere in this project. Anything above 10% is refused unless
        allow_high_discount was set (an employee session operating this
        cart, order_add_line).
        """
        percent = self.cleaned_data.get("discount_percent")
        if percent is None:
            return 0
        if percent < 0:
            raise ValidationError("Discount can't be negative.")
        if percent > 10 and not self.allow_high_discount:
            raise ValidationError(
                "Discounts above 10% need employee approval -- have an employee process this line."
            )
        if percent > 100:
            raise ValidationError("Discount can't exceed 100%.")
        return percent

    def clean(self):
        """
        Cross-field check: quantity against the selected product's own
        units_in_stock (enhancement 5). Also applies Extra Credit A's
        volume-based default discount -- once quantity reaches
        VOLUME_DISCOUNT_THRESHOLD, a VOLUME_DISCOUNT_PERCENT discount
        applies automatically, raising discount_percent to at least
        that value without touching whatever the customer already typed
        -- a manually entered discount larger than the volume default
        is never reduced by this.
        """
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        quantity = cleaned_data.get("quantity")
        if product is not None and quantity is not None:
            in_stock = product.units_in_stock or 0
            if quantity > in_stock:
                self.add_error(
                    "quantity",
                    f"Only {in_stock} in stock -- reduce the quantity."
                )
            # Extra Credit A: volume-based default discount.
            if quantity >= VOLUME_DISCOUNT_THRESHOLD:
                entered_percent = cleaned_data.get("discount_percent") or 0
                if entered_percent < VOLUME_DISCOUNT_PERCENT:
                    cleaned_data["discount_percent"] = VOLUME_DISCOUNT_PERCENT
                    self.volume_discount_applied = True
        return cleaned_data

    @property
    def discount_fraction(self):
        """0.0-1.0, as OrderDetail.discount actually stores it (models.py)."""
        percent = self.cleaned_data.get("discount_percent") or 0
        return float(percent) / 100

class ShipToForm(forms.Form):
    """
    A validated ship-to address, shown next to OrderCommitForm's own
    fields at commit time. A plain Form, not a ModelForm -- nothing
    forces this address to be the customer's own on-file Customer
    address (order_build.html's old read-only display), since a
    customer may legitimately want to ship an order somewhere else.
    Initial values are the customer's own current address
    (order_build, djtraders/views.py), so the common case (ship to
    yourself) needs no typing, but every field stays editable.

    order_commit (djtraders/views.py) copies this form's cleaned_data
    straight onto the real Order's ship_* columns at commit, replacing
    the old customer.address/.city/etc. copy it used to do.
    """
    ship_name = forms.CharField(label="Ship To (Name)", max_length=40)
    ship_address = forms.CharField(label="Address", max_length=60, required=False)
    ship_city = forms.CharField(label="City", max_length=15, required=False)
    ship_region = forms.CharField(label="Region", max_length=15, required=False)
    ship_postal_code = forms.CharField(label="Postal Code", max_length=10, required=False)
    ship_country = forms.CharField(label="Country", max_length=15)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

    def clean_ship_name(self):
        """
        Server layer. Required (unlike the model's own Customer fields,
        which mostly allow blank) -- an order has to ship to *someone*,
        the same "form is stricter than the column" shape every other
        business rule in this file uses.
        """
        name = self.cleaned_data.get("ship_name", "").strip()
        if not name:
            raise ValidationError("Ship-to name is required.")
        return name

    def clean_ship_country(self):
        """Server layer. Required -- same reasoning as ship_name above."""
        country = self.cleaned_data.get("ship_country", "").strip()
        if not country:
            raise ValidationError("Ship-to country is required.")
        return country

class OrderCommitForm(forms.ModelForm):
    """
    Sets an order's employee/required_date/shipped_date at commit time
    -- the one point where a cart becomes a real, placed Order.
    order_date itself is set by the view (order_commit, djtraders/
    views.py), not by this form -- it's always today, on commit, not a
    value anyone picks.

    employee is a real, required field on this form even though the
    model column itself is nullable (Order.employee, models.py,
    SET_NULL) -- required here is a business rule ("every placed order
    needs an employee of record"), not a database constraint, the same
    "form is stricter than the column" shape as everywhere else in this
    file. __init__ below overrides the ModelForm default (a nullable
    model field would otherwise make this field optional on its own)
    and gives it a label_from_instance, the same reason OrderDetailForm's
    product field needs one -- Employee (models.py) has no __str__ of
    its own, so without this override each option would render as
    Django's default "Employee object (5)".

    required_date/shipped_date both come with a sensible default (two
    weeks out / one week out from today) computed in the view and
    passed in as this form's initial= values, but both stay real,
    editable fields -- a business-convention starting guess, not a
    fixed rule.

    Used unbound (no instance=) -- order_commit (djtraders/views.py)
    calls form.save(commit=False) to build a brand-new Order. A
    ModelForm behaves as a create form or an update form purely based
    on whether instance= was passed at construction, not on anything
    declared here.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].required = True
        self.fields["employee"].empty_label = "Select an employee..."
        self.fields["employee"].queryset = self.fields["employee"].queryset.order_by(
            "last_name", "first_name"
        )
        self.fields["employee"].label_from_instance = (
            lambda employee: f"{employee.first_name} {employee.last_name}"
        )
        self.fields["employee"].widget.attrs.update({"class": "form-select"})

    class Meta:
        model = Order
        fields = ["employee", "required_date", "shipped_date"]
        widgets = {
            "required_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "shipped_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        today = date.today()
        for field_name, label in (("required_date", "Required date"), ("shipped_date", "Ship-by date")):
            value = cleaned_data.get(field_name)
            if value is not None and value < today:
                self.add_error(field_name, f"{label} can't be before today's order date.")
        return cleaned_data


def default_required_date():
    """order_date (today, at commit) + 2 weeks -- see OrderCommitForm."""
    return date.today() + timedelta(weeks=2)


def default_shipped_date():
    """order_date (today, at commit) + 1 week -- see OrderCommitForm."""
    return date.today() + timedelta(weeks=1)