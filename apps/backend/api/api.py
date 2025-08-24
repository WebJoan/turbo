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
    # existing
    UserChangePasswordErrorSerializer,
    UserChangePasswordSerializer,
    UserCreateErrorSerializer,
    UserCreateSerializer,
    UserCurrentErrorSerializer,
    UserCurrentSerializer,
    UserInfoSerializer,
    ProductSerializer,
    ProductListSerializer,
    ProductGroupSerializer,
    ProductSubgroupSerializer,
    BrandSerializer,
    CompanySerializer,
    # new
    RFQSerializer,
    RFQItemSerializer,
    RFQCreateSerializer,
)

User = get_user_model()


class UserViewSet(
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.all()
    serializer_class = UserCurrentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(pk=self.request.user.pk)

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]

        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        elif self.action == "me":
            return UserCurrentSerializer
        elif self.action == "change_password":
            return UserChangePasswordSerializer

        return super().get_serializer_class()

    @extend_schema(
        responses={
            200: UserCreateSerializer,
            400: UserCreateErrorSerializer,
        }
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        responses={
            200: UserCurrentSerializer,
            400: UserCurrentErrorSerializer,
        }
    )
    @action(["get", "put", "patch"], detail=False)
    def me(self, request, *args, **kwargs):
        if request.method == "GET":
            serializer = self.get_serializer(self.request.user)
            return Response(serializer.data)
        elif request.method == "PUT":
            serializer = self.get_serializer(
                self.request.user, data=request.data, partial=False
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        elif request.method == "PATCH":
            serializer = self.get_serializer(
                self.request.user, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

    @extend_schema(
        responses={
            204: None,
            400: UserChangePasswordErrorSerializer,
        }
    )
    @action(["post"], url_path="change-password", detail=False)
    def change_password(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self.request.user.set_password(serializer.data["password_new"])
        self.request.user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        responses={
            200: UserInfoSerializer,
            404: {"description": "Пользователь не найден"},
        }
    )
    @action(["get"], detail=True, url_path="info")
    def get_user_info(self, request, pk=None, *args, **kwargs):
        """Получить информацию о пользователе по ID, включая old_db_name."""
        try:
            user = User.objects.get(pk=pk)
            serializer = UserInfoSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {"detail": f"Пользователь с ID {pk} не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(["delete"], url_path="delete-account", detail=False)
    def delete_account(self, request, *args, **kwargs):
        self.request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
def ping_post(request):
    return Response({"ok": True}, status=status.HTTP_200_OK)


# Фильтры для товаров
class ProductFilter(FilterSet):
    ext_id = CharFilter(field_name="ext_id", lookup_expr="exact")
    ext_id_contains = CharFilter(field_name="ext_id", lookup_expr="icontains")
    name = CharFilter(field_name="name", lookup_expr="icontains")
    complex_name = CharFilter(field_name="complex_name", lookup_expr="icontains")
    brand_name = CharFilter(field_name="brand__name", lookup_expr="icontains")
    group_name = CharFilter(field_name="subgroup__group__name", lookup_expr="icontains")
    subgroup_name = CharFilter(field_name="subgroup__name", lookup_expr="icontains")
    manager_id = NumberFilter(method="filter_by_manager")
    search = CharFilter(method="filter_search")
    
    class Meta:
        model = Product
        fields = ["ext_id", "name", "brand_name", "group_name", "subgroup_name"]
    
    def filter_by_manager(self, queryset, name, value):
        """Фильтрация по назначенному менеджеру (учитывает иерархию)"""
        return queryset.filter(
            Q(product_manager_id=value) |
            Q(brand__product_manager_id=value) |
            Q(subgroup__product_manager_id=value)
        )
    
    def filter_search(self, queryset, name, value):
        """Общий поиск по ключевым полям"""
        return queryset.filter(
            Q(ext_id__icontains=value) |
            Q(name__icontains=value) |
            Q(complex_name__icontains=value) |
            Q(description__icontains=value) |
            Q(brand__name__icontains=value) |
            Q(subgroup__name__icontains=value) |
            Q(subgroup__group__name__icontains=value)
        )


# ViewSets для товаров
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.select_related(
        'brand', 'subgroup__group', 'product_manager',
        'brand__product_manager', 'subgroup__product_manager'
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["ext_id", "name", "complex_name", "description", "brand__name"]
    ordering_fields = ["name", "ext_id"]
    ordering = ["name"]
    
    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductSerializer
    
    @action(detail=False, methods=["get"], url_path="ms-search")
    def ms_search(self, request):
        """Поиск товаров через MeiliSearch индекс products.

        Параметры:
        - q: строка запроса
        - page: номер страницы (1..)
        - page_size: элементов на странице
        """
        try:
            from meilisearch import Client  # type: ignore
        except Exception:
            return Response({"error": "MeiliSearch client is not installed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        query = request.query_params.get("q", "")
        try:
            page = int(request.query_params.get("page", 1))
        except Exception:
            page = 1
        try:
            page_size = int(request.query_params.get("page_size") or request.query_params.get("pageSize") or 10)
        except Exception:
            page_size = 10

        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        offset = (page - 1) * page_size

        client = Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_API_KEY)
        index = client.index(ProductIndexer.index_name())

        try:
            result = index.search(query, {"limit": page_size, "offset": offset})
        except Exception as e:
            return Response({"error": f"MeiliSearch error: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

        hits = result.get("hits", [])
        total = result.get("estimatedTotalHits") or result.get("nbHits") or len(hits)

        # Получаем ID товаров из результатов поиска
        product_ids = [h.get("id") for h in hits if h.get("id")]
        
        if not product_ids:
            return Response({
                "count": int(total),
                "results": [],
                "page": page,
                "page_size": page_size,
            })
        
        # Получаем полные объекты товаров из БД с оптимизацией запросов
        from goods.models import Product
        products_queryset = Product.objects.filter(id__in=product_ids).select_related(
            'brand', 'subgroup__group', 'subgroup__product_manager', 
            'brand__product_manager', 'product_manager'
        )
        
        # Создаем словарь для быстрого доступа по ID
        products_dict = {p.id: p for p in products_queryset}
        
        # Сохраняем порядок из MeiliSearch и сериализуем через ProductListSerializer
        ordered_products = []
        for product_id in product_ids:
            if product_id in products_dict:
                ordered_products.append(products_dict[product_id])
        
        # Сериализуем данные включая assigned_manager
        serializer = ProductListSerializer(ordered_products, many=True)
        
        return Response({
            "count": int(total),
            "results": serializer.data,
            "page": page,
            "page_size": page_size,
        })

    @action(detail=False, methods=["get"])
    def by_ext_id(self, request):
        """Поиск товара по точному ext_id"""
        ext_id = request.query_params.get("ext_id")
        if not ext_id:
            return Response({"error": "Параметр ext_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product = self.get_queryset().get(ext_id=ext_id)
            serializer = ProductSerializer(product)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({"error": f"Товар с ext_id '{ext_id}' не найден"}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=["get"])
    def by_manager(self, request):
        """Получить товары по менеджеру"""
        manager_id = request.query_params.get("manager_id")
        if not manager_id:
            return Response({"error": "Параметр manager_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.filter_queryset(
            self.get_queryset().filter(
                Q(product_manager_id=manager_id) |
                Q(brand__product_manager_id=manager_id) |
                Q(subgroup__product_manager_id=manager_id)
            )
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(queryset, many=True)
        return Response(serializer.data)


class ProductGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductGroup.objects.all()
    serializer_class = ProductGroupSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "ext_id"]
    ordering = ["name"]


class ProductSubgroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductSubgroup.objects.select_related('group', 'product_manager').all()
    serializer_class = ProductSubgroupSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "ext_id", "group__name"]
    ordering = ["group__name", "name"]
    filterset_fields = ["group"]
    
    @action(detail=False, methods=["get"])
    def autocomplete(self, request):
        """Автокомплит для подгрупп товаров по названию"""
        query = request.query_params.get("q", "").strip()
        limit = min(int(request.query_params.get("limit", 20)), 50)
        
        if not query:
            queryset = self.get_queryset()[:limit]
        else:
            queryset = self.get_queryset().filter(name__icontains=query)[:limit]
        
        data = []
        for subgroup in queryset:
            data.append({
                "id": subgroup.id,
                "ext_id": subgroup.ext_id,
                "name": subgroup.name,
                "group_name": subgroup.group.name if subgroup.group else None,
                "display_name": f"{subgroup.name} ({subgroup.group.name})" if subgroup.group else subgroup.name
            })
        
        return Response(data)


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "short_name", "inn", "ext_id"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.select_related('product_manager').all()
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "ext_id"]
    ordering = ["name"]
    
    @action(detail=False, methods=["get"])
    def autocomplete(self, request):
        """Автокомплит для брендов по названию"""
        query = request.query_params.get("q", "").strip()
        limit = min(int(request.query_params.get("limit", 20)), 50)
        
        if not query:
            queryset = self.get_queryset()[:limit]
        else:
            queryset = self.get_queryset().filter(name__icontains=query)[:limit]
        
        data = []
        for brand in queryset:
            data.append({
                "id": brand.id,
                "ext_id": brand.ext_id,
                "name": brand.name,
                "product_manager": brand.product_manager.full_name if brand.product_manager else None
            })
        
        return Response(data)
    
    @action(detail=False, methods=["get"])
    def get_all_names(self, request):
        """Получить список всех названий брендов для фильтрации"""
        queryset = self.get_queryset()
        brands = queryset.values_list('name', flat=True).distinct().order_by('name')
        return Response(list(brands))


# --- RFQ API ---

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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def export_products_descriptions(request):
    """
    Запуск экспорта описаний товаров с фильтрацией по подгруппам и брендам.
    
    POST /api/products/export-descriptions/
    {
        "typecode": "123",          // ext_id одной подгруппы (для обратной совместимости)
        "subgroup_ids": ["123", "456"], // список ext_id подгрупп (опционально)
        "brand_names": ["ST", "RUICHI"], // список названий брендов (опционально)
        "only_two_params": true,    // если true, экспортируются только товары с двумя техническими параметрами
        "no_description": true,     // если true, экспортируются только товары без описания
        "async": true              // опционально - если true, возвращает task_id для отслеживания
    }
    
    Можно использовать либо typecode (старый способ), либо новые параметры subgroup_ids и brand_names.
    Если не указать никаких фильтров, будут экспортированы все товары.
    """
    # Получаем параметры запроса
    typecode = request.data.get("typecode")
    subgroup_ids = request.data.get("subgroup_ids", [])
    brand_names = request.data.get("brand_names", [])
    only_two_params = request.data.get("only_two_params", False)
    no_description = request.data.get("no_description", False)
    is_async = request.data.get("async", False)
    
    # Обратная совместимость: если передан typecode, добавляем его в список подгрупп
    if typecode:
        if not subgroup_ids:
            subgroup_ids = [typecode]
        elif typecode not in subgroup_ids:
            subgroup_ids.append(typecode)
    
    # Если не указаны фильтры, экспортируются все товары
    if not subgroup_ids and not brand_names:
        logger.info("Экспорт всех товаров без фильтрации")
    
    # Проверяем существование подгрупп если они указаны
    if subgroup_ids:
        existing_subgroups = ProductSubgroup.objects.filter(ext_id__in=subgroup_ids).values_list('ext_id', flat=True)
        missing_subgroups = [sg_id for sg_id in subgroup_ids if sg_id not in existing_subgroups]
        if missing_subgroups:
            return Response(
                {"error": f"Подгруппы с ext_id не найдены: {missing_subgroups}"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    # Проверяем существование брендов если они указаны
    if brand_names:
        existing_brands = Brand.objects.filter(name__in=brand_names).values_list('name', flat=True)
        missing_brands = [brand for brand in brand_names if brand not in existing_brands]
        if missing_brands:
            return Response(
                {"error": f"Бренды не найдены: {missing_brands}"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    # Логируем параметры фильтрации
    logger.info(f"Запрос экспорта с фильтрами: подгруппы={subgroup_ids}, бренды={brand_names}, только_два_параметра={only_two_params}, без_описания={no_description}, async={is_async}")
    
    if is_async:
        # Асинхронный запуск новой задачи
        task = export_products_by_filters.delay(subgroup_ids, brand_names, only_two_params, no_description)
        
        # Формируем описание фильтров для ответа
        filters_description = []
        if subgroup_ids:
            filters_description.append(f"подгруппы: {len(subgroup_ids)} шт.")
        if brand_names:
            filters_description.append(f"бренды: {', '.join(brand_names)}")
        
        message = f"Начат экспорт товаров с фильтрами ({', '.join(filters_description)}). Используйте task_id для отслеживания."
        
        return Response({
            "task_id": task.id,
            "message": message
        })
    else:
        # Синхронный запуск новой задачи
        try:
            result = export_products_by_filters(subgroup_ids, brand_names, only_two_params, no_description)
            
            if result['success']:
                # Декодируем base64 данные обратно в бинарные
                file_data = base64.b64decode(result['data'])
                
                # Возвращаем файл как HTTP response для скачивания
                response = HttpResponse(
                    file_data,
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="{result["filename"]}"'
                return response
            else:
                return Response(
                    {"error": result['error']}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            return Response(
                {"error": f"Ошибка при экспорте: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_export_task(request, task_id):
    """
    Проверка статуса задачи экспорта.
    
    GET /api/products/export-status/{task_id}/
    """
    try:
        result = AsyncResult(task_id)
        
        if result.ready():
            if result.successful():
                task_result = result.get()
                if task_result['success']:
                    # Декодируем base64 данные обратно в бинарные
                    file_data = base64.b64decode(task_result['data'])
                    
                    # Возвращаем файл как HTTP response для скачивания
                    response = HttpResponse(
                        file_data,
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                    response['Content-Disposition'] = f'attachment; filename="{task_result["filename"]}"'
                    return response
                else:
                    return Response(
                        {"status": "failed", "error": task_result['error']}, 
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                return Response(
                    {"status": "failed", "error": str(result.info)}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            return Response({
                "status": "pending",
                "message": "Задача еще выполняется..."
            })
            
    except Exception as e:
        return Response(
            {"error": f"Ошибка при проверке статуса задачи: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
