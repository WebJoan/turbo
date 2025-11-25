from django.contrib.auth import get_user_model
from django.db.models import Q, Prefetch
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter, DateFilter
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import pandas as pd
from datetime import datetime
from decimal import Decimal

from .models import (
    Competitor,
    CompetitorProduct,
    CompetitorProductMatch,
    CompetitorPriceStockSnapshot,
    OurPriceHistory,
)
from .serializers import (
    CompetitorSerializer,
    CompetitorProductSerializer,
    CompetitorProductMatchSerializer,
    CompetitorProductMatchCreateSerializer,
    CompetitorPriceStockSnapshotSerializer,
    CompetitorPriceStockSnapshotCreateSerializer,
    OurPriceHistorySerializer,
    PriceComparisonSerializer,
)
from .tasks import import_histprice_from_mysql, export_competitor_price_comparison_task
import base64

User = get_user_model()


# Фильтры для конкурентов
class CompetitorFilter(FilterSet):
    name_contains = CharFilter(field_name="name", lookup_expr="icontains")
    data_source_type = CharFilter(field_name="data_source_type", lookup_expr="exact")

    class Meta:
        model = Competitor
        fields = ["name", "data_source_type"]


# Фильтры для позиций конкурентов
class CompetitorProductFilter(FilterSet):
    competitor_id = NumberFilter(field_name="competitor_id", lookup_expr="exact")
    part_number = CharFilter(field_name="part_number", lookup_expr="icontains")
    brand_name = CharFilter(field_name="brand__name", lookup_expr="icontains")
    has_mapping = CharFilter(method="filter_has_mapping")

    class Meta:
        model = CompetitorProduct
        fields = ["competitor", "part_number", "brand__name"]

    def filter_has_mapping(self, queryset, name, value):
        if value.lower() in ["true", "1", "yes"]:
            return queryset.filter(mapped_product__isnull=False)
        elif value.lower() in ["false", "0", "no"]:
            return queryset.filter(mapped_product__isnull=True)
        return queryset


# Фильтры для снимков цен/склада
class CompetitorPriceStockSnapshotFilter(FilterSet):
    competitor_id = NumberFilter(field_name="competitor_id", lookup_expr="exact")
    competitor_product_id = NumberFilter(field_name="competitor_product_id", lookup_expr="exact")
    collected_after = DateFilter(field_name="collected_at", lookup_expr="gte")
    collected_before = DateFilter(field_name="collected_at", lookup_expr="lte")
    stock_status = CharFilter(field_name="stock_status", lookup_expr="exact")
    has_stock = CharFilter(method="filter_has_stock")

    class Meta:
        model = CompetitorPriceStockSnapshot
        fields = ["competitor", "stock_status"]

    def filter_has_stock(self, queryset, name, value):
        if value.lower() in ["true", "1", "yes"]:
            return queryset.filter(stock_qty__gt=0)
        elif value.lower() in ["false", "0", "no"]:
            return queryset.filter(Q(stock_qty__isnull=True) | Q(stock_qty=0))
        return queryset


# Фильтры для истории наших цен
class OurPriceHistoryFilter(FilterSet):
    product_id = NumberFilter(field_name="product_id", lookup_expr="exact")
    moment_after = DateFilter(field_name="moment", lookup_expr="gte")
    moment_before = DateFilter(field_name="moment", lookup_expr="lte")

    class Meta:
        model = OurPriceHistory
        fields = ["product"]


