from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Person
from .serializers import PersonSerializer


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.select_related("company").all()
    serializer_class = PersonSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "company",
        "status",
        "is_primary_contact",
    ]
    search_fields = [
        "first_name",
        "last_name",
        "middle_name",
        "email",
        "phone",
        "position",
        "department",
        "company__name",
        "company__short_name",
        "company__inn",
    ]
    ordering_fields = [
        "id",
        "last_name",
        "first_name",
        "email",
        "created_at",
        "updated_at",
        "company__name",
    ]
    ordering = ["last_name", "first_name"]

