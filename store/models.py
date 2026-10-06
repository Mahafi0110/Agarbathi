from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.CharField(max_length=240, blank=True)
    image_url = models.URLField(max_length=500, blank=True, editable=False)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("store:category", args=[self.slug])


class Product(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=170, unique=True)
    description = models.TextField()
    price = models.DecimalField("selling price", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    mrp = models.DecimalField("MRP (original price)", max_digits=10, decimal_places=2, null=True, blank=True,
                              help_text="Optional. If higher than the selling price, shows a strike-through and a % off badge.")
    pack_info = models.CharField(max_length=80, blank=True, help_text="For example: 100 g, about 60 sticks.")
    wholesale_price = models.DecimalField("wholesale price per pack", max_digits=10, decimal_places=2, null=True, blank=True,
                                          help_text="Optional. Price per pack when the customer buys the wholesale minimum or more.")
    wholesale_min_qty = models.PositiveIntegerField("wholesale minimum packs", default=0,
                                                    help_text="Packs needed to get the wholesale price. Leave 0 for no wholesale rate.")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    image_url = models.URLField(max_length=500, blank=True, editable=False)
    stock = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text="Untick to hide from the storefront.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("store:product", args=[self.slug])

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def low_stock(self):
        return 0 < self.stock <= 5

    @property
    def has_wholesale(self):
        return bool(self.wholesale_price and self.wholesale_min_qty and self.wholesale_price < self.price)

    def unit_price_for(self, qty):
        """Retail price, or the wholesale price once the customer buys enough packs."""
        if self.has_wholesale and qty >= self.wholesale_min_qty:
            return self.wholesale_price
        return self.price

    @property
    def discount_percent(self):
        if self.mrp and self.mrp > self.price:
            return int((self.mrp - self.price) * 100 / self.mrp)
        return 0


class Coupon(models.Model):
    code = models.CharField(max_length=30, unique=True, help_text="Customers type this at checkout. Saved in capitals.")
    percent_off = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(90)],
                                                   help_text="Percentage discount. Leave 0 to use the flat amount instead.")
    flat_off = models.DecimalField("flat amount off (Rs.)", max_digits=8, decimal_places=2, default=0)
    min_order = models.DecimalField("minimum basket (Rs.)", max_digits=8, decimal_places=2, default=0)
    valid_until = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Leave empty for unlimited.")
    used_count = models.PositiveIntegerField(default=0, editable=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def problem_for(self, subtotal):
        """Return a plain-English problem, or None if the coupon can be used."""
        if not self.is_active:
            return "This coupon is not active."
        if self.valid_until and self.valid_until < timezone.now():
            return "This coupon has expired."
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return "This coupon has been fully used."
        if subtotal < self.min_order:
            return f"Add items worth Rs. {self.min_order:.0f} or more to use this coupon."
        return None

    def discount_for(self, subtotal):
        amount = subtotal * Decimal(self.percent_off) / 100 if self.percent_off else self.flat_off
        return min(amount, subtotal).quantize(Decimal("0.01"))


class Order(models.Model):
    STATUS = [("new", "New"), ("packed", "Packed"), ("shipped", "Shipped"), ("delivered", "Delivered"), ("cancelled", "Cancelled")]
    PAYMENT_METHODS = [("cod", "Cash on Delivery"), ("razorpay", "Pay online (UPI, cards, net banking)")]
    PAYMENT_STATUS = [("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed"), ("refund_due", "Refund due")]
    STEPS = ["new", "packed", "shipped", "delivered"]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=15, validators=[RegexValidator(r"^[0-9+\- ]{8,15}$", "Enter a valid phone number.")])
    email = models.EmailField(blank=True)
    address = models.TextField()
    city = models.CharField(max_length=80)
    pincode = models.CharField(max_length=10)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    coupon_code = models.CharField(max_length=30, blank=True)

    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default="cod")
    payment_status = models.CharField(max_length=12, choices=PAYMENT_STATUS, default="pending")
    razorpay_order_id = models.CharField(max_length=60, blank=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=60, blank=True)

    status = models.CharField(max_length=12, choices=STATUS, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} - {self.full_name}"

    @property
    def step_index(self):
        return self.STEPS.index(self.status) if self.status in self.STEPS else -1

    @property
    def can_cancel(self):
        return self.status == "new"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=160)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlisted_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["-created_at"]


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=100)
    comment = models.TextField(max_length=1500)
    verified = models.BooleanField(default=False, help_text="The reviewer has a delivered order for this product.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product} - {self.rating} stars"

    @property
    def stars(self):
        return "\u2605" * self.rating + "\u2606" * (5 - self.rating)


class WholesaleEnquiry(models.Model):
    name = models.CharField(max_length=120)
    business_name = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=15, validators=[RegexValidator(r"^[0-9+\- ]{8,15}$", "Enter a valid phone number.")])
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=80)
    monthly_quantity = models.CharField("approx. packs per month", max_length=60, blank=True)
    message = models.TextField(blank=True)
    handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "wholesale enquiries"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.business_name or self.city})"
