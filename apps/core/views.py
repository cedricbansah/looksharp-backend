from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """
    Health check endpoint for load balancers and orchestrators.
    Returns 200 if the app can connect to the database.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "healthy", "database": "connected"})
    except Exception as e:
        return JsonResponse(
            {"status": "unhealthy", "database": "disconnected", "error": str(e)},
            status=503,
        )
