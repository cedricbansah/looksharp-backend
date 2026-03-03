from django.urls import path

from .views import AdminUserListView, GrantAdminView

urlpatterns = [
    path("users/", AdminUserListView.as_view(), name="admin-users"),
    path("users/<str:user_id>/grant-admin/", GrantAdminView.as_view(), name="admin-users-grant-admin"),
]
