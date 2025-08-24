from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from django.db.models import Q

from goods.models import Product, ProductGroup, ProductSubgroup, Brand
from goods.indexers import ProductIndexer
from django.conf import settings
from customers.models import Company
from rfqs.models import RFQ, RFQItem
from goods.tasks import export_products_by_typecode, export_products_by_filters
from celery.result import AsyncResult
import base64
import logging
from django.http import HttpResponse

logger = logging.getLogger(__name__)
from .serializers import (
    CompanySerializer,
)


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "short_name", "inn", "ext_id"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]
