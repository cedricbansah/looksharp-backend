from django.urls import path

from .views import AdminWithdrawalListView, AdminWithdrawalUpdateView

urlpatterns = [
    path("withdrawals/", AdminWithdrawalListView.as_view(), name="admin-withdrawals"),
    path(
        "withdrawals/<uuid:withdrawal_id>/",
        AdminWithdrawalUpdateView.as_view(),
        name="admin-withdrawals-detail",
    ),
]
