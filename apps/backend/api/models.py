from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    modified_at = models.DateTimeField(_("modified at"), auto_now=True)

    class Role(models.TextChoices):
        SALES = "sales", "Sales"
        PURCHASER = "purchaser", "Purchaser"
        ADMIN = "admin", "Admin"
        USER = "user", "User"

    role = models.CharField(_("role"), max_length=255, choices=Role.choices, default=Role.USER)
    old_db_name = models.CharField(_("old db name"), max_length=512, null=True, blank=True)

    class Meta:
        db_table = "users"
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.email if self.email else self.username
