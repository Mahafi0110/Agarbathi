from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .cloud import upload_image, validate_image
from .models import Category, ContactMessage, Coupon, Order, OrderItem, Product, Review, WholesaleEnquiry


class ImageUploadForm(forms.ModelForm):
    """Adds a plain file picker; the file is streamed to Cloudinary on save."""
    image_file = forms.ImageField(
        required=False,
        label="Image",
        help_text="JPEG, PNG or WebP, up to 5 MB. Uploaded to Cloudinary with automatic quality and format.",
        validators=[validate_image],
    )


class CloudinaryAdminMixin:
    def save_model(self, request, obj, form, change):
        upload = form.cleaned_data.get("image_file")
        if upload:
            obj.image_url = upload_image(upload)
        super().save_model(request, obj, form, change)

    @admin.display(description="Image")
    def thumb(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="height:48px;width:48px;object-fit:cover;border:1px solid #D4AF37">', obj.image_url)
        return "-"


class CategoryForm(ImageUploadForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "description", "show_in_menu"]


class ProductForm(ImageUploadForm):
    class Meta:
        model = Product
        fields = ["title", "slug", "description", "pack_info", "price", "mrp", "wholesale_price", "wholesale_min_qty", "category", "stock", "is_featured", "is_active"]

    def clean(self):
        data = super().clean()
        if data.get("mrp") and data.get("price") and data["mrp"] < data["price"]:
            self.add_error("mrp", "MRP should not be lower than the selling price.")
        return data


@admin.register(Category)
class CategoryAdmin(CloudinaryAdminMixin, admin.ModelAdmin):
    form = CategoryForm
    list_display = ("thumb", "name", "slug", "show_in_menu")
    list_editable = ("show_in_menu",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(CloudinaryAdminMixin, admin.ModelAdmin):
    form = ProductForm
    list_display = ("thumb", "title", "category", "price", "mrp", "stock", "is_featured", "is_active")
    list_filter = ("category", "is_active", "is_featured")
    list_editable = ("price", "stock", "is_active")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        ("Product", {"fields": ("title", "slug", "description", "pack_info", "category")}),
        ("Retail price and stock", {"fields": ("price", "mrp", "stock")}),
        ("Wholesale rate", {"fields": ("wholesale_price", "wholesale_min_qty")}),
        ("Image", {"fields": ("image_file",)}),
        ("Visibility", {"fields": ("is_featured", "is_active")}),
    )


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "percent_off", "flat_off", "min_order", "valid_until", "used_count", "max_uses", "is_active")
    list_editable = ("is_active",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "title", "verified", "created_at")
    list_filter = ("rating", "verified")
    search_fields = ("title", "comment", "product__title")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "title", "unit_price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone", "city", "total", "payment_method", "payment_status", "status", "created_at")
    list_filter = ("status", "payment_method", "payment_status", "created_at")
    list_editable = ("status", "payment_status")
    search_fields = ("full_name", "phone", "email", "razorpay_payment_id")
    readonly_fields = ("user", "full_name", "phone", "email", "address", "city", "pincode", "subtotal", "discount_amount",
                       "shipping_fee", "total", "coupon_code", "payment_method", "razorpay_order_id",
                       "razorpay_payment_id", "created_at")
    inlines = [OrderItemInline]
    actions = ["mark_packed", "mark_shipped", "mark_delivered"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Mark selected orders as packed")
    def mark_packed(self, request, queryset):
        queryset.exclude(status="cancelled").update(status="packed")

    @admin.action(description="Mark selected orders as shipped")
    def mark_shipped(self, request, queryset):
        queryset.exclude(status="cancelled").update(status="shipped")

    @admin.action(description="Mark selected orders as delivered (Cash on Delivery orders become paid)")
    def mark_delivered(self, request, queryset):
        queryset.filter(payment_method="cod").exclude(status="cancelled").update(payment_status="paid")
        queryset.exclude(status="cancelled").update(status="delivered")


@admin.register(WholesaleEnquiry)
class WholesaleEnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "business_name", "phone", "city", "monthly_quantity", "created_at", "handled")
    list_filter = ("handled", "created_at")
    list_editable = ("handled",)
    search_fields = ("name", "business_name", "phone", "city")
    readonly_fields = ("created_at",)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "subject", "created_at", "handled")
    list_filter = ("handled", "created_at")
    list_editable = ("handled",)
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("created_at",)
