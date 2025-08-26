from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from django.db.models import Q, Count

from goods.models import Product, ProductGroup, ProductSubgroup, Brand
from goods.indexers import ProductIndexer
from django.conf import settings
from customers.models import Company
from rfqs.models import RFQ, RFQItem, Quotation, QuotationItem, RFQItemFile
from goods.tasks import export_products_by_typecode, export_products_by_filters
from celery.result import AsyncResult
import base64
import logging
from django.http import HttpResponse

logger = logging.getLogger(__name__)
from .serializers import (
    RFQSerializer,
    RFQItemSerializer,
    RFQItemWriteSerializer,
    RFQCreateSerializer,
    QuotationSerializer,
    QuotationItemSerializer,
    RFQItemFileSerializer,
)


class RFQFilter(FilterSet):
    partnumber = CharFilter(method="filter_partnumber")
    brand = CharFilter(method="filter_brand")
    number = CharFilter(field_name="number", lookup_expr="icontains")
    company_name = CharFilter(field_name="company__name", lookup_expr="icontains")

    class Meta:
        model = RFQ
        fields = []

    def filter_partnumber(self, queryset, name, value):
        return queryset.filter(items__part_number__icontains=value).distinct()

    def filter_brand(self, queryset, name, value):
        return queryset.filter(items__manufacturer__icontains=value).distinct()


class RFQViewSet(viewsets.ModelViewSet):
    queryset = (
        RFQ.objects.select_related("company", "sales_manager", "contact_person")
        .prefetch_related("items__product", "items")
        .annotate(quotations_count=Count("quotations", distinct=True))
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = RFQFilter
    search_fields = ["number", "description", "company__name", "items__part_number", "items__manufacturer"]
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

        # Описание
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


class RFQItemViewSet(viewsets.ModelViewSet):
    queryset = (
        RFQItem.objects.select_related("rfq", "product")
        .prefetch_related("files")
        .all()
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["rfq"]
    search_fields = ["product_name", "manufacturer", "part_number", "comments"]
    ordering_fields = ["rfq", "line_number", "created_at", "updated_at"]
    ordering = ["rfq", "line_number"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return RFQItemWriteSerializer
        return RFQItemSerializer


class RFQItemFileViewSet(mixins.DestroyModelMixin,
                         mixins.RetrieveModelMixin,
                         mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    queryset = RFQItemFile.objects.select_related("rfq_item", "rfq_item__rfq").all()
    serializer_class = RFQItemFileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["rfq_item"]
    search_fields = ["description", "file"]
    ordering_fields = ["uploaded_at"]
    ordering = ["-uploaded_at"]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rfq_item_quotations(request, rfq_item_id):
    """Получить предложения (цены и сроки) для конкретной позиции RFQ"""
    logger.info(f"Запрос предложений для RFQItem ID: {rfq_item_id}")
    
    try:
        rfq_item = RFQItem.objects.get(id=rfq_item_id)
        logger.info(f"RFQItem найден: {rfq_item}")
    except RFQItem.DoesNotExist:
        logger.warning(f"RFQItem с ID {rfq_item_id} не найден")
        return Response(
            {"error": f"RFQ Item с ID {rfq_item_id} не найден"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Получаем все QuotationItem, которые связаны с этой RFQItem
    quotation_items = QuotationItem.objects.filter(
        rfq_item=rfq_item
    ).select_related(
        'quotation', 
        'quotation__product_manager', 
        'quotation__currency'
    ).order_by('-quotation__created_at')
    
    # Группируем по quotation для удобства
    quotations_data = []
    for quotation_item in quotation_items:
        quotation = quotation_item.quotation
        
        quotation_data = {
            "quotation": QuotationSerializer(quotation).data,
            "quotation_item": QuotationItemSerializer(quotation_item).data
        }
        quotations_data.append(quotation_data)
    
    logger.info(f"Найдено {len(quotations_data)} предложений для RFQItem {rfq_item_id}")
    
    return Response({
        "rfq_item_id": rfq_item_id,
        "quotations": quotations_data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def debug_rfq_items(request):
    """Debug endpoint для получения всех RFQItem IDs"""
    rfq_items = RFQItem.objects.all().values('id', 'rfq__number', 'line_number', 'product_name')
    return Response({
        "count": len(rfq_items),
        "rfq_items": list(rfq_items)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_rfq_item_files(request, rfq_item_id):
    """Загрузка одного или нескольких файлов к конкретной строке RFQ.

    Ожидает multipart/form-data с ключами:
    - files: один или несколько файлов (используйте одинаковое имя поля несколько раз)
    - file_type (опц.): общий тип для всех файлов (photo|datasheet|specification|drawing|other)
    - description (опц.): общее описание (при необходимости можно вызывать несколько раз с разными описаниями)
    """
    from rfqs.models import RFQItemFile, RFQItemFile as _RFQItemFile, RFQItem
    from rfqs.models import validate_rfq_item_file_size

    try:
        rfq_item = RFQItem.objects.get(id=rfq_item_id)
    except RFQItem.DoesNotExist:
        return Response({"error": f"RFQ Item с ID {rfq_item_id} не найден"}, status=status.HTTP_404_NOT_FOUND)

    # Проверим, что это multipart
    if not request.FILES:
        return Response({"error": "Файлы не переданы (ожидается multipart/form-data c полем files)"}, status=status.HTTP_400_BAD_REQUEST)

    files = request.FILES.getlist('files') or []
    if not files:
        # Некоторые клиенты отправляют files[]; покроем оба варианта
        files = request.FILES.getlist('files[]')

    if not files:
        return Response({"error": "Добавьте хотя бы один файл в поле 'files'"}, status=status.HTTP_400_BAD_REQUEST)

    raw_file_type = request.data.get('file_type') or _RFQItemFile.FileTypeChoices.OTHER
    if raw_file_type not in dict(_RFQItemFile.FileTypeChoices.choices):
        raw_file_type = _RFQItemFile.FileTypeChoices.OTHER
    description = request.data.get('description', '')

    created = []
    for f in files:
        # Ранняя проверка размера для дружелюбной ошибки
        try:
            validate_rfq_item_file_size(f)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        created.append(
            RFQItemFile.objects.create(
                rfq_item=rfq_item,
                file=f,
                file_type=raw_file_type,
                description=str(description)[:200]
            )
        )

    return Response(RFQItemFileSerializer(created, many=True).data, status=status.HTTP_201_CREATED)
