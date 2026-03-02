from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """User must have is_admin=True."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsVerified(BasePermission):
    """User must have is_verified=True."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_verified)


class IsOwnerOrAdmin(BasePermission):
    """Object-level: user owns the resource or is admin."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        return getattr(obj, "user_id", None) == request.user.id
