"""Cloudinary helper: upload a file and return a secure, optimised delivery URL."""
import cloudinary.uploader
from cloudinary import CloudinaryImage
from django.core.exceptions import ValidationError

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024


def validate_image(upload):
    if upload.content_type not in ALLOWED_TYPES:
        raise ValidationError("Upload a JPEG, PNG or WebP image.")
    if upload.size > MAX_BYTES:
        raise ValidationError("Image must be 5 MB or smaller.")


def upload_image(upload, folder="pooja-shop"):
    """Stream the file to Cloudinary; return a secure URL using q_auto and f_auto."""
    result = cloudinary.uploader.upload(upload, folder=folder, resource_type="image")
    return CloudinaryImage(result["public_id"]).build_url(
        secure=True, quality="auto", fetch_format="auto", version=result.get("version")
    )
