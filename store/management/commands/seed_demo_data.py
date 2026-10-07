"""Fill the store with demo agarbatti categories and products.

    python manage.py seed_demo_data                  # add or refresh the demo items (no pictures)
    python manage.py seed_demo_data --wipe           # first delete ALL categories and products (asks to confirm)
    python manage.py seed_demo_data --if-empty       # only seed when the store has no products (used on deploys)
    python manage.py seed_demo_data --upload-images  # also make a simple picture per item and send it to Cloudinary

Safe to run more than once: items are matched by slug, so nothing is duplicated.
"""
import io
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from store.models import Category, Coupon, Product

# (title, description, pack info, retail price, stock, featured, wholesale minimum packs)
DATA = {
    "Sandalwood Agarbatti": ("Classic chandan sticks, the everyday fragrance of the pooja room.", [
        ("Mysore Sandalwood Agarbatti", "Smooth, woody sandalwood sticks that burn evenly and leave a soft, lasting fragrance.", "100 g, about 60 sticks", "120.00", 300, True, 12),
        ("Chandan Premium Hand-Rolled", "Hand-rolled chandan sticks with a richer, creamier scent for daily aarti.", "100 g, about 50 sticks", "180.00", 200, True, 12),
        ("Kesar Chandan Agarbatti", "Saffron and sandalwood blend with a warm, festive fragrance.", "100 g, about 55 sticks", "150.00", 150, False, 12),
    ]),
    "Floral Agarbatti": ("Rose, jasmine, champa and lotus sticks for a fresh, gentle fragrance.", [
        ("Rose Agarbatti", "Fresh rose fragrance in slow-burning sticks, pleasant for daily pooja.", "100 g, about 60 sticks", "110.00", 250, True, 12),
        ("Jasmine Agarbatti", "Sweet jasmine sticks with a light, flowery aroma.", "100 g, about 60 sticks", "110.00", 220, False, 12),
        ("Champa Agarbatti", "Traditional champa fragrance loved for temples and festivals.", "100 g, about 60 sticks", "125.00", 200, True, 12),
        ("Lotus Agarbatti", "Soft lotus fragrance, calm and clean.", "100 g, about 55 sticks", "130.00", 140, False, 12),
    ]),
    "Premium Masala Agarbatti": ("Hand-rolled masala sticks with deep, resinous fragrances.", [
        ("Guggul Masala Agarbatti", "Resinous guggul masala sticks, a classic for puja and havan days.", "100 g, about 45 sticks", "160.00", 160, False, 12),
        ("Loban Masala Agarbatti", "Rich loban fragrance with a long, steady burn.", "100 g, about 45 sticks", "170.00", 150, False, 12),
        ("Mogra Masala Agarbatti", "Mogra flower masala sticks with a sweet, full aroma.", "100 g, about 45 sticks", "165.00", 130, False, 12),
    ]),
    "Dhoop Sticks and Cones": ("Thick dhoop sticks and cones for a fuller, longer fragrance.", [
        ("Sandal Dhoop Sticks", "Thick sandalwood dhoop sticks for a strong, lasting aroma.", "Pack of 20 sticks", "90.00", 260, False, 24),
        ("Herbal Dhoop Cones", "Cones made with natural herbs and guggul. Use on a holder.", "Pack of 30 cones", "140.00", 180, False, 12),
        ("Camphor Dhoop Cones", "Camphor-scented cones with a clean, sharp fragrance.", "Pack of 30 cones", "150.00", 160, False, 12),
    ]),
    "Gift and Festival Packs": ("Assorted boxes for gifting, festivals and weddings.", [
        ("Pooja Assorted Box of 6", "Six fragrances in one box, a good introduction to the range.", "6 packs of 25 sticks", "399.00", 90, True, 6),
        ("Festival Gift Hamper", "Agarbatti, dhoop cones and a holder in a gift box.", "Gift box", "799.00", 40, False, 6),
    ]),
}


# Categories left out of the menu bar (their products still show under All items)
HIDDEN_FROM_MENU = {"Premium Masala Agarbatti"}


def make_picture(title):
    """A plain ivory and gold card with the product name, just so the grid has something to show."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 800), "#FBF8F1")
    d = ImageDraw.Draw(img)
    d.rectangle([24, 24, 776, 776], outline="#D4AF37", width=6)
    try:
        font = ImageFont.load_default(size=44)
    except TypeError:  # older Pillow
        font = ImageFont.load_default()
    lines, line = [], ""
    for w in title.split():
        if len(line + " " + w) > 18 and line:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    lines.append(line)
    y = 400 - 28 * len(lines)
    for text in lines:
        width = d.textlength(text, font=font)
        d.text(((800 - width) / 2, y), text, fill="#000000", font=font)
        y += 56
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return SimpleUploadedFile(slugify(title) + ".png", buf.getvalue(), content_type="image/png")


class Command(BaseCommand):
    help = "Add demo agarbatti categories and products."

    def add_arguments(self, parser):
        parser.add_argument("--wipe", action="store_true", help="Delete ALL categories and products first.")
        parser.add_argument("--if-empty", action="store_true", help="Do nothing if the store already has products.")
        parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation with --wipe.")
        parser.add_argument("--upload-images", action="store_true",
                            help="Make a simple picture for each item and upload it to Cloudinary.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["if_empty"] and Product.objects.exists():
            self.stdout.write("Store already has products. Skipped seeding.")
            return
        if opts["wipe"]:
            if not opts["yes"]:
                answer = input(f"This deletes ALL {Product.objects.count()} products and {Category.objects.count()} categories. Type yes to continue: ")
                if answer.strip().lower() != "yes":
                    raise CommandError("Cancelled. Nothing was deleted.")
            Product.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write("Removed all old products and categories.")

        upload = None
        if opts["upload_images"]:
            from store.cloud import upload_image
            upload = upload_image

        made = 0
        for cat_name, (cat_desc, items) in DATA.items():
            category, _ = Category.objects.update_or_create(
                slug=slugify(cat_name),
                defaults={"name": cat_name, "description": cat_desc, "show_in_menu": cat_name not in HIDDEN_FROM_MENU})
            for title, desc, pack, price, stock, featured, wmin in items:
                retail = Decimal(price)
                product, created = Product.objects.update_or_create(
                    slug=slugify(title),
                    defaults={"title": title, "description": desc, "pack_info": pack, "price": retail,
                              "mrp": (retail * Decimal("1.2")).quantize(Decimal("1")),
                              "wholesale_price": (retail * Decimal("0.72")).quantize(Decimal("1")),
                              "wholesale_min_qty": wmin, "category": category, "stock": stock,
                              "is_featured": featured, "is_active": True})
                if upload and not product.image_url:
                    product.image_url = upload(make_picture(title))
                    product.save(update_fields=["image_url"])
                made += created
        Coupon.objects.get_or_create(code="WELCOME10", defaults={"percent_off": 10, "min_order": Decimal("299")})
        Coupon.objects.get_or_create(code="FESTIVE100", defaults={"flat_off": Decimal("100"), "min_order": Decimal("999")})
        self.stdout.write(self.style.SUCCESS(
            f"Done. {made} new products added, {Product.objects.count()} in the store. Demo coupons: WELCOME10 and FESTIVE100."))
