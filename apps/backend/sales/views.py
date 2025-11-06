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
