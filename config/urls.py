from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/surveys/", include("apps.surveys.urls")),
    path("api/v1/responses/", include("apps.responses.urls")),
    path("api/v1/offers/", include("apps.offers.urls")),
    path("api/v1/redemptions/", include("apps.offers.redemption_urls")),
    path("api/v1/verifications/", include("apps.verifications.urls")),
    path("api/v1/withdrawals/", include("apps.withdrawals.urls")),
    path("api/v1/paystack/", include("apps.paystack.urls")),
    path("api/v1/webhooks/", include("apps.webhooks.urls")),
    path("api/v1/admin/", include("apps.counters.urls")),
    path("api/v1/admin/", include("apps.users.admin_urls")),
    path("api/v1/admin/", include("apps.responses.admin_urls")),
    path("api/v1/admin/", include("apps.withdrawals.admin_urls")),
    path("api/v1/admin/", include("apps.verifications.admin_urls")),
    path("api/v1/admin/", include("apps.surveys.admin_urls")),
    path("api/v1/admin/", include("apps.offers.admin_urls")),
    path("api/v1/admin/", include("apps.clients.admin_urls")),
]
