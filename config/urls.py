from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Pooja Shop Administration"
admin.site.site_title = "Pooja Shop Admin"
admin.site.index_title = "Inventory and orders"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("store.urls")),
]
