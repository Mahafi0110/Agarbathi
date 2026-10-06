# Shubham Pooja: monolithic Django pooja store

## Setup
1. `python -m venv venv && source venv/bin/activate`
2. `pip install -r requirements.txt` (do not install `python-dotenv`; it clashes with `django-dotenv`)
3. `cp .env.example .env` and fill in MySQL and Cloudinary values
4. In MySQL: `CREATE DATABASE pooja_shop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`
5. `python manage.py migrate && python manage.py createsuperuser`
6. `python manage.py runserver` then open `/admin/` to add categories and products

## Production
Set `DJANGO_DEBUG=False`, a long `DJANGO_SECRET_KEY`, your domain in `DJANGO_ALLOWED_HOSTS` and
`DJANGO_CSRF_TRUSTED_ORIGINS` (https://...), run `python manage.py collectstatic --noinput`,
then serve with `gunicorn config.wsgi`.
