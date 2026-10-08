"""
Cleaned-up models generated from `manage.py inspectdb` (see
rev_engineer_models.py for the raw, unedited output). inspectdb reads
an existing database's tables and writes a first-draft model per table,
but leaves manual work behind: every model here is set managed=False
(this app reads a database Django didn't create, so it should never try
to migrate these tables), model names were singularized (Category,
Customer, ...) and reordered so each is defined before anything that
references it by bare class name, and every foreign key was given a
real on_delete (inspectdb defaults to DO_NOTHING) matching what should
actually happen when the related row is removed.

Beyond that baseline, most models add a few computed @property values
(e.g. Order.order_total, Customer.formatted_address) and a couple carry
classmethods used by views.py: *.search() backs a list page's search
form, and Employee.authenticate/Customer.authenticate back this app's
two hand-rolled logins (no django.contrib.auth involved). Each one's
own docstring below explains the specifics.
"""

from django.db import models


class Category(models.Model):
    """
    A product category. Defined before Product (the model that references
    it) so Product.category can use the bare class name instead of a
    forward-reference string - see the module docs for why order
    matters here.
    """
    category_id = models.SmallIntegerField(primary_key=True)
    category_name = models.CharField(max_length=15)
    description = models.TextField(blank=True, null=True)
    picture = models.BinaryField(blank=True, null=True)

    class Meta:
        """
        Meta configures the model/table itself, not a database column.
        managed=False: table already exists, Django shouldn't migrate it.
        db_table: the real table name, since it doesn't match Django's
        default ("djtraders_category").
        """
        managed = False
        db_table = 'categories'


