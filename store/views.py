import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Case, Count, DecimalField, F, Q, When
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from . import payments
from .forms import CheckoutForm, ReviewForm, SignupForm, WholesaleForm
from .models import Coupon, Order, OrderItem, Product, Review, Wishlist

MAX_LINE_QTY = 500
MAX_LINES = 50
TOKEN_SALT = "order-done"
logger = logging.getLogger(__name__)


# ---------- helpers ----------
def base_products():
    """Active products with their average rating and review count."""
    return (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .annotate(avg_rating=Avg("reviews__rating"), review_count=Count("reviews"))
    )


def _safe_next(request, default):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return default


def _dec(value):
    try:
        d = Decimal(value)
    except (InvalidOperation, TypeError):
        return None
    return d if d.is_finite() and d >= 0 else None


def _token(order):
    return signing.dumps(order.pk, salt=TOKEN_SALT)


def _breakdown(subtotal, coupon):
    discount = coupon.discount_for(subtotal) if coupon else Decimal("0.00")
    after = subtotal - discount
    shipping = Decimal("0.00") if after >= settings.FREE_SHIPPING_ABOVE else settings.SHIPPING_FEE
    return discount, shipping, after + shipping


def _cancel_order(order, payment_status=None):
    """Put stock (and the coupon use) back and mark the order cancelled."""
    with transaction.atomic():
        for item in order.items.all():
            if item.product_id:
                Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)
        if order.coupon_code:
            Coupon.objects.filter(code=order.coupon_code, used_count__gt=0).update(used_count=F("used_count") - 1)
        order.status = "cancelled"
        if payment_status:
            order.payment_status = payment_status
        order.save(update_fields=["status", "payment_status"])


# ---------- storefront ----------
def home(request):
    products = base_products()
    return render(request, "store/home.html", {"featured": products.filter(is_featured=True)[:8], "latest": products[:4]})


SORTS = {
    "low": ["price"],
    "high": ["-price"],
    "name": ["title"],
    "discount": ["-discount_pct", "-created_at"],
    "rating": [F("avg_rating").desc(nulls_last=True), "-review_count"],
}


def product_list(request, slug=None):
    from .models import Category

    products = base_products().annotate(
        discount_pct=Case(
            When(mrp__gt=F("price"), then=(F("mrp") - F("price")) * 100 / F("mrp")),
            default=Decimal("0"),
            output_field=DecimalField(max_digits=6, decimal_places=2),
        )
    )
    category = get_object_or_404(Category, slug=slug) if slug else None
    if category:
        products = products.filter(category=category)

    q = request.GET.get("q", "").strip()[:80]
    if q:
        products = products.filter(Q(title__icontains=q) | Q(description__icontains=q))
    lo, hi = _dec(request.GET.get("min")), _dec(request.GET.get("max"))
    if lo is not None:
        products = products.filter(price__gte=lo)
    if hi is not None:
        products = products.filter(price__lte=hi)
    instock = request.GET.get("instock") == "1"
    if instock:
        products = products.filter(stock__gt=0)

    sort = request.GET.get("sort", "")
    products = products.order_by(*SORTS.get(sort, ["-created_at"]))

    page = Paginator(products, 12).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "store/product_list.html", {
        "page": page, "category": category, "q": q, "sort": sort, "instock": instock,
        "min": request.GET.get("min", ""), "max": request.GET.get("max", ""),
        "querystring": params.urlencode(),
    })


def product_detail(request, slug):
    product = get_object_or_404(base_products(), slug=slug)
    related = base_products().filter(category=product.category).exclude(pk=product.pk)[:4]

    recent_ids = [i for i in request.session.get("recent", []) if i != product.pk]
    recent_map = {p.pk: p for p in base_products().filter(pk__in=recent_ids)}
    recent = [recent_map[i] for i in recent_ids if i in recent_map][:4]
    request.session["recent"] = ([product.pk] + recent_ids)[:8]

    counts = {r["rating"]: r["n"] for r in product.reviews.values("rating").annotate(n=Count("id"))}
    total = sum(counts.values())
    distribution = [(s, counts.get(s, 0), round(counts.get(s, 0) * 100 / total) if total else 0) for s in (5, 4, 3, 2, 1)]

    user_review = None
    if request.user.is_authenticated:
        user_review = product.reviews.filter(user=request.user).first()
    form = ReviewForm(instance=user_review) if user_review else ReviewForm()
    return render(request, "store/product_detail.html", {
        "product": product, "related": related, "recent": recent,
        "reviews": product.reviews.select_related("user")[:20], "distribution": distribution,
        "review_form": form, "user_review": user_review,
    })


@login_required
@require_POST
def review_submit(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    form = ReviewForm(request.POST)
    if form.is_valid():
        verified = OrderItem.objects.filter(order__user=request.user, order__status="delivered", product=product).exists()
        Review.objects.update_or_create(
            product=product, user=request.user, defaults={**form.cleaned_data, "verified": verified}
        )
        messages.success(request, "Thank you. Your review is saved.")
    else:
        messages.error(request, "Choose a rating and fill in the title and review.")
    return redirect(product.get_absolute_url() + "#reviews")


# ---------- cart, checkout, payment ----------
def _parse_cart(raw):
    """Parse the localStorage cart posted by the browser. Prices are NEVER trusted from it."""
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return None
    if not isinstance(data, list) or not 0 < len(data) <= MAX_LINES:
        return None
    lines = {}
    for row in data:
        try:
            pid, qty = int(row["id"]), int(row["qty"])
        except (KeyError, TypeError, ValueError):
            return None
        if not 1 <= qty <= MAX_LINE_QTY:
            return None
        lines[pid] = lines.get(pid, 0) + qty
    return lines


def _place_order(request, form, lines):
    """Validate stock and coupon, then save the order. Returns (order, error)."""
    with transaction.atomic():
        products = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=lines, is_active=True)}
        if len(products) != len(lines):
            return None, "An item in your cart is no longer available."
        short = [p.title for pid, p in products.items() if p.stock < lines[pid]]
        if short:
            return None, "Not enough stock for: " + ", ".join(short)

        subtotal = sum((products[pid].unit_price_for(qty) * qty for pid, qty in lines.items()), Decimal("0"))
        coupon = None
        code = form.cleaned_data.get("coupon_code", "").strip().upper()
        if code:
            coupon = Coupon.objects.select_for_update().filter(code=code).first()
            problem = coupon.problem_for(subtotal) if coupon else "That coupon code is not valid."
            if problem:
                return None, problem
        discount, shipping, total = _breakdown(subtotal, coupon)

        order = form.save(commit=False)
        order.user = request.user if request.user.is_authenticated else None
        order.subtotal, order.discount_amount, order.shipping_fee, order.total = subtotal, discount, shipping, total
        order.coupon_code = coupon.code if coupon else ""
        order.save()
        for pid, qty in lines.items():
            p = products[pid]
            OrderItem.objects.create(order=order, product=p, title=p.title, unit_price=p.unit_price_for(qty), quantity=qty)
            Product.objects.filter(pk=pid).update(stock=F("stock") - qty)
        if coupon:
            Coupon.objects.filter(pk=coupon.pk).update(used_count=F("used_count") + 1)
    return order, None


@require_http_methods(["GET", "POST"])
def cart(request):
    if request.method == "GET":
        initial = {}
        if request.user.is_authenticated:
            initial = {"full_name": request.user.get_full_name(), "email": request.user.email}
            last = request.user.orders.first()
            if last:
                initial.update(full_name=last.full_name, phone=last.phone, email=last.email or request.user.email,
                               address=last.address, city=last.city, pincode=last.pincode)
        return render(request, "store/cart.html", {"form": CheckoutForm(initial=initial)})

    form = CheckoutForm(request.POST)
    lines = _parse_cart(request.POST.get("cart_json"))
    error = None
    if lines is None:
        error = "Your cart is empty or could not be read. Add items and try again."
    elif form.is_valid():
        order, error = _place_order(request, form, lines)
        if order and order.payment_method == "razorpay":
            try:
                order.razorpay_order_id = payments.create_order(order)
                order.save(update_fields=["razorpay_order_id"])
            except Exception:
                _cancel_order(order, "failed")
                error = "Online payment is not available right now. Please try again or choose Cash on Delivery."
            else:
                request.session["pay_order_id"] = order.pk
                return redirect("store:pay", pk=order.pk)
        elif order:
            return redirect("store:order_done", token=_token(order))
    return render(request, "store/cart.html", {"form": form, "error": error})


def pay(request, pk):
    order = get_object_or_404(Order, pk=pk, payment_method="razorpay")
    if request.session.get("pay_order_id") != order.pk or order.payment_status != "pending" or order.status == "cancelled":
        return redirect("store:cart")
    return render(request, "store/pay.html", {
        "order": order,
        "key_id": settings.RAZORPAY_KEY_ID,
        "amount_paise": int(order.total * 100),
        "callback_url": request.build_absolute_uri("/payment/callback/"),
    })


@csrf_exempt  # Razorpay posts here from its own site; the signature check below is the protection
@require_POST
def payment_callback(request):
    rp_order_id = request.POST.get("razorpay_order_id", "")
    if not rp_order_id:  # failure posts carry the order id inside error[metadata]
        try:
            rp_order_id = json.loads(request.POST.get("error[metadata]", "{}")).get("order_id", "")
        except ValueError:
            rp_order_id = ""
    order = Order.objects.filter(razorpay_order_id=rp_order_id, payment_method="razorpay").first() if rp_order_id else None
    if not order:
        return redirect("store:home")

    payment_id = request.POST.get("razorpay_payment_id", "")
    if payments.verify_signature(rp_order_id, payment_id, request.POST.get("razorpay_signature", "")):
        order.razorpay_payment_id = payment_id
        order.payment_status = "refund_due" if order.status == "cancelled" else "paid"
        order.save(update_fields=["razorpay_payment_id", "payment_status"])
    elif order.payment_status == "pending":
        _cancel_order(order, "failed")
    return redirect("store:order_done", token=_token(order))


def order_done(request, token):
    try:
        pk = signing.loads(token, salt=TOKEN_SALT, max_age=60 * 60 * 24 * 7)
    except signing.BadSignature:
        raise Http404
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk)
    return render(request, "store/order_done.html", {"order": order})


# ---------- accounts ----------
@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("store:home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        messages.success(request, "Welcome. Your account is ready.")
        return redirect(_safe_next(request, "store:home"))
    return render(request, "store/signup.html", {"form": form})


@login_required
def account_orders(request):
    return render(request, "store/account_orders.html", {"orders": request.user.orders.prefetch_related("items")})


@login_required
def account_order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk, user=request.user)
    return render(request, "store/account_order.html", {"order": order})


@login_required
@require_POST
def cancel_my_order(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.can_cancel:
        _cancel_order(order, "refund_due" if order.payment_status == "paid" else None)
        messages.success(request, f"Order #{order.pk} is cancelled." + (" Your refund will be processed by the shop." if order.payment_status == "refund_due" else ""))
    else:
        messages.error(request, "This order has already been packed and can no longer be cancelled here.")
    return redirect("store:account_order", pk=order.pk)


@login_required
def wishlist(request):
    ids = Wishlist.objects.filter(user=request.user).values("product_id")
    return render(request, "store/wishlist.html", {"products": base_products().filter(pk__in=ids)})


@login_required
@require_POST
def wishlist_toggle(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    obj, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if created:
        messages.success(request, f"Saved {product.title} to your wishlist.")
    else:
        obj.delete()
        messages.info(request, f"Removed {product.title} from your wishlist.")
    return redirect(_safe_next(request, "store:wishlist"))


# ---------- wholesale ----------
def _one_line(text):
    return " ".join(str(text).split())


def _notify_wholesale(enquiry):
    """Email the owner (and confirm to the customer). A mail problem never breaks the form."""
    owner = settings.WHOLESALE_NOTIFY_EMAIL
    if not owner:
        return
    lines = [
        f"Name: {_one_line(enquiry.name)}",
        f"Business: {_one_line(enquiry.business_name) or '-'}",
        f"Phone: {_one_line(enquiry.phone)}",
        f"Email: {_one_line(enquiry.email) or '-'}",
        f"City: {_one_line(enquiry.city)}",
        f"Packs per month: {_one_line(enquiry.monthly_quantity) or '-'}",
        "",
        enquiry.message or "(no message)",
    ]
    try:
        EmailMessage(
            subject=f"New wholesale enquiry from {_one_line(enquiry.name)}",
            body="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[owner],
            reply_to=[enquiry.email] if enquiry.email else None,
        ).send()
        if enquiry.email:
            EmailMessage(
                subject="We received your wholesale enquiry",
                body=f"Hello {_one_line(enquiry.name)},\n\nThank you for your wholesale enquiry. "
                     "We will call you soon with rates.\n\nShubham Pooja",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[enquiry.email],
            ).send()
    except Exception:
        logger.exception("Could not send wholesale enquiry email for enquiry %s", enquiry.pk)


@require_http_methods(["GET", "POST"])
def wholesale(request):
    form = WholesaleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not form.cleaned_data.get("website"):  # bots fill the hidden field; skip saving
            _notify_wholesale(form.save())
        messages.success(request, "Thank you. We have your enquiry and will call you soon with wholesale rates.")
        return redirect("store:wholesale")
    deals = base_products().filter(wholesale_min_qty__gt=0, wholesale_price__isnull=False)[:6]
    return render(request, "store/wholesale.html", {"form": form, "deals": deals})
