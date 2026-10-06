"""Razorpay helpers using only the standard library (no extra package needed)."""
import base64
import hashlib
import hmac
import json
import urllib.request

from django.conf import settings


def enabled():
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def create_order(order):
    """Ask Razorpay to create a payment order for this shop order; returns Razorpay's order id."""
    payload = {
        "amount": int(order.total * 100),  # paise
        "currency": "INR",
        "receipt": f"order_{order.pk}",
        "notes": {"shop_order_id": str(order.pk)},
    }
    auth = base64.b64encode(f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode()).decode()
    req = urllib.request.Request(
        "https://api.razorpay.com/v1/orders",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Basic " + auth},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)["id"]


def verify_signature(razorpay_order_id, payment_id, signature):
    """Confirm the payment really came from Razorpay (HMAC-SHA256 with your secret)."""
    if not (razorpay_order_id and payment_id and signature):
        return False
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(), f"{razorpay_order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
