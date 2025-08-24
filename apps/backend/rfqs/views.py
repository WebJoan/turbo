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
    RFQSerializer,
    RFQItemSerializer,
    RFQCreateSerializer,
)


class RFQFilter(FilterSet):
    partnumber = CharFilter(method="filter_partnumber")
    brand = CharFilter(method="filter_brand")

    class Meta:
        model = RFQ
        fields = []

    def filter_partnumber(self, queryset, name, value):
        return queryset.filter(items__part_number__icontains=value).distinct()

    def filter_brand(self, queryset, name, value):
        return queryset.filter(items__manufacturer__icontains=value).distinct()


class RFQViewSet(viewsets.ModelViewSet):
    queryset = RFQ.objects.select_related("company", "sales_manager", "contact_person").prefetch_related("items")
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = RFQFilter
    search_fields = ["number", "title", "description", "company__name", "items__part_number", "items__manufacturer"]
    ordering_fields = ["created_at", "updated_at", "number"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve", "update", "partial_update"]:
            return RFQSerializer
        if self.action == "create":
            return RFQCreateSerializer
        return RFQSerializer

    @extend_schema(
        request=RFQCreateSerializer,
        responses={201: RFQSerializer}
    )
    def create(self, request, *args, **kwargs):
        """Создание RFQ с поддержкой как упрощенного, так и полного формата.

        Вариант А (упрощенный): partnumber, brand, qty, target_price (опц.), company_id (опц.), title/description (опц.)
        — создаёт черновик RFQ и одну строку RFQItem.

        Вариант Б (полный): items = [...], а также поля шапки RFQ
        — создаёт RFQ и строки согласно переданному массиву.
        """
        ser = RFQCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Определяем компанию: если не пришла, попробуем первую
        company = None
        company_id = data.get("company_id")
        if company_id:
            try:
                from customers.models import Company
                company = Company.objects.get(id=company_id)
            except Exception:
                pass
        if not company:
            from customers.models import Company
            company = Company.objects.order_by("id").first()
            if not company:
                return Response({"error": "Нет компаний для привязки RFQ. Создайте компанию и повторите."}, status=status.HTTP_400_BAD_REQUEST)

        # Поля шапки RFQ
        rfq_kwargs = {
            "company": company,
            "sales_manager": request.user if getattr(request.user, "is_authenticated", False) else None,
        }

        # Заголовок и описание
        title = data.get("title")
        description = data.get("description")

        # Контактное лицо, приоритет и прочие расширенные поля
        contact_person_id = data.get("contact_person_id")
        if contact_person_id:
            try:
                from persons.models import Person
                rfq_kwargs["contact_person"] = Person.objects.get(id=contact_person_id)
            except Exception:
                pass

        for optional_field in [
            "priority",
            "deadline",
            "delivery_address",
            "payment_terms",
            "delivery_terms",
            "notes",
        ]:
            if optional_field in data:
                rfq_kwargs[optional_field] = data.get(optional_field)

        # Если это упрощённый вариант и title не задан — соберём его из partnumber/brand
        if not title and all(k in data for k in ["partnumber", "brand"]):
            title = f"Запрос: {data['partnumber']} / {data['brand']}"

        rfq_kwargs["title"] = str(title or "RFQ").strip()[:200]
        if description is not None:
            rfq_kwargs["description"] = str(description)[:2000]

        # Создаём RFQ
        rfq = RFQ.objects.create(**rfq_kwargs)

        # Создание строк
        items = data.get("items") or []
        if items:
            from goods.models import Product
            next_line = 1
            used_line_numbers = set()
            for item in items:
                # line_number: если не задан — автоинкремент
                line_number = item.get("line_number") or next_line
                try:
                    line_number = int(line_number)
                except Exception:
                    line_number = next_line
                # Обеспечим уникальность line_number в рамках RFQ
                while line_number in used_line_numbers or line_number < 1:
                    line_number += 1

                product_obj = None
                product_id = item.get("product")
                if product_id:
                    try:
                        product_obj = Product.objects.get(id=product_id)
                    except Product.DoesNotExist:
                        product_obj = None

                is_new_product = item.get("is_new_product")
                if is_new_product is None:
                    is_new_product = product_obj is None

                RFQItem.objects.create(
                    rfq=rfq,
                    line_number=line_number,
                    product=product_obj,
                    product_name=str(item.get("product_name") or ""),
                    manufacturer=str(item.get("manufacturer") or ""),
                    part_number=str(item.get("part_number") or ""),
                    quantity=int(item.get("quantity")),
                    unit=str(item.get("unit") or "шт"),
                    specifications=str(item.get("specifications") or ""),
                    comments=str(item.get("comments") or ""),
                    is_new_product=bool(is_new_product),
                )
                used_line_numbers.add(line_number)
                next_line = max(next_line + 1, line_number + 1)
        else:
            # Упрощённый сценарий (одна строка)
            RFQItem.objects.create(
                rfq=rfq,
                line_number=1,
                product=None,
                product_name="",
                manufacturer=data["brand"],
                part_number=data["partnumber"],
                quantity=int(data["qty"]),
                unit="шт",
                specifications="",
                comments=(f"target_price={data['target_price']}" if data.get("target_price") is not None else ""),
                is_new_product=True,
            )

        out = RFQSerializer(rfq)
        headers = self.get_success_headers(out.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)
