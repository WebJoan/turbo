from rest_framework import serializers
from .models import Invoice, InvoiceLine
from customers.serializers import CompanySerializer
from goods.serializers import ProductSerializer


class InvoiceLineSerializer(serializers.ModelSerializer):
    """Сериализатор для строк счета"""
    product = ProductSerializer(read_only=True)
    total_price = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        read_only=True
    )

    class Meta:
        model = InvoiceLine
        fields = [
            'id', 'ext_id', 'invoice', 'product', 
            'quantity', 'price', 'total_price',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'ext_id', 'created_at', 'updated_at']


class InvoiceSerializer(serializers.ModelSerializer):
    """Сериализатор для счетов"""
    company = CompanySerializer(read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        read_only=True
    )
    lines = InvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'ext_id', 'invoice_number', 'invoice_date',
            'company', 'invoice_type', 'sale_type', 'currency',
            'total_amount', 'lines', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'ext_id', 'total_amount', 'created_at', 'updated_at']


class InvoiceListSerializer(serializers.ModelSerializer):
    """Упрощенный сериализатор для списка счетов без строк"""
    company = CompanySerializer(read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        read_only=True
    )

    class Meta:
        model = Invoice
        fields = [
            'id', 'ext_id', 'invoice_number', 'invoice_date',
            'company', 'invoice_type', 'sale_type', 'currency',
            'total_amount', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'ext_id', 'total_amount', 'created_at', 'updated_at']


# Сериализаторы для аналитики

class CustomerSalesAnalyticsSerializer(serializers.Serializer):
    """Сериализатор для аналитики продаж по клиентам"""
    company_id = serializers.IntegerField()
    company_name = serializers.CharField()
    company_type = serializers.CharField()
    is_partner = serializers.BooleanField()
    period = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    order_count = serializers.IntegerField()
    average_check = serializers.DecimalField(max_digits=15, decimal_places=2)


class ProductSalesAnalyticsSerializer(serializers.Serializer):
    """Сериализатор для аналитики продаж по товарам"""
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    product_article = serializers.CharField(allow_null=True, required=False)
    brand_name = serializers.CharField(allow_null=True, required=False)
    subgroup_name = serializers.CharField(allow_null=True, required=False)
    period = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    order_count = serializers.IntegerField()
    quantity_sold = serializers.IntegerField()
    average_price = serializers.DecimalField(max_digits=15, decimal_places=2)


class ChannelSalesAnalyticsSerializer(serializers.Serializer):
    """Сериализатор для аналитики продаж по каналам"""
    channel_type = serializers.CharField()
    customer_type = serializers.CharField()
    period = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    order_count = serializers.IntegerField()
    customer_count = serializers.IntegerField()
    average_check = serializers.DecimalField(max_digits=15, decimal_places=2)


class GeographySalesAnalyticsSerializer(serializers.Serializer):
    """Сериализатор для географии продаж"""
    region = serializers.CharField(allow_null=True, required=False)
    city = serializers.CharField(allow_null=True, required=False)
    district = serializers.CharField(allow_null=True, required=False)
    period = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    order_count = serializers.IntegerField()
    customer_count = serializers.IntegerField()


class SalesSummarySerializer(serializers.Serializer):
    """Сериализатор для общей статистики продаж"""
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_orders = serializers.IntegerField()
    total_customers = serializers.IntegerField()
    average_check = serializers.DecimalField(max_digits=15, decimal_places=2)
    growth_rate = serializers.FloatField(allow_null=True, required=False)


class TopItemSerializer(serializers.Serializer):
    """Сериализатор для топовых клиентов/товаров"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    order_count = serializers.IntegerField()
    percentage = serializers.FloatField()


class TimeSeriesDataSerializer(serializers.Serializer):
    """Сериализатор для данных временных рядов"""
    period = serializers.CharField()
    revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    orders = serializers.IntegerField()
    customers = serializers.IntegerField(allow_null=True, required=False)
    average_check = serializers.DecimalField(max_digits=15, decimal_places=2)


class CustomerSalesDynamicsRequestSerializer(serializers.Serializer):
    """Сериализатор для запроса на генерацию отчета по динамике продаж по клиентам"""
    date_from = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Начальная дата для анализа (YYYY-MM-DD)'
    )
    date_to = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Конечная дата для анализа (YYYY-MM-DD)'
    )
    company_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        help_text='Список ID компаний для фильтрации (если не указан - все компании)'
    )
    period_type = serializers.ChoiceField(
        choices=['day', 'week', 'month', 'year'],
        default='month',
        help_text='Тип периодизации: day (день), week (неделя), month (месяц), year (год)'
    )


class CustomerSalesDynamicsResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа на запрос генерации отчета"""
    task_id = serializers.CharField(help_text='ID Celery задачи для отслеживания статуса')
    status = serializers.CharField(help_text='Статус запроса')
    message = serializers.CharField(help_text='Сообщение о результате')