# ViewSets для конкурентов
class CompetitorViewSet(viewsets.ModelViewSet):
    queryset = Competitor.objects.all()
    serializer_class = CompetitorSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CompetitorFilter
    search_fields = ["name", "data_url"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


# ViewSets для позиций конкурентов
class CompetitorProductViewSet(viewsets.ModelViewSet):
    queryset = CompetitorProduct.objects.select_related("competitor", "mapped_product").all()
    serializer_class = CompetitorProductSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CompetitorProductFilter
    search_fields = ["part_number", "brand__name", "name", "ext_id"]
    ordering_fields = ["part_number", "brand__name", "created_at"]
    ordering = ["part_number"]


# ViewSets для сопоставлений товаров
class CompetitorProductMatchViewSet(viewsets.ModelViewSet):
    queryset = CompetitorProductMatch.objects.select_related(
        "competitor_product__competitor", "product"
    ).all()
    serializer_class = CompetitorProductMatchSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["competitor_product__part_number", "product__name"]
    ordering_fields = ["confidence", "created_at"]
    ordering = ["-confidence"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CompetitorProductMatchCreateSerializer
        return CompetitorProductMatchSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        product_id = self.request.query_params.get("product_id")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset


# ViewSets для снимков цен/склада конкурентов
class CompetitorPriceStockSnapshotViewSet(viewsets.ModelViewSet):
    queryset = CompetitorPriceStockSnapshot.objects.select_related(
        "competitor", "competitor_product"
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CompetitorPriceStockSnapshotFilter
    search_fields = ["competitor__name", "competitor_product__part_number"]
    ordering_fields = ["collected_at", "price_ex_vat"]
    ordering = ["-collected_at"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CompetitorPriceStockSnapshotCreateSerializer
        return CompetitorPriceStockSnapshotSerializer

    @action(detail=False, methods=["get"], url_path="latest")
    def get_latest_snapshots(self, request):
        """Получить последние снимки для каждого продукта конкурента"""
        competitor_id = request.query_params.get("competitor_id")

        queryset = self.get_queryset()
        if competitor_id:
            queryset = queryset.filter(competitor_id=competitor_id)

        # Получаем последние снимки для каждого competitor_product
        latest_snapshots = []
        competitor_products = set()

        for snapshot in queryset.order_by("-collected_at"):
            if snapshot.competitor_product_id not in competitor_products:
                latest_snapshots.append(snapshot)
                competitor_products.add(snapshot.competitor_product_id)
                if len(latest_snapshots) >= 100:  # Ограничение для производительности
                    break

        serializer = self.get_serializer(latest_snapshots, many=True)
        return Response(serializer.data)


# ViewSets для истории наших цен
class OurPriceHistoryViewSet(viewsets.ModelViewSet):
    queryset = OurPriceHistory.objects.select_related("product").all()
    serializer_class = OurPriceHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = OurPriceHistoryFilter
    search_fields = ["product__name", "product__ext_id"]
    ordering_fields = ["moment", "price_ex_vat"]
    ordering = ["-moment"]


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_histprice(request):
    """Запустить импорт истории цен из MySQL"""
    task = import_histprice_from_mysql.delay()
    return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_price_comparison(request, product_id):
    """Получить сравнение цен для товара"""
    try:
        from goods.models import Product
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

    # История наших цен
    our_price_history = OurPriceHistory.objects.filter(product=product).order_by("-moment")[:10]

    # Сопоставления с товарами конкурентов
    matches = CompetitorProductMatch.objects.filter(product=product).select_related(
        "competitor_product__competitor"
    )

    # Последние цены конкурентов для сопоставленных товаров
    competitor_product_ids = matches.values_list("competitor_product_id", flat=True)
    competitor_prices = CompetitorPriceStockSnapshot.objects.filter(
        competitor_product_id__in=competitor_product_ids
    ).select_related(
        "competitor", "competitor_product"
    ).order_by("-collected_at")

    # Группируем по продукту конкурента, берём самые свежие цены
    latest_prices = {}
    for price in competitor_prices:
        key = price.competitor_product_id
        if key not in latest_prices:
            latest_prices[key] = price

    competitor_prices_list = list(latest_prices.values())

    data = {
        "our_product_id": product.id,
        "our_product_name": product.name,
        "our_current_price": our_price_history.first().price_ex_vat if our_price_history.exists() else None,
        "our_price_history": OurPriceHistorySerializer(our_price_history, many=True).data,
        "competitor_prices": CompetitorPriceStockSnapshotSerializer(competitor_prices_list, many=True).data,
        "matches": CompetitorProductMatchSerializer(matches, many=True).data,
    }

    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def export_competitor_price_comparison(request):
    """
    Запуск экспорта сравнения цен с конкурентами.
    
    POST /api/stock/export-price-comparison/
    
    Запускает асинхронную задачу Celery для генерации Excel файла.
    Возвращает task_id для отслеживания прогресса.
    """
    # Запускаем асинхронную задачу
    task = export_competitor_price_comparison_task.delay()
    
    return Response({
        "task_id": task.id,
        "message": "Начат экспорт сравнения цен. Используйте task_id для отслеживания прогресса."
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_price_comparison_export_task(request, task_id):
    """
    Проверка статуса задачи экспорта сравнения цен.
    
    GET /api/stock/export-price-comparison-status/<task_id>/
    
    Возвращает статус задачи и файл при завершении.
    """
    from celery.result import AsyncResult
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        task = AsyncResult(task_id)
        
        # Проверяем состояние задачи
        logger.info(f"Проверка статуса задачи {task_id}, state: {task.state}")
        
        if task.ready():
            try:
                result = task.result
                logger.info(f"Задача {task_id} завершена, успех: {result.get('success') if isinstance(result, dict) else False}")
                
                if isinstance(result, dict) and result.get('success'):
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
                    error_message = result.get('error', 'Неизвестная ошибка') if isinstance(result, dict) else str(result)
                    logger.error(f"Задача {task_id} завершилась с ошибкой: {error_message}")
                    return Response(
                        {"status": "failed", "error": error_message},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            except Exception as e:
                logger.error(f"Ошибка при получении результата задачи {task_id}: {str(e)}", exc_info=True)
                return Response(
                    {"status": "failed", "error": f"Ошибка при получении результата: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            # Задача ещё выполняется
            logger.debug(f"Задача {task_id} ещё выполняется, state: {task.state}")
            return Response({
                "status": "processing",
                "message": "Экспорт в процессе выполнения...",
                "state": task.state
            })
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса задачи {task_id}: {str(e)}", exc_info=True)
        return Response(
            {"status": "error", "error": f"Ошибка при проверке статуса задачи: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def export_competitor_sales(request):
    """
    Запуск экспорта продаж конкурентов.
    
    POST /api/stock/export-competitor-sales/
    
    Параметры:
    - date_from (опционально): начальная дата в формате YYYY-MM-DD (по умолчанию: 30 дней назад)
    - date_to (опционально): конечная дата в формате YYYY-MM-DD (по умолчанию: сегодня)
    - competitor_ids (опционально): массив ID конкурентов для анализа (по умолчанию: все конкуренты)
    
    Запускает асинхронную задачу Celery для генерации Excel файла.
    Возвращает task_id для отслеживания прогресса.
    """
    from .tasks import export_competitor_sales_task
    
    date_from = request.data.get('date_from')
    date_to = request.data.get('date_to')
    competitor_ids = request.data.get('competitor_ids')  # Ожидаем массив ID
    
    # Валидация competitor_ids
    if competitor_ids is not None:
        if not isinstance(competitor_ids, list):
            return Response(
                {"error": "competitor_ids должен быть массивом"},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Проверяем, что все элементы - числа
        try:
            competitor_ids = [int(cid) for cid in competitor_ids]
        except (ValueError, TypeError):
            return Response(
                {"error": "competitor_ids должен содержать только числа"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Запускаем асинхронную задачу
    task = export_competitor_sales_task.delay(
        date_from=date_from, 
        date_to=date_to,
        competitor_ids=competitor_ids
    )
    
    return Response({
        "task_id": task.id,
        "message": "Начат экспорт продаж конкурентов. Используйте task_id для отслеживания прогресса.",
        "date_from": date_from,
        "date_to": date_to,
        "competitor_ids": competitor_ids
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_competitor_sales_export_task(request, task_id):
    """
    Проверка статуса задачи экспорта продаж конкурентов.
    
    GET /api/stock/export-competitor-sales-status/<task_id>/
    
    Возвращает статус задачи и файл при завершении.
    """
    from celery.result import AsyncResult
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        task = AsyncResult(task_id)
        
        # Проверяем состояние задачи
        logger.info(f"Проверка статуса задачи экспорта продаж {task_id}, state: {task.state}")
        
        if task.ready():
            try:
                result = task.result
                logger.info(f"Задача {task_id} завершена, успех: {result.get('success') if isinstance(result, dict) else False}")
                
                if isinstance(result, dict) and result.get('success'):
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
                    error_message = result.get('error', 'Неизвестная ошибка') if isinstance(result, dict) else str(result)
                    logger.error(f"Задача {task_id} завершилась с ошибкой: {error_message}")
                    return Response(
                        {"status": "failed", "error": error_message},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            except Exception as e:
                logger.error(f"Ошибка при получении результата задачи {task_id}: {str(e)}", exc_info=True)
                return Response(
                    {"status": "failed", "error": f"Ошибка при получении результата: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            # Задача ещё выполняется
            logger.debug(f"Задача {task_id} ещё выполняется, state: {task.state}")
            return Response({
                "status": "processing",
                "message": "Экспорт продаж конкурентов в процессе выполнения...",
                "state": task.state
            })
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса задачи {task_id}: {str(e)}", exc_info=True)
        return Response(
            {"status": "error", "error": f"Ошибка при проверке статуса задачи: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )