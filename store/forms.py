from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from . import payments
from .models import Order, Review, WholesaleEnquiry


class CheckoutForm(forms.ModelForm):
    payment_method = forms.ChoiceField(widget=forms.RadioSelect, label="Payment method", initial="cod")
    coupon_code = forms.CharField(required=False, max_length=30, label="Coupon code (optional)")

    class Meta:
        model = Order
        fields = ["full_name", "phone", "email", "address", "city", "pincode", "payment_method", "coupon_code"]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}
        labels = {"full_name": "Full name", "pincode": "PIN code"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("cod", "Cash on Delivery")]
        if payments.enabled():
            choices.append(("razorpay", "Pay online (UPI, cards, net banking)"))
        self.fields["payment_method"].choices = choices

    def clean_pincode(self):
        value = self.cleaned_data["pincode"].strip()
        if not value.isdigit() or len(value) != 6:
            raise forms.ValidationError("Enter a 6-digit PIN code.")
        return value


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email")


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(5, "5 - Excellent"), (4, "4 - Good"), (3, "3 - Average"), (2, "2 - Poor"), (1, "1 - Terrible")],
        coerce=int,
    )

    class Meta:
        model = Review
        fields = ["rating", "title", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 3})}


class WholesaleForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)  # honeypot: real people leave it empty

    class Meta:
        model = WholesaleEnquiry
        fields = ["name", "business_name", "phone", "email", "city", "monthly_quantity", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 3, "placeholder": "Which fragrances, pack sizes or your own brand label?"})}
        labels = {"name": "Your name", "business_name": "Shop or business name"}
