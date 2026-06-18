from django.urls import path

from . import payment_callback_views

urlpatterns = [
    path("mtn/", payment_callback_views.mtn_momo_callback, name="finance_mtn_collection_update"),
    path("airtel/", payment_callback_views.airtel_money_callback, name="finance_airtel_collection_update"),
]
