from django.urls import path

from cf_es_mirror.django import views

urlpatterns = [
    path("webhook-update", views.webhook_update, name="webhook-update"),
]

app_name = "cf_es_mirror"
