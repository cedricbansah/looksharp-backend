from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, id, email, **extra_fields):
        user = self.model(id=id, email=email, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    # Firebase UID is the primary key — no auto-generated integer PK
    id = models.CharField(max_length=128, primary_key=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=100, default="Ghana")
    profile_photo_url = models.URLField(blank=True, max_length=500)

    # Server-controlled — never written directly by clients
    points = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    recipient_code = models.CharField(max_length=100, blank=True)
    is_admin = models.BooleanField(default=False)
    welcome_bonus_claimed = models.BooleanField(default=False)

    # JSON arrays — mirrors Firestore contract
    surveys_completed = models.JSONField(default=list)
    offers_claimed = models.JSONField(default=list)

    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Required by AbstractBaseUser
    last_login = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.email
