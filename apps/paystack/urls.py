from django.urls import path

from .views import BanksView, FinalizeTransferView, TransferRecipientsView, TransfersView

urlpatterns = [
    path("banks/", BanksView.as_view(), name="paystack-banks"),
    path(
        "transfer-recipients/",
        TransferRecipientsView.as_view(),
        name="paystack-recipients",
    ),
    path("transfers/", TransfersView.as_view(), name="paystack-transfers"),
    path(
        "transfers/<str:transfer_code>/finalize/",
        FinalizeTransferView.as_view(),
        name="paystack-finalize",
    ),
]
