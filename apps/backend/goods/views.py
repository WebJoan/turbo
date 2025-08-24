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
    ProductSerializer,
    ProductListSerializer,
    ProductGroupSerializer,
    ProductSubgroupSerializer,
    BrandSerializer,
)
from api.serializers import UserCurrentSerializer


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
