from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from django.db.models import Q, Count

from goods.models import Product, ProductGroup, ProductSubgroup, Brand
from goods.indexers import ProductIndexer
from django.conf import settings
from customers.models import Company
from rfqs.models import RFQ, RFQItem, Quotation, QuotationItem, RFQItemFile, Currency, QuotationItemFile
from goods.tasks import export_products_by_typecode, export_products_by_filters
from celery.result import AsyncResult
import base64
import logging
from django.http import HttpResponse
from decimal import Decimal

logger = logging.getLogger(__name__)
from .serializers import (
    RFQSerializer,
    RFQItemSerializer,
    RFQItemWriteSerializer,
    RFQCreateSerializer,
    QuotationSerializer,
    QuotationItemSerializer,
    RFQItemFileSerializer,
    QuotationItemFileSerializer,
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
        .prefetch_related(
            "items__product",
            "items",
            # для has_quotations в сериализаторе RFQItemSerializer
            "items__quotation_items",
        )
        .annotate(quotations_count=Count("quotations", distinct=True))
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = RFQFilter
    search_fields = ["number", "description", "company__name", "items__part_number", "items__manufacturer"]
    ordering_fields = ["created_at", "updated_at", "number"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Restrict RFQs for sales managers to only their own; admins see all."""
        base_qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return base_qs.none()

        # Admins or staff/superusers see everything
        user_role = getattr(user, "role", None)
        if user_role == "admin" or getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return base_qs

        # Sales managers only see their own RFQs
        if user_role == "sales":
            return base_qs.filter(sales_manager=user)

        # Purchasers see RFQs that contain at least one item whose product is under their responsibility
        if user_role == "purchaser":
            return (
                base_qs.filter(
                    Q(items__is_new_product=True)
                    | Q(items__product__product_manager=user)
                    | Q(items__product__brand__product_manager=user)
                    | Q(items__product__subgroup__product_manager=user)
                )
                .exclude(status=RFQ.StatusChoices.DRAFT)
                .distinct()
            )

        # Other roles (e.g., purchaser) currently see all
        return base_qs

    def get_serializer_class(self):
        if self.action in ["list", "retrieve", "update", "partial_update"]:
            return RFQSerializer
        if self.action == "create":
            return RFQCreateSerializer
        return RFQSerializer

    # --- Permissions for edit/delete: only owner (sales_manager) or admins ---
    def _is_admin(self, user):
        return getattr(user, "role", None) == "admin" or getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)

    def _ensure_can_modify_rfq(self, request, rfq: RFQ):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            raise PermissionDenied("Требуется аутентификация")
        if self._is_admin(user):
            return
        if rfq.sales_manager_id and rfq.sales_manager_id == getattr(user, "id", None):
            return
        # Anyone else (including purchasers and other sales) cannot modify foreign RFQs
        raise PermissionDenied("Вы не можете изменять или удалять чужой RFQ")

    def update(self, request, *args, **kwargs):
        rfq = self.get_object()
        user = getattr(request, "user", None)
        # Allow purchasers to set status to in_progress for visible RFQs (submitted -> in_progress) only
        if getattr(user, "role", None) == "purchaser":
            incoming_status = request.data.get("status") if isinstance(request.data, dict) else None
            # Only allow changing only the status field to 'in_progress' and only from 'submitted'
            allowed_keys = {"status"}
            provided_keys = set(request.data.keys()) if isinstance(request.data, dict) else set()
            if provided_keys.issubset(allowed_keys) and incoming_status == RFQ.StatusChoices.IN_PROGRESS and rfq.status == RFQ.StatusChoices.SUBMITTED:
                return super().update(request, *args, **kwargs)
            raise PermissionDenied("Только product/purchaser может взять в работу (submitted → in_progress) и больше никаких изменений")
        # Default rule: only owner (sales manager) or admin/staff
        self._ensure_can_modify_rfq(request, rfq)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        rfq = self.get_object()
        user = getattr(request, "user", None)
        # Allow purchasers to set status to in_progress for visible RFQs (submitted -> in_progress) only
        if getattr(user, "role", None) == "purchaser":
            incoming_status = request.data.get("status") if isinstance(request.data, dict) else None
            allowed_keys = {"status"}
            provided_keys = set(request.data.keys()) if isinstance(request.data, dict) else set()
            if provided_keys.issubset(allowed_keys) and incoming_status == RFQ.StatusChoices.IN_PROGRESS and rfq.status == RFQ.StatusChoices.SUBMITTED:
                return super().partial_update(request, *args, **kwargs)
            raise PermissionDenied("Только product/purchaser может взять в работу (submitted → in_progress) и больше никаких изменений")
        # Default rule: only owner (sales manager) or admin/staff
        self._ensure_can_modify_rfq(request, rfq)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        rfq = self.get_object()
        self._ensure_can_modify_rfq(request, rfq)
        return super().destroy(request, *args, **kwargs)

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

    # --- Mirror RFQ modification permissions for RFQ items ---
    def _is_admin(self, user):
        return getattr(user, "role", None) == "admin" or getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)

    def _ensure_can_modify_rfq_item(self, request, rfq_obj: RFQ):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            raise PermissionDenied("Требуется аутентификация")
        if self._is_admin(user):
            return
        if rfq_obj.sales_manager_id and rfq_obj.sales_manager_id == getattr(user, "id", None):
            return
        raise PermissionDenied("Вы не можете изменять чужой RFQ")

    def create(self, request, *args, **kwargs):
        # Ensure user owns the RFQ they are adding an item to
        try:
            rfq_id = request.data.get("rfq")
        except Exception:
            rfq_id = None
        if rfq_id:
            try:
                parent_rfq = RFQ.objects.get(id=rfq_id)
            except RFQ.DoesNotExist:
                parent_rfq = None
            if parent_rfq is None:
                raise PermissionDenied("Указанный RFQ не найден")
            self._ensure_can_modify_rfq_item(request, parent_rfq)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        self._ensure_can_modify_rfq_item(request, obj.rfq)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        self._ensure_can_modify_rfq_item(request, obj.rfq)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        self._ensure_can_modify_rfq_item(request, obj.rfq)
        return super().destroy(request, *args, **kwargs)


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


class QuotationItemFileViewSet(mixins.DestroyModelMixin,
                               mixins.RetrieveModelMixin,
                               mixins.ListModelMixin,
                               viewsets.GenericViewSet):
    queryset = QuotationItemFile.objects.select_related("quotation_item", "quotation_item__quotation").all()
    serializer_class = QuotationItemFileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["quotation_item"]
    search_fields = ["description", "file"]
    ordering_fields = ["uploaded_at"]
    ordering = ["-uploaded_at"]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_quotation_item_files(request, quotation_item_id):
    """Загрузка одного или нескольких файлов к строке предложения QuotationItem.

    Ожидает multipart/form-data с ключами:
    - files: один или несколько файлов
    - file_type (опц.)
    - description (опц.)
    """
    from rfqs.models import validate_quotation_item_file_size

    try:
        quotation_item = QuotationItem.objects.get(id=quotation_item_id)
    except QuotationItem.DoesNotExist:
        return Response({"error": f"Quotation Item с ID {quotation_item_id} не найден"}, status=status.HTTP_404_NOT_FOUND)

    if not request.FILES:
        return Response({"error": "Файлы не переданы (ожидается multipart/form-data c полем files)"}, status=status.HTTP_400_BAD_REQUEST)

    files = request.FILES.getlist('files') or request.FILES.getlist('files[]')
    if not files:
        return Response({"error": "Добавьте хотя бы один файл в поле 'files'"}, status=status.HTTP_400_BAD_REQUEST)

    raw_file_type = request.data.get('file_type') or QuotationItemFile.FileTypeChoices.OTHER
    if raw_file_type not in dict(QuotationItemFile.FileTypeChoices.choices):
        raw_file_type = QuotationItemFile.FileTypeChoices.OTHER
    description = request.data.get('description', '')

    created = []
    for f in files:
        try:
            validate_quotation_item_file_size(f)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        created.append(
            QuotationItemFile.objects.create(
                quotation_item=quotation_item,
                file=f,
                file_type=raw_file_type,
                description=str(description)[:200]
            )
        )

    return Response(QuotationItemFileSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rfq_item_last_prices(request, rfq_item_id):
    """Возвращает последние цены продажи для данной позиции RFQ:

    - last_price_for_company: последняя цена по этому товару для компании RFQ
    - last_price_any: последняя цена по этому товару среди всех компаний

    Если товар в строке RFQ не привязан к Product, возвращаются null.
    """
    try:
        rfq_item = RFQItem.objects.select_related('rfq', 'product').get(id=rfq_item_id)
    except RFQItem.DoesNotExist:
        return Response({"error": f"RFQ Item с ID {rfq_item_id} не найден"}, status=status.HTTP_404_NOT_FOUND)

    product_id = getattr(rfq_item, 'product_id', None)
    if not product_id:
        return Response({
            "rfq_item_id": rfq_item_id,
            "last_price_for_company": None,
            "last_price_any": None,
        })

    from sales.models import Invoice, InvoiceLine

    base_qs = (
        InvoiceLine.objects.select_related('invoice')
        .filter(product_id=product_id, invoice__invoice_type=Invoice.InvoiceType.SALE)
        .order_by('-invoice__invoice_date', '-id')
    )

    try:
        company_last = base_qs.filter(invoice__company_id=rfq_item.rfq.company_id).first()
    except Exception:
        company_last = None

    try:
        any_last = base_qs.first()
    except Exception:
        any_last = None

    def serialize_line(line):
        if not line:
            return None
        inv = line.invoice
        return {
            "price": str(line.price),
            "currency": getattr(inv, 'currency', ''),
            "invoice_date": getattr(inv, 'invoice_date', None),
            "invoice_number": getattr(inv, 'invoice_number', ''),
        }

    return Response({
        "rfq_item_id": rfq_item_id,
        "last_price_for_company": serialize_line(company_last),
        "last_price_any": serialize_line(any_last),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_quotation_for_rfq_item(request, rfq_item_id):
    """Создать предложение (Quotation) и одну строку предложения (QuotationItem) для указанной позиции RFQ.

    Доступно для ролей: admin, purchaser. Sales — запрещено.

    Входные поля (JSON):
    - title (опц.)
    - quantity (опц., по умолчанию = quantity из RFQItem)
    - unit_cost_price (обяз.)
    - cost_expense_percent (опц., по умолчанию 10.00)
    - cost_markup_percent (опц., по умолчанию 20.00)
    - delivery_time (опц.)
    - payment_terms (опц.)
    - delivery_terms (опц.)
    - notes (опц.)
    - currency_id (опц.)
    - product (опц., ID товара из базы)
    - proposed_product_name / proposed_manufacturer / proposed_part_number (опц., если выбирается новый товар)
    """
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return Response({"error": "Требуется аутентификация"}, status=status.HTTP_401_UNAUTHORIZED)

    user_role = getattr(user, 'role', None)
    if user_role == 'sales':
        return Response({"error": "Sales менеджерам запрещено создавать предложения"}, status=status.HTTP_403_FORBIDDEN)

    try:
        rfq_item = RFQItem.objects.select_related('rfq', 'product').get(id=rfq_item_id)
    except RFQItem.DoesNotExist:
        return Response({"error": f"RFQ Item с ID {rfq_item_id} не найден"}, status=status.HTTP_404_NOT_FOUND)

    data = request.data if isinstance(request.data, dict) else {}

    # Определяем валюту
    currency_obj = None
    currency_id = data.get('currency_id')
    if currency_id:
        try:
            currency_obj = Currency.objects.get(id=currency_id)
        except Currency.DoesNotExist:
            currency_obj = None
    if currency_obj is None:
        currency_obj = Currency.objects.filter(is_active=True).order_by('code').first()
    if currency_obj is None:
        currency_obj = Currency.objects.create(code='RUB', name='Рубли', symbol='₽', exchange_rate_to_rub=Decimal('1'))

    title = str(data.get('title') or '').strip() or f"Предложение по {rfq_item.rfq.number} / строка {rfq_item.line_number}"
    delivery_time = str(data.get('delivery_time') or '').strip()
    payment_terms = str(data.get('payment_terms') or '').strip()
    delivery_terms = str(data.get('delivery_terms') or '').strip()
    notes = str(data.get('notes') or '').strip()

    # Количество и цены
    try:
        unit_cost_price = Decimal(str(data.get('unit_cost_price')))
    except Exception:
        return Response({"error": "Поле unit_cost_price обязательно и должно быть числом"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        quantity = int(data.get('quantity') or rfq_item.quantity)
    except Exception:
        quantity = rfq_item.quantity

    def to_decimal(value, default: str):
        try:
            if value is None or value == '':
                return Decimal(default)
            return Decimal(str(value))
        except Exception:
            return Decimal(default)

    cost_expense_percent = to_decimal(data.get('cost_expense_percent'), '10.00')
    cost_markup_percent = to_decimal(data.get('cost_markup_percent'), '20.00')

    # Определяем товар для строки предложения: из тела запроса или из RFQItem
    product_obj = None
    product_id = data.get('product')
    if product_id:
        try:
            product_obj = Product.objects.get(id=product_id)
        except Exception:
            product_obj = None
    if product_obj is None and rfq_item.product_id:
        product_obj = rfq_item.product

    # Создаём Quotation
    quotation = Quotation.objects.create(
        rfq=rfq_item.rfq,
        product_manager=user,
        title=title,
        currency=currency_obj,
        description='',
        delivery_time=delivery_time,
        payment_terms=payment_terms,
        delivery_terms=delivery_terms,
        notes=notes,
    )

    # Подготовим данные строки предложения
    qi_kwargs = {
        'quotation': quotation,
        'rfq_item': rfq_item,
        'product': product_obj,
        'quantity': quantity,
        'unit_cost_price': unit_cost_price,
        'cost_expense_percent': cost_expense_percent,
        'cost_markup_percent': cost_markup_percent,
        'delivery_time': delivery_time,
        'notes': notes,
    }

    # Если выбран новый товар — сохраним предложенные поля
    if product_obj is None:
        qi_kwargs.update({
            'proposed_product_name': str(data.get('proposed_product_name') or rfq_item.product_name or ''),
            'proposed_manufacturer': str(data.get('proposed_manufacturer') or rfq_item.manufacturer or ''),
            'proposed_part_number': str(data.get('proposed_part_number') or rfq_item.part_number or ''),
        })

    quotation_item = QuotationItem.objects.create(**qi_kwargs)

    out = QuotationSerializer(quotation)
    return Response(out.data, status=status.HTTP_201_CREATED)