class ProductSalesDynamicsRequestSerializer(serializers.Serializer):
    """Сериализатор для запроса на генерацию отчета по динамике продаж по товарам"""
    date_from = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Начальная дата для анализа (YYYY-MM-DD)'
    )
    date_to = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Конечная дата для анализа (YYYY-MM-DD)'
    )
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True,
        help_text='Список ID товаров для фильтрации (если не указан - все товары)'
    )
    period_type = serializers.ChoiceField(
        choices=['day', 'week', 'month', 'year'],
        default='month',
        help_text='Тип периодизации: day (день), week (неделя), month (месяц), year (год)'
    )


class ProductSalesDynamicsResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа на запрос генерации отчета по товарам"""
    task_id = serializers.CharField(help_text='ID Celery задачи для отслеживания статуса')
    status = serializers.CharField(help_text='Статус запроса')
    message = serializers.CharField(help_text='Сообщение о результате')


class CustomerCohortAnalysisRequestSerializer(serializers.Serializer):
    """Сериализатор для запроса на генерацию когортного анализа клиентов"""
    date_from = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Начальная дата для фильтрации когорт (YYYY-MM-DD)'
    )
    date_to = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Конечная дата для фильтрации когорт (YYYY-MM-DD)'
    )
    period_type = serializers.ChoiceField(
        choices=['week', 'month'],
        default='month',
        help_text='Тип периодизации: week (неделя), month (месяц)'
    )


class CustomerCohortAnalysisResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа на запрос генерации когортного анализа"""
    task_id = serializers.CharField(help_text='ID Celery задачи для отслеживания статуса')
    status = serializers.CharField(help_text='Статус запроса')
    message = serializers.CharField(help_text='Сообщение о результате')


class RFMSegmentationRequestSerializer(serializers.Serializer):
    """Сериализатор для запроса на генерацию RFM-сегментации клиентов"""
    date_from = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Начальная дата для анализа транзакций (YYYY-MM-DD)'
    )
    date_to = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Конечная дата для анализа транзакций (YYYY-MM-DD)'
    )
    reference_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Референсная дата для расчета Recency (YYYY-MM-DD). По умолчанию - сегодня'
    )


class RFMSegmentationResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа на запрос генерации RFM-сегментации"""
    task_id = serializers.CharField(help_text='ID Celery задачи для отслеживания статуса')
    status = serializers.CharField(help_text='Статус запроса')
    message = serializers.CharField(help_text='Сообщение о результате')


class LTVAnalysisRequestSerializer(serializers.Serializer):
    """Сериализатор для запроса на генерацию LTV анализа"""
    date_from = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Начальная дата для анализа (YYYY-MM-DD)'
    )
    date_to = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Конечная дата для анализа (YYYY-MM-DD)'
    )


class LTVAnalysisResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа на запрос генерации LTV анализа"""
    task_id = serializers.CharField(help_text='ID Celery задачи для отслеживания статуса')
    status = serializers.CharField(help_text='Статус запроса')
    message = serializers.CharField(help_text='Сообщение о результате')


class MarketBasketAnalysisRequestSerializer(serializers.Serializer):
    """Сериализатор для запроса на генерацию Market Basket Analysis"""
    date_from = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Начальная дата для анализа (YYYY-MM-DD)'
    )
    date_to = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Конечная дата для анализа (YYYY-MM-DD)'
    )
    min_support = serializers.FloatField(
        required=False,
        default=0.005,
        min_value=0.001,
        max_value=1.0,
        help_text='Минимальная поддержка (0.005 = 0.5%), по умолчанию 0.005'
    )
    min_confidence = serializers.FloatField(
        required=False,
        default=0.1,
        min_value=0.01,
        max_value=1.0,
        help_text='Минимальная уверенность (0.1 = 10%), по умолчанию 0.1'
    )
    min_lift = serializers.FloatField(
        required=False,
        default=1.0,
        min_value=0.1,
        max_value=100.0,
        help_text='Минимальный lift, по умолчанию 1.0'
    )


class MarketBasketAnalysisResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа на запрос генерации Market Basket Analysis"""
    task_id = serializers.CharField(help_text='ID Celery задачи для отслеживания статуса')
    status = serializers.CharField(help_text='Статус запроса')
    message = serializers.CharField(help_text='Сообщение о результате')

