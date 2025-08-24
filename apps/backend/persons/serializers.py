from rest_framework import serializers

from customers.models import Company
from .models import Person


class PersonSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Person
        fields = [
            "id",
            "ext_id",
            "company",
            "company_name",
            "first_name",
            "last_name",
            "middle_name",
            "email",
            "phone",
            "position",
            "department",
            "status",
            "is_primary_contact",
            "notes",
            "created_at",
            "updated_at",
            "full_name",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "full_name",
        ]


