from os import environ
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Ensure a service user exists and has the desired credentials/flags"

    def handle(self, *args, **options):
        username = (
            environ.get("SERVICE_USER_USERNAME")
            or environ.get("BACKEND_API_USERNAME")
        )
        password = (
            environ.get("SERVICE_USER_PASSWORD")
            or environ.get("BACKEND_API_PASSWORD")
        )
        is_staff = (environ.get("SERVICE_USER_IS_STAFF", "0") == "1")
        is_superuser = (environ.get("SERVICE_USER_IS_SUPERUSER", "0") == "1")

        if not username:
            self.stdout.write("ensure_service_user: no SERVICE_USER_USERNAME provided; skipping")
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "is_active": True,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
            },
        )

        if created:
            if password:
                user.set_password(password)
                user.save(update_fields=["password"])
            self.stdout.write(f"ensure_service_user: created user '{username}'")
        else:
            updated = False
            if user.is_staff != is_staff or user.is_superuser != is_superuser or not user.is_active:
                user.is_staff = is_staff
                user.is_superuser = is_superuser
                user.is_active = True
                updated = True
            if password:
                user.set_password(password)
                updated = True
            if updated:
                user.save()
                self.stdout.write(f"ensure_service_user: updated user '{username}'")
            else:
                self.stdout.write(f"ensure_service_user: user '{username}' already up-to-date")


