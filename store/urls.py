from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "store"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("products/", views.product_list, name="shop"),
    path("products/category/<slug:slug>/", views.product_list, name="category"),
    path("shop/", RedirectView.as_view(pattern_name="store:shop", query_string=True)),  # old address
    path("product/<slug:slug>/", views.product_detail, name="product"),
    path("product/<slug:slug>/review/", views.review_submit, name="review"),

    path("wholesale/", views.wholesale, name="wholesale"),
    path("cart/", views.cart, name="cart"),
    path("pay/<int:pk>/", views.pay, name="pay"),
    path("payment/callback/", views.payment_callback, name="payment_callback"),
    path("order/thanks/<str:token>/", views.order_done, name="order_done"),

    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="store/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("account/orders/", views.account_orders, name="account_orders"),
    path("account/orders/<int:pk>/", views.account_order_detail, name="account_order"),
    path("account/orders/<int:pk>/cancel/", views.cancel_my_order, name="cancel_order"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/toggle/<int:pk>/", views.wishlist_toggle, name="wishlist_toggle"),
]
