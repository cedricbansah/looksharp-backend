from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from .serializers import UserSerializer, UserUpdateSerializer


class MeView(RetrieveUpdateAPIView):
    """
    GET  /api/v1/users/me/  — return authenticated user's profile
    PATCH /api/v1/users/me/ — update client-writable fields only
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserUpdateSerializer
        return UserSerializer
