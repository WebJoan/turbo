from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from api.serializers import UserCurrentSerializer

from .models import (
    Competitor,
    CompetitorProduct,
    CompetitorProductMatch,
    CompetitorPriceStockSnapshot,
    OurPriceHistory,
)

User = get_user_model()


class CompetitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competitor
        fields = [
            "id", "name", "site_url", "b2b_site_url", "is_active",
            "created_at", "updated_at"
        ]


class CompetitorProductSerializer(serializers.ModelSerializer):
    competitor = CompetitorSerializer(read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True)
    brand_id = serializers.IntegerField(source="brand.id", read_only=True)
    mapped_product_name = serializers.CharField(
        source="mapped_product.name", read_only=True
    )

    class Meta:
        model = CompetitorProduct
        fields = [
            "id", "competitor", "ext_id", "part_number", "brand_id", "brand_name",
            "name", "tech_params", "mapped_product", "mapped_product_name",
            "created_at", "updated_at"
        ]


class CompetitorProductMatchSerializer(serializers.ModelSerializer):
    competitor_product = CompetitorProductSerializer(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_ext_id = serializers.CharField(source="product.ext_id", read_only=True)

    class Meta:
        model = CompetitorProductMatch
        fields = [
            "id", "competitor_product", "product", "product_name", "product_ext_id",
            "match_type", "confidence", "notes", "created_at", "updated_at"
        ]


class CompetitorProductMatchCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetitorProductMatch
        fields = [
            "competitor_product", "product", "match_type", "confidence", "notes"
        ]


class CompetitorPriceStockSnapshotSerializer(serializers.ModelSerializer):
    competitor = CompetitorSerializer(read_only=True)
    competitor_product = CompetitorProductSerializer(read_only=True)
    competitor_name = serializers.CharField(source="competitor.name", read_only=True)
    product_part_number = serializers.CharField(
        source="competitor_product.part_number", read_only=True
    )

    class Meta:
        model = CompetitorPriceStockSnapshot
        fields = [
            "id", "competitor", "competitor_product", "competitor_name",
            "product_part_number", "collected_at", "price_ex_vat", "price_inc_vat", "vat_rate",
            "currency", "stock_qty", "stock_status", "delivery_days_min",
            "delivery_days_max", "raw_payload", "created_at", "updated_at"
        ]


class CompetitorPriceStockSnapshotCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания снимка цены/склада"""

    class Meta:
        model = CompetitorPriceStockSnapshot
        fields = [
            "competitor", "competitor_product", "collected_at", "price_ex_vat", "price_inc_vat",
            "vat_rate", "currency", "stock_qty", "stock_status", "delivery_days_min",
            "delivery_days_max", "raw_payload"
        ]


class OurPriceHistorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_ext_id = serializers.CharField(source="product.ext_id", read_only=True)

    class Meta:
        model = OurPriceHistory
        fields = [
            "id", "product", "product_name", "product_ext_id", "moment",
            "price_ex_vat", "vat_rate", "price_inc_vat", "created_at", "updated_at"
        ]


class PriceComparisonSerializer(serializers.Serializer):
    """Сериализатор для сравнения цен"""
    our_product_id = serializers.IntegerField()
    our_product_name = serializers.CharField(read_only=True)
    our_current_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    our_price_history = OurPriceHistorySerializer(many=True, read_only=True)
    competitor_prices = CompetitorPriceStockSnapshotSerializer(many=True, read_only=True)
    matches = CompetitorProductMatchSerializer(many=True, read_only=True)
