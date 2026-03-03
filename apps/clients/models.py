from django.db import models


class Client(models.Model):
    id = models.CharField(max_length=128, primary_key=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=500, blank=True)
    website_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    client_code = models.CharField(max_length=64, blank=True, null=True, unique=True, db_index=True)
    logo_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clients"
        ordering = ["name"]

    def __str__(self):
        return self.name
