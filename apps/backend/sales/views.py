from django.db.models import Sum, Count, F, DecimalField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear, Coalesce
from decimal import Decimal
from rest_framework import viewsets, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, DateFilter, NumberFilter, CharFilter

from .models import Invoice, InvoiceLine
from .serializers import (
    InvoiceSerializer,
    InvoiceListSerializer,
    SalesSummarySerializer,
    TimeSeriesDataSerializer,
    TopItemSerializer,
)


class InvoiceFilter(FilterSet):
    """Фильтр для счетов"""
    date_from = DateFilter(field_name='invoice_date', lookup_expr='gte')
    date_to = DateFilter(field_name='invoice_date', lookup_expr='lte')
    company_id = NumberFilter(field_name='company__id')
    company_name = CharFilter(field_name='company__name', lookup_expr='icontains')
    invoice_type = CharFilter(field_name='invoice_type')
    sale_type = CharFilter(field_name='sale_type')
    currency = CharFilter(field_name='currency')

    class Meta:
        model = Invoice
        fields = ['date_from', 'date_to', 'company_id', 'company_name', 'invoice_type', 'sale_type', 'currency']


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для просмотра счетов"""
    queryset = Invoice.objects.select_related('company').prefetch_related('lines__product').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = InvoiceFilter
    search_fields = ['invoice_number', 'company__name', 'company__short_name']
    ordering_fields = ['id', 'invoice_date', 'invoice_number', 'created_at']
    ordering = ['-invoice_date']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return InvoiceSerializer
        return InvoiceListSerializer


def get_period_trunc(period_type):
    """Возвращает функцию для группировки по периоду"""
    if period_type == 'day':
        return TruncDay
    elif period_type == 'week':
        return TruncWeek
    elif period_type == 'year':
        return TruncYear
    else:  # по умолчанию month
        return TruncMonth


def parse_filters(request):
    """Парсит фильтры из запроса"""
    filters = {}
    
    # Даты
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from:
        filters['invoice_date__gte'] = date_from
    if date_to:
        filters['invoice_date__lte'] = date_to
    
    # Компания
    company_id = request.query_params.get('company_id')
    if company_id:
        filters['company_id'] = company_id
    
    # Продукт (для фильтрации через строки счета)
    product_id = request.query_params.get('product_id')
    
    # Валюта
    currency = request.query_params.get('currency')
    if currency:
        filters['currency'] = currency
    
    # Тип продажи
    sale_type = request.query_params.get('sale_type')
    if sale_type:
        filters['sale_type'] = sale_type
    
    return filters, product_id


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_summary(request):
    """
    Общая сводка по продажам
    """
    filters, product_id = parse_filters(request)
    
    # Базовый queryset
    queryset = Invoice.objects.filter(invoice_type=Invoice.InvoiceType.SALE, **filters)
    
    if product_id:
        queryset = queryset.filter(lines__product_id=product_id).distinct()
    
    # Получаем все строки счетов
    lines = InvoiceLine.objects.filter(invoice__in=queryset)
    
    # Агрегированная статистика
    stats = lines.aggregate(
        total_revenue=Coalesce(
            Sum(F('quantity') * F('price'), output_field=DecimalField()),
            Decimal('0')
        )
    )
    
    total_orders = queryset.count()
    total_customers = queryset.values('company').distinct().count()
    
    average_check = Decimal('0')
    if total_orders > 0:
        average_check = stats['total_revenue'] / total_orders
    
    result = {
        'total_revenue': float(stats['total_revenue']),
        'total_orders': total_orders,
        'total_customers': total_customers,
        'average_check': float(average_check),
        'growth_rate': None
    }
    
    serializer = SalesSummarySerializer(result)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_sales_timeseries(request):
    """
    Временной ряд продаж по клиенту или всем клиентам
    """
    filters, product_id = parse_filters(request)
    period_type = request.query_params.get('period_type', 'month')
    
    # Базовый queryset
    queryset = Invoice.objects.filter(invoice_type=Invoice.InvoiceType.SALE, **filters)
    
    if product_id:
        queryset = queryset.filter(lines__product_id=product_id).distinct()
    
    # Группировка по периоду
    period_trunc = get_period_trunc(period_type)
    
    # Получаем ID всех счетов
    invoice_ids = list(queryset.values_list('id', flat=True))
    
    # Агрегируем через строки счетов
    timeseries_data = InvoiceLine.objects.filter(
        invoice_id__in=invoice_ids
    ).annotate(
        period=period_trunc('invoice__invoice_date')
    ).values('period').annotate(
        revenue=Coalesce(
            Sum(F('quantity') * F('price'), output_field=DecimalField()),
            Decimal('0')
        ),
        orders=Count('invoice', distinct=True),
        customers=Count('invoice__company', distinct=True)
    ).order_by('period')
    
    results = []
    for item in timeseries_data:
        avg_check = Decimal('0')
        if item['orders'] > 0:
            avg_check = item['revenue'] / item['orders']
        
        results.append({
            'period': item['period'].strftime('%Y-%m-%d'),
            'revenue': float(item['revenue']),
            'orders': item['orders'],
            'customers': item['customers'],
            'average_check': float(avg_check)
        })
    
    serializer = TimeSeriesDataSerializer(results, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_sales_top(request):
    """
    Топ клиентов по объему продаж
    """
    filters, product_id = parse_filters(request)

    limit_param = request.query_params.get('limit')
    try:
        limit = max(1, int(limit_param)) if limit_param is not None else 20
    except (TypeError, ValueError):
        limit = 20

    invoice_queryset = Invoice.objects.filter(
        invoice_type=Invoice.InvoiceType.SALE,
        **filters
    )

    if product_id:
        invoice_queryset = invoice_queryset.filter(
            lines__product_id=product_id
        ).distinct()

    invoice_ids = list(invoice_queryset.values_list('id', flat=True))

    if not invoice_ids:
        serializer = TopItemSerializer([], many=True)
        return Response(serializer.data)

    lines_queryset = InvoiceLine.objects.filter(invoice_id__in=invoice_ids)

    if product_id:
        lines_queryset = lines_queryset.filter(product_id=product_id)

    totals = lines_queryset.aggregate(
        total_revenue=Coalesce(
            Sum(F('quantity') * F('price'), output_field=DecimalField()),
            Decimal('0')
        )
    )

    total_revenue = totals['total_revenue'] or Decimal('0')

    top_customers_query = (
        lines_queryset.values('invoice__company_id', 'invoice__company__name')
        .annotate(
            revenue=Coalesce(
                Sum(F('quantity') * F('price'), output_field=DecimalField()),
                Decimal('0')
            ),
            orders=Count('invoice', distinct=True)
        )
        .order_by('-revenue')
    )

    top_customers = list(top_customers_query[:limit])

    results = []
    for item in top_customers:
        revenue = item['revenue'] or Decimal('0')
        percentage = float(
            (revenue / total_revenue * Decimal('100'))
            if total_revenue > 0
            else Decimal('0')
        )

        results.append({
            'id': item['invoice__company_id'],
            'name': item['invoice__company__name'] or 'Без названия',
            'total_revenue': float(revenue),
            'order_count': item['orders'],
            'percentage': percentage,
        })

    serializer = TopItemSerializer(results, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_sales_top(request):
    """Топ товаров по объему продаж"""
    filters, product_id = parse_filters(request)

    limit_param = request.query_params.get('limit')
    try:
        limit = max(1, int(limit_param)) if limit_param is not None else 20
    except (TypeError, ValueError):
        limit = 20

    invoice_queryset = Invoice.objects.filter(
        invoice_type=Invoice.InvoiceType.SALE,
        **filters
    )

    if product_id:
        invoice_queryset = invoice_queryset.filter(
            lines__product_id=product_id
        ).distinct()

    invoice_ids = list(invoice_queryset.values_list('id', flat=True))

    if not invoice_ids:
        serializer = TopItemSerializer([], many=True)
        return Response(serializer.data)

    lines_queryset = InvoiceLine.objects.filter(invoice_id__in=invoice_ids)

    if product_id:
        lines_queryset = lines_queryset.filter(product_id=product_id)

    totals = lines_queryset.aggregate(
        total_revenue=Coalesce(
            Sum(F('quantity') * F('price'), output_field=DecimalField()),
            Decimal('0')
        )
    )

    total_revenue = totals['total_revenue'] or Decimal('0')

    top_products_query = (
        lines_queryset.values('product_id', 'product__name', 'product__complex_name')
        .annotate(
            revenue=Coalesce(
                Sum(F('quantity') * F('price'), output_field=DecimalField()),
                Decimal('0')
            ),
            orders=Count('invoice', distinct=True)
        )
        .order_by('-revenue')
    )

    top_products = list(top_products_query[:limit])

    results = []
    for item in top_products:
        revenue = item['revenue'] or Decimal('0')
        percentage = float(
            (revenue / total_revenue * Decimal('100'))
            if total_revenue > 0
            else Decimal('0')
        )

        name = item['product__complex_name'] or item['product__name'] or 'Без названия'
        if item['product__name'] and item['product__complex_name']:
            name = f"{item['product__name']} — {item['product__complex_name']}"

        results.append({
            'id': item['product_id'],
            'name': name,
            'total_revenue': float(revenue),
            'order_count': item['orders'],
            'percentage': percentage,
        })

    serializer = TopItemSerializer(results, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_sales_timeseries(request):
    """
    Временной ряд продаж по товару или всем товарам
    """
    filters, product_id = parse_filters(request)
    period_type = request.query_params.get('period_type', 'month')
    
    # Базовый queryset счетов
    invoice_queryset = Invoice.objects.filter(invoice_type=Invoice.InvoiceType.SALE, **filters)
    invoice_ids = list(invoice_queryset.values_list('id', flat=True))
    
    # Работаем через строки счета
    queryset = InvoiceLine.objects.filter(invoice_id__in=invoice_ids)
    
    if product_id:
        queryset = queryset.filter(product_id=product_id)
    
    # Группировка по периоду
    period_trunc = get_period_trunc(period_type)
    
    timeseries = queryset.annotate(
        period=period_trunc('invoice__invoice_date')
    ).values('period').annotate(
        revenue=Coalesce(
            Sum(F('quantity') * F('price'), output_field=DecimalField()),
            Decimal('0')
        ),
        orders=Count('invoice', distinct=True),
        customers=Count('invoice__company', distinct=True)
    ).order_by('period')
    
    results = []
    for item in timeseries:
        avg_check = Decimal('0')
        if item['orders'] > 0:
            avg_check = item['revenue'] / item['orders']
        
        results.append({
            'period': item['period'].strftime('%Y-%m-%d'),
            'revenue': float(item['revenue']),
            'orders': item['orders'],
            'customers': item['customers'],
            'average_check': float(avg_check)
        })
    
    serializer = TimeSeriesDataSerializer(results, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_customer_sales_dynamics_report_view(request):
    """
    API endpoint для запуска генерации Excel отчета по динамике продаж по клиентам.
    
    Создает отчет с анализом:
    - Объем выручки
    - Количество заказов
    - Средний чек
    В разрезе времени (день, неделя, месяц, год) и компании-клиента.
    
    Параметры (POST body):
    - date_from: Начальная дата (YYYY-MM-DD), опционально
    - date_to: Конечная дата (YYYY-MM-DD), опционально
    - company_ids: Список ID компаний, опционально (все компании если не указано)
    - period_type: Тип периодизации (day/week/month/year), по умолчанию month
    
    Возвращает:
    - task_id: ID Celery задачи для отслеживания статуса
    - status: Статус запроса
    - message: Информационное сообщение
    """
    from .serializers import CustomerSalesDynamicsRequestSerializer, CustomerSalesDynamicsResponseSerializer
    from .tasks import generate_customer_sales_dynamics_report
    
    # Валидация входных данных
    request_serializer = CustomerSalesDynamicsRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response(
            {
                'status': 'error',
                'message': 'Ошибка валидации данных',
                'errors': request_serializer.errors
            },
            status=400
        )
    
    validated_data = request_serializer.validated_data
    
    # Преобразуем даты в строки для передачи в Celery
    date_from = validated_data.get('date_from')
    date_to = validated_data.get('date_to')
    company_ids = validated_data.get('company_ids')
    period_type = validated_data.get('period_type', 'month')
    
    # Преобразуем даты в строки
    if date_from:
        date_from = date_from.strftime('%Y-%m-%d')
    if date_to:
        date_to = date_to.strftime('%Y-%m-%d')
    
    # Запускаем Celery задачу
    task = generate_customer_sales_dynamics_report.delay(
        date_from=date_from,
        date_to=date_to,
        company_ids=company_ids,
        period_type=period_type
    )
    
    # Формируем ответ
    response_data = {
        'task_id': task.id,
        'status': 'pending',
        'message': f'Задача создания отчета по динамике продаж запущена. ID задачи: {task.id}. Используйте GET /api/sales/report-status/{task.id}/ для проверки статуса.'
    }
    
    response_serializer = CustomerSalesDynamicsResponseSerializer(response_data)
    return Response(response_serializer.data, status=202)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_report_task_status(request, task_id):
    """
    Проверка статуса задачи генерации отчета.
    
    Параметры:
    - task_id: ID Celery задачи
    
    Возвращает:
    - state: Статус задачи (PENDING, STARTED, SUCCESS, FAILURE, etc.)
    - result: Результат выполнения задачи (если завершена успешно)
    - error: Ошибка (если завершена с ошибкой)
    """
    from celery.result import AsyncResult
    
    task_result = AsyncResult(task_id)
    
    response_data = {
        'task_id': task_id,
        'state': task_result.state,
    }
    
    if task_result.state == 'PENDING':
        response_data['message'] = 'Задача ожидает выполнения или еще не начата'
    elif task_result.state == 'STARTED':
        response_data['message'] = 'Задача выполняется'
    elif task_result.state == 'SUCCESS':
        result = task_result.result
        if isinstance(result, dict):
            if 'error' in result:
                response_data['status'] = 'error'
                response_data['message'] = result['error']
            else:
                response_data['status'] = 'success'
                response_data['message'] = 'Отчет успешно создан'
                response_data['result'] = result
        else:
            response_data['status'] = 'success'
            response_data['message'] = 'Задача выполнена'
            response_data['result'] = str(result)
    elif task_result.state == 'FAILURE':
        response_data['status'] = 'error'
        response_data['message'] = 'Ошибка при выполнении задачи'
        response_data['error'] = str(task_result.info)
    else:
        response_data['message'] = f'Неизвестный статус: {task_result.state}'
    
    return Response(response_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_product_sales_dynamics_report_view(request):
    """
    API endpoint для запуска генерации Excel отчета по динамике продаж по товарам.
    
    Создает отчет с анализом:
    - Объем выручки
    - Количество заказов
    - Средний чек
    - Количество проданных единиц
    В разрезе времени (день, неделя, месяц, год) и товара.
    
    Параметры (POST body):
    - date_from: Начальная дата (YYYY-MM-DD), опционально
    - date_to: Конечная дата (YYYY-MM-DD), опционально
    - product_ids: Список ID товаров, опционально (все товары если не указано)
    - period_type: Тип периодизации (day/week/month/year), по умолчанию month
    
    Возвращает:
    - task_id: ID Celery задачи для отслеживания статуса
    - status: Статус запроса
    - message: Информационное сообщение
    """
    from .serializers import ProductSalesDynamicsRequestSerializer, ProductSalesDynamicsResponseSerializer
    from .tasks import generate_product_sales_dynamics_report
    
    # Валидация входных данных
    request_serializer = ProductSalesDynamicsRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response(
            {
                'status': 'error',
                'message': 'Ошибка валидации данных',
                'errors': request_serializer.errors
            },
            status=400
        )
    
    validated_data = request_serializer.validated_data
    
    # Преобразуем даты в строки для передачи в Celery
    date_from = validated_data.get('date_from')
    date_to = validated_data.get('date_to')
    product_ids = validated_data.get('product_ids')
    period_type = validated_data.get('period_type', 'month')
    
    # Преобразуем даты в строки
    if date_from:
        date_from = date_from.strftime('%Y-%m-%d')
    if date_to:
        date_to = date_to.strftime('%Y-%m-%d')
    
    # Запускаем Celery задачу
    task = generate_product_sales_dynamics_report.delay(
        date_from=date_from,
        date_to=date_to,
        product_ids=product_ids,
        period_type=period_type
    )
    
    # Формируем ответ
    response_data = {
        'task_id': task.id,
        'status': 'pending',
        'message': f'Задача создания отчета по динамике продаж товаров запущена. ID задачи: {task.id}. Используйте GET /api/sales/report-status/{task.id}/ для проверки статуса.'
    }
    
    response_serializer = ProductSalesDynamicsResponseSerializer(response_data)
    return Response(response_serializer.data, status=202)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_customer_cohort_analysis_report_view(request):
    """
    API endpoint для запуска генерации Excel отчета когортного анализа клиентов.
    
    Создает отчет с анализом:
    - Retention Rate (процент вернувшихся клиентов)
    - Revenue Retention (выручка от когорты по периодам)
    - Размер когорт
    - Количество заказов от когорты
    
    Когорты формируются на основе месяца/недели первой покупки клиента.
    
    Параметры (POST body):
    - date_from: Начальная дата для фильтрации когорт (YYYY-MM-DD), опционально
    - date_to: Конечная дата для фильтрации когорт (YYYY-MM-DD), опционально
    - period_type: Тип периодизации (week/month), по умолчанию month
    
    Возвращает:
    - task_id: ID Celery задачи для отслеживания статуса
    - status: Статус запроса
    - message: Информационное сообщение
    """
    from .serializers import CustomerCohortAnalysisRequestSerializer, CustomerCohortAnalysisResponseSerializer
    from .tasks import generate_customer_cohort_analysis_report
    
    # Валидация входных данных
    request_serializer = CustomerCohortAnalysisRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response(
            {
                'status': 'error',
                'message': 'Ошибка валидации данных',
                'errors': request_serializer.errors
            },
            status=400
        )
    
    validated_data = request_serializer.validated_data
    
    # Преобразуем даты в строки для передачи в Celery
    date_from = validated_data.get('date_from')
    date_to = validated_data.get('date_to')
    period_type = validated_data.get('period_type', 'month')
    
    # Преобразуем даты в строки
    if date_from:
        date_from = date_from.strftime('%Y-%m-%d')
    if date_to:
        date_to = date_to.strftime('%Y-%m-%d')
    
    # Запускаем Celery задачу
    task = generate_customer_cohort_analysis_report.delay(
        date_from=date_from,
        date_to=date_to,
        period_type=period_type
    )
    
    # Формируем ответ
    response_data = {
        'task_id': task.id,
        'status': 'pending',
        'message': f'Задача создания когортного анализа клиентов запущена. ID задачи: {task.id}. Используйте GET /api/sales/report-status/{task.id}/ для проверки статуса.'
    }
    
    response_serializer = CustomerCohortAnalysisResponseSerializer(response_data)
    return Response(response_serializer.data, status=202)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_rfm_segmentation_report_view(request):
    """
    API endpoint для запуска генерации Excel отчета RFM-сегментации клиентов.
    
    Создает отчет с RFM анализом:
    - Recency (R): Давность последней покупки
    - Frequency (F): Частота покупок
    - Monetary (M): Денежная ценность клиента
    
    Сегментирует клиентов на группы: Champions, Loyal Customers, At Risk, и др.
    
    Параметры (POST body):
    - date_from: Начальная дата для анализа транзакций (YYYY-MM-DD), опционально
    - date_to: Конечная дата для анализа транзакций (YYYY-MM-DD), опционально
    - reference_date: Референсная дата для расчета Recency (YYYY-MM-DD), опционально (по умолчанию - сегодня)
    
    Возвращает:
    - task_id: ID Celery задачи для отслеживания статуса
    - status: Статус запроса
    - message: Информационное сообщение
    """
    from .serializers import RFMSegmentationRequestSerializer, RFMSegmentationResponseSerializer
    from .tasks import generate_rfm_segmentation_report
    
    # Валидация входных данных
    request_serializer = RFMSegmentationRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response(
            {
                'status': 'error',
                'message': 'Ошибка валидации данных',
                'errors': request_serializer.errors
            },
            status=400
        )
    
    validated_data = request_serializer.validated_data
    
    # Преобразуем даты в строки для передачи в Celery
    date_from = validated_data.get('date_from')
    date_to = validated_data.get('date_to')
    reference_date = validated_data.get('reference_date')
    
    # Преобразуем даты в строки
    if date_from:
        date_from = date_from.strftime('%Y-%m-%d')
    if date_to:
        date_to = date_to.strftime('%Y-%m-%d')
    if reference_date:
        reference_date = reference_date.strftime('%Y-%m-%d')
    
    # Запускаем Celery задачу
    task = generate_rfm_segmentation_report.delay(
        date_from=date_from,
        date_to=date_to,
        reference_date=reference_date
    )
    
    # Формируем ответ
    response_data = {
        'task_id': task.id,
        'status': 'pending',
        'message': f'Задача создания RFM-сегментации клиентов запущена. ID задачи: {task.id}. Используйте GET /api/sales/report-status/{task.id}/ для проверки статуса.'
    }
    
    response_serializer = RFMSegmentationResponseSerializer(response_data)
    return Response(response_serializer.data, status=202)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_ltv_analysis_report_view(request):
    """
    API endpoint для запуска генерации Excel отчета LTV (Customer Lifetime Value) анализа.
    
    Создает отчет с расчетом пожизненной ценности клиентов:
    - Historical LTV: реальная выручка от клиента
    - Average Order Value (AOV): средний чек
    - Purchase Frequency: частота покупок
    - Predicted LTV: прогнозная ценность на 12 и 24 месяца
    
    Параметры (POST body):
    - date_from: Начальная дата для анализа (YYYY-MM-DD), опционально
    - date_to: Конечная дата для анализа (YYYY-MM-DD), опционально
    
    Возвращает:
    - task_id: ID Celery задачи для отслеживания статуса
    - status: Статус запроса
    - message: Информационное сообщение
    """
    from .serializers import LTVAnalysisRequestSerializer, LTVAnalysisResponseSerializer
    from .tasks import generate_ltv_analysis_report
    
    # Валидация входных данных
    request_serializer = LTVAnalysisRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response(
            {
                'status': 'error',
                'message': 'Ошибка валидации данных',
                'errors': request_serializer.errors
            },
            status=400
        )
    
    validated_data = request_serializer.validated_data
    
    # Преобразуем даты в строки для передачи в Celery
    date_from = validated_data.get('date_from')
    date_to = validated_data.get('date_to')
    
    # Преобразуем даты в строки
    if date_from:
        date_from = date_from.strftime('%Y-%m-%d')
    if date_to:
        date_to = date_to.strftime('%Y-%m-%d')
    
    # Запускаем Celery задачу
    task = generate_ltv_analysis_report.delay(
        date_from=date_from,
        date_to=date_to
    )
    
    # Формируем ответ
    response_data = {
        'task_id': task.id,
        'status': 'pending',
        'message': f'Задача создания LTV анализа клиентов запущена. ID задачи: {task.id}. Используйте GET /api/sales/report-status/{task.id}/ для проверки статуса.'
    }
    
    response_serializer = LTVAnalysisResponseSerializer(response_data)
    return Response(response_serializer.data, status=202)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_market_basket_analysis_report_view(request):
    """
    API endpoint для запуска генерации Excel отчета Market Basket Analysis (Анализ корзины).
    
    Создает отчет с анализом товаров, покупаемых вместе:
    - Ассоциативные правила (если купил A, то купит B)
    - Support: доля транзакций с товаром/набором
    - Confidence: вероятность покупки B при покупке A
    - Lift: насколько вероятнее покупка B при покупке A
    
    Параметры (POST body):
    - date_from: Начальная дата для анализа (YYYY-MM-DD), опционально
    - date_to: Конечная дата для анализа (YYYY-MM-DD), опционально
    - min_support: Минимальная поддержка (0.005 = 0.5%), по умолчанию 0.005
    - min_confidence: Минимальная уверенность (0.1 = 10%), по умолчанию 0.1
    - min_lift: Минимальный lift, по умолчанию 1.0
    
    Возвращает:
    - task_id: ID Celery задачи для отслеживания статуса
    - status: Статус запроса
    - message: Информационное сообщение
    """
    from .serializers import MarketBasketAnalysisRequestSerializer, MarketBasketAnalysisResponseSerializer
    from .tasks import generate_market_basket_analysis_report
    
    # Валидация входных данных
    request_serializer = MarketBasketAnalysisRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response(
            {
                'status': 'error',
                'message': 'Ошибка валидации данных',
                'errors': request_serializer.errors
            },
            status=400
        )
    
    validated_data = request_serializer.validated_data
    
    # Преобразуем даты в строки для передачи в Celery
    date_from = validated_data.get('date_from')
    date_to = validated_data.get('date_to')
    min_support = validated_data.get('min_support', 0.005)
    min_confidence = validated_data.get('min_confidence', 0.1)
    min_lift = validated_data.get('min_lift', 1.0)
    
    # Преобразуем даты в строки
    if date_from:
        date_from = date_from.strftime('%Y-%m-%d')
    if date_to:
        date_to = date_to.strftime('%Y-%m-%d')
    
    # Запускаем Celery задачу
    task = generate_market_basket_analysis_report.delay(
        date_from=date_from,
        date_to=date_to,
        min_support=min_support,
        min_confidence=min_confidence,
        min_lift=min_lift
    )
    
    # Формируем ответ
    response_data = {
        'task_id': task.id,
        'status': 'pending',
        'message': f'Задача создания Market Basket Analysis запущена. ID задачи: {task.id}. Используйте GET /api/sales/report-status/{task.id}/ для проверки статуса.'
    }
    
    response_serializer = MarketBasketAnalysisResponseSerializer(response_data)
    return Response(response_serializer.data, status=202)
