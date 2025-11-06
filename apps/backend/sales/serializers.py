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

