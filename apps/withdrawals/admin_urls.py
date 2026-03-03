from django.urls import path

from .views import AdminWithdrawalListView

urlpatterns = [
    path("withdrawals/", AdminWithdrawalListView.as_view(), name="admin-withdrawals"),
]