class Customer(models.Model):
    """A DjangoTraders customer. No foreign keys, so no on_delete concerns."""
    customer_id = models.CharField(primary_key=True, max_length=5)
    company_name = models.CharField(max_length=40)
    contact_name = models.CharField(max_length=30, blank=True, null=True)
    contact_title = models.CharField(max_length=30, blank=True, null=True)
    address = models.CharField(max_length=60, blank=True, null=True)
    city = models.CharField(max_length=15, blank=True, null=True)
    region = models.CharField(max_length=15, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    country = models.CharField(max_length=15, blank=True, null=True)
    phone = models.CharField(max_length=24, blank=True, null=True)
    fax = models.CharField(max_length=24, blank=True, null=True)
    password = models.CharField(db_column='Password', max_length=64, blank=True, null=True)  # Field name made lowercase.
    inactive_date = models.DateField(blank=True, null=True)

    @property
    def formatted_address(self):
        """
        This customer's address, city, region, postal_code, and country
        joined into one line (blank ones skipped), instead of five
        separate fields -- used by customer_detail.html.
        """
        parts = [self.address, self.city, self.region, self.postal_code, self.country]
        return ", ".join(part for part in parts if part)

    @classmethod
    def search(cls, company_name="", contact_name="", contact_title="", city="", country=""):
        """
        Filters customers by any combination of company name, contact
        name, contact title, city, and country, returning every customer
        when none are given. Used by customer_list (djtraders/views.py)
        to back its search form.

        A @classmethod (not a regular instance method) because it builds
        a brand-new queryset from scratch (cls.objects...) rather than
        acting on one existing Customer -- there's no single customer
        instance to call it on yet, so it needs the class itself (cls),
        not self. This also lets it be called directly on the model
        (Customer.search(...)) instead of needing an instance first.

        cls: the Customer class itself, passed in automatically since
        this is a classmethod -- not a particular customer instance.

        company_name/contact_name use "icontains" (a case-insensitive
        substring match) since they're free-text fields -- someone
        typing part of a name expects a match anywhere in it, regardless
        of case. contact_title/city/country use an exact match instead,
        since their values always come from a dropdown of values already
        on record, not free text -- there's nothing partial (or
        case-varied) to match against.
        """
        queryset = cls.objects.order_by("company_name")
        if company_name:
            queryset = queryset.filter(company_name__icontains=company_name)
        if contact_name:
            queryset = queryset.filter(contact_name__icontains=contact_name)
        if contact_title:
            queryset = queryset.filter(contact_title=contact_title)
        if city:
            queryset = queryset.filter(city=city)
        if country:
            queryset = queryset.filter(country=country)
        return queryset

    @classmethod
    def authenticate(cls, customer_id, password):
        """
        Looks up the customer by the ID entered in the login form and
        checks their password: a direct string compare against this
        customer's own password column (the customers table already has
        real values seeded there -- unlike Employee, which has no
        password column of its own and uses a derived birth-year stand-in
        instead). Returns the matching Customer on success, or None if
        the customer_id doesn't exist or the password doesn't match.

        Same shape as Employee.authenticate (djtraders/models.py) -- a
        direct comparison, no Django auth system (django.contrib.auth)
        involved on either side of this app's two logins.
        """
        customer = cls.objects.filter(pk=customer_id).first()
        if customer is None:
            return None
        if customer.password != password:
            return None
        return customer

    @classmethod
    def generate_customer_id(cls, company_name):
        """
        Builds a new, unique 5-letter customer_id from a company name,
        the same style Northwind's own existing rows already use (e.g.
        "Alfreds Futterkiste" -> ALFKI) -- called only from customer_
        create's POST handler (djtraders/views.py), and only after the
        rest of the new customer's fields have already passed
        CustomerEditForm's own validation. A customer never types or
        picks this value themselves; it's derived from data they've
        already entered, the same way Order.order_id (djtraders/
        models.py) comes from the database's own auto-increment rather
        than from whoever is placing the order.

        Starts from the company name's own letters (spaces, punctuation,
        and digits stripped, then uppercased) and takes the first five,
        padding a short name with "X" if it doesn't have five letters to
        give. customer_id is this model's own primary key (above), so
        that column's own uniqueness constraint is the real, final
        guarantee against a collision -- same principle as Order's
        auto-increment column, just enforced on a value this code
        proposes instead of one the database assigns outright. The loop
        below only exists so a plausible, already-available ID reaches
        the database on the first try, rather than a user ever seeing
        that constraint reject one.
        """
        letters = "".join(char for char in company_name.upper() if char.isalpha())
        base = (letters + "XXXXX")[:5]

        if not cls.objects.filter(pk=base).exists():
            return base

        # base alone is taken -- replace its trailing digits with a
        # counter (e.g. ALFK1, ALFK2, ... ALFK9, ALF10, ALF11, ...) until
        # an unused 5-character value turns up.
        suffix = 1
        while suffix < 100_000:
            digits = str(suffix)
            candidate = base[: 5 - len(digits)] + digits
            if not cls.objects.filter(pk=candidate).exists():
                return candidate
            suffix += 1

        # Practically unreachable for a class-sized dataset -- every
        # 5-character value derived from this base is already taken.
        raise ValueError(f"Could not generate a unique customer_id from {company_name!r}")

    class Meta:
        managed = False
        db_table = 'customers'


class Employee(models.Model):
    """A DjangoTraders employee. Has a self-referencing FK for its manager (reports_to)."""
    employee_id = models.SmallIntegerField(primary_key=True)
    last_name = models.CharField(max_length=20)
    first_name = models.CharField(max_length=10)
    title = models.CharField(max_length=30, blank=True, null=True)
    title_of_courtesy = models.CharField(max_length=25, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    hire_date = models.DateField(blank=True, null=True)
    address = models.CharField(max_length=60, blank=True, null=True)
    city = models.CharField(max_length=15, blank=True, null=True)
    region = models.CharField(max_length=15, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    country = models.CharField(max_length=15, blank=True, null=True)
    home_phone = models.CharField(max_length=24, blank=True, null=True)
    extension = models.CharField(max_length=4, blank=True, null=True)
    photo = models.BinaryField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    photo_path = models.CharField(max_length=255, blank=True, null=True)
    # region [CONCEPT] self-referencing FK (reports_to)
    # FK to Employee itself, for the manager hierarchy: gives us
    # employee.reports_to.first_name (up to the manager) and
    # employee.employee_set.all() (down to their reports).
    # SET_NULL so deleting a manager just clears the link, not their reports.
    # endregion
    reports_to = models.ForeignKey('self', models.SET_NULL, db_column='reports_to', blank=True, null=True)

    @property
    def formatted_address(self):
        """
        This employee's address, city, region, postal_code, and country
        joined into one line (blanks skipped), same pattern as
        Customer.formatted_address -- used by employee_detail.html.
        """
        parts = [self.address, self.city, self.region, self.postal_code, self.country]
        return ", ".join(part for part in parts if part)

    @classmethod
    def authenticate(cls, employee_id, password):
        """
        Looks up the employee picked in the login form and checks their
        password: the 4-digit year of their own birth_date, as a string
        (e.g. birth_date of 1985-03-12 -> password "1985"). Returns the
        matching Employee on success, or None if the employee_id doesn't
        exist, has no birth_date on record, or the password is wrong.
        """
        employee = cls.objects.filter(pk=employee_id).first()
        if employee is None or employee.birth_date is None:
            return None
        if str(employee.birth_date.year) != password:
            return None
        return employee

    class Meta:
        managed = False
        db_table = 'employees'


class OrderDetail(models.Model):
    """
    A single line item on an order (composite primary key: order_id + product_id).
    """
    # region [WARNING] order+product form the composite PK, not a separate id column
    # order and product below are ordinary FKs, but they're ALSO the two
    # columns making up this table's primary key (CompositePrimaryKey, not
    # a separate id column) - a product can only appear once per order.
    # endregion
    pk = models.CompositePrimaryKey('order_id', 'product_id')

    # FK to Order (order_detail.order.order_date, order.orderdetail_set.all()).
    # CASCADE: a line item is meaningless without its order.
    order = models.ForeignKey('Order', models.CASCADE)

    # FK to Product (order_detail.product.product_name, product.orderdetail_set.all()).
    # PROTECT: refuse to delete a product still on a historical order line.
    product = models.ForeignKey('Product', models.PROTECT)
    unit_price = models.FloatField()
    quantity = models.SmallIntegerField()
    discount = models.FloatField()

    @property
    def line_total(self):
        """
        This line's own revenue: unit_price times quantity, minus the
        discount fraction. A @property, not a field, since it's derived
        from the three fields above rather than stored -- Order.order_total
        sums this same property across every line instead of repeating
        the formula.
        """
        return self.unit_price * self.quantity * (1 - self.discount)

    class Meta:
        managed = False
        db_table = 'order_details'


class Order(models.Model):
    """
    A customer order. The customer/employee/shipper links are all nullable, so
    on_delete=SET_NULL keeps the order history intact even if one of those
    related records is later removed.
    """
    # region [WHY] AutoField only for order_id
    # SmallAutoField, unlike this app's other primary keys: order_id's
    # database column is backed by a real auto-incrementing sequence, so
    # the other models' IDs (category_id, etc.) aren't - they're fixed
    # reference IDs the database won't generate for you.
    # endregion
    order_id = models.SmallAutoField(primary_key=True)
    order_date = models.DateField(blank=True, null=True)
    required_date = models.DateField(blank=True, null=True)
    shipped_date = models.DateField(blank=True, null=True)
    freight = models.FloatField(blank=True, null=True)
    ship_name = models.CharField(max_length=40, blank=True, null=True)
    ship_address = models.CharField(max_length=60, blank=True, null=True)
    ship_city = models.CharField(max_length=15, blank=True, null=True)
    ship_region = models.CharField(max_length=15, blank=True, null=True)
    ship_postal_code = models.CharField(max_length=10, blank=True, null=True)
    ship_country = models.CharField(max_length=15, blank=True, null=True)

    # FK to Customer (order.customer.company_name, customer.order_set.all()).
    customer = models.ForeignKey(Customer, models.SET_NULL, blank=True, null=True)

    # FK to Employee (order.employee.last_name, employee.order_set.all()).
    employee = models.ForeignKey(Employee, models.SET_NULL, blank=True, null=True)

    # FK to Shipper, stored in a column named ship_via (db_column below) --
    # that's the existing table's column name, not shipper_id.
    ship_via = models.ForeignKey('Shipper', models.SET_NULL, db_column='ship_via', blank=True, null=True)

    @property
    def order_total(self):
        """
        This order's total revenue -- every line item's own line_total
        (OrderDetail.line_total) added together, not recomputed here.
        order.customer is already a real field (the FK above), not a
        property -- it needs no extra code to access.
        """
        return sum(line.line_total for line in self.orderdetail_set.all())

    @property
    def formatted_ship_address(self):
        """
        This order's ship_address, ship_city, ship_region,
        ship_postal_code, and ship_country joined into one line (blanks
        skipped), instead of four separate fields -- used by
        order_detail.html, same pattern as Customer.formatted_address.
        """
        parts = [self.ship_address, self.ship_city, self.ship_region, self.ship_postal_code, self.ship_country]
        return ", ".join(part for part in parts if part)

    class Meta:
        managed = False
        db_table = 'orders'


class Product(models.Model):
    """
    A DjangoTraders product. Supplier and category are both nullable, so removing
    either one just clears the link (SET_NULL) instead of touching the product.
    """
    product_id = models.SmallIntegerField(primary_key=True)
    product_name = models.CharField(max_length=40)
    quantity_per_unit = models.CharField(max_length=20, blank=True, null=True)
    unit_price = models.FloatField(blank=True, null=True)
    units_in_stock = models.SmallIntegerField(blank=True, null=True)
    units_on_order = models.SmallIntegerField(blank=True, null=True)
    reorder_level = models.SmallIntegerField(blank=True, null=True)
    discontinued = models.IntegerField()
    date_discontinued = models.DateField(blank=True, null=True)
    
    # FK to Supplier (product.supplier.company_name, supplier.product_set.all()).
    supplier = models.ForeignKey('Supplier', models.SET_NULL, blank=True, null=True)

    # FK to Category (product.category.category_name, category.product_set.all()).
    category = models.ForeignKey(Category, models.SET_NULL, blank=True, null=True)

    @property
    def is_discontinued(self):
        """
        discontinued is a plain 1/0 IntegerField, not a BooleanField -- this
        maps it to a real bool so callers can write product.is_discontinued
        instead of comparing product.discontinued to 1 by hand. A @property,
        not a field, so it's computed fresh each access, no migration needed.
        """
        return bool(self.discontinued)

    @classmethod
    def search(cls, product_name="", category_id="", show_all=False):
        """
        Filters products by an optional product name and/or category,
        returning every non-discontinued product by default. Used by
        product_list (djtraders/views.py) to back its search form.

        product_name uses "icontains" (a case-insensitive substring
        match), same reasoning as Customer.search's company_name.
        category_id uses an exact match, since its value comes from a
        dropdown of categories already on record, not free text.
        show_all=False filters out discontinued products (discontinued
        is a plain 1/0 field, not is_discontinued -- that's a Python
        property, not something the database can filter on); show_all=
        True skips that filter, showing discontinued products too.
        """
        queryset = cls.objects.order_by("product_name")
        # if there is a product_name, filter by it; 
        if product_name:
            queryset = queryset.filter(product_name__icontains=product_name)

        # if there is a category_id, filter by it;
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # if show_all is False, filter out discontinued products (discontinued=1);
        if not show_all:
            queryset = queryset.filter(discontinued=0)

        return queryset

    @property
    def total_revenue(self):
        """
        Total revenue this product has generated -- every order line it
        appears on, each one's own line_total (OrderDetail.line_total)
        added together. product.orderdetail_set is the reverse side of
        OrderDetail.product's FK (every OrderDetail row for this product).
        """
        return sum(line.line_total for line in self.orderdetail_set.all())

    @property
    def units_sold(self):
        """
        Total quantity of this product sold -- every order line's
        quantity added together, across every order it's appeared on.
        """
        return sum(line.quantity for line in self.orderdetail_set.all())

    class Meta:
        managed = False
        db_table = 'products'


class Shipper(models.Model):
    """A shipping carrier. No foreign keys."""
    shipper_id = models.SmallIntegerField(primary_key=True)
    company_name = models.CharField(max_length=40)
    phone = models.CharField(max_length=24, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'shippers'


class Supplier(models.Model):
    """A product supplier. No foreign keys."""
    supplier_id = models.SmallIntegerField(primary_key=True)
    company_name = models.CharField(max_length=40)
    contact_name = models.CharField(max_length=30, blank=True, null=True)
    contact_title = models.CharField(max_length=30, blank=True, null=True)
    address = models.CharField(max_length=60, blank=True, null=True)
    city = models.CharField(max_length=15, blank=True, null=True)
    region = models.CharField(max_length=15, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    country = models.CharField(max_length=15, blank=True, null=True)
    phone = models.CharField(max_length=24, blank=True, null=True)
    fax = models.CharField(max_length=24, blank=True, null=True)
    homepage = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'suppliers'