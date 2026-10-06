from django.conf import settings

from .models import Category, Wishlist


def shop(request):
    user = getattr(request, "user", None)
    wishlist_ids = set()
    if user is not None and user.is_authenticated:
        wishlist_ids = set(Wishlist.objects.filter(user=user).values_list("product_id", flat=True))
    return {
        "nav_categories": Category.objects.all(),
        "wishlist_ids": wishlist_ids,
        "free_shipping_above": settings.FREE_SHIPPING_ABOVE,
        "shipping_fee": settings.SHIPPING_FEE,
    }
