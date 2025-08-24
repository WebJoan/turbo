from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers

from rfqs.models import RFQ, RFQItem


class RFQItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RFQItem
        fields = [
            "id",
            "line_number",
            "product",
            "product_name",
            "manufacturer",
            "part_number",
            "quantity",
            "unit",
            "specifications",
            "comments",
            "is_new_product",
        ]

class RFQItemCreateSerializer(serializers.Serializer):
    """Валидация данных для создания строк RFQ."""
    product = serializers.IntegerField(required=False)
    product_name = serializers.CharField(required=False, allow_blank=True)
    manufacturer = serializers.CharField(required=False, allow_blank=True)
    part_number = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1)
    unit = serializers.CharField(required=False, allow_blank=True, default="шт")
    specifications = serializers.CharField(required=False, allow_blank=True)
    comments = serializers.CharField(required=False, allow_blank=True)
    is_new_product = serializers.BooleanField(required=False)
    line_number = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        # Должен быть либо product (id), либо хотя бы один из свободных полей о товаре
        has_free_text = any([
            bool(attrs.get("product_name")),
            bool(attrs.get("manufacturer")),
            bool(attrs.get("part_number")),
        ])
        if not attrs.get("product") and not has_free_text:
            raise serializers.ValidationError(
                "Укажите product (ID существующего товара) или заполните хотя бы одно из полей: product_name/manufacturer/part_number"
            )
        return super().validate(attrs)


class RFQSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    sales_manager_username = serializers.CharField(source="sales_manager.username", read_only=True)
    items = RFQItemSerializer(many=True, read_only=True)

    class Meta:
        model = RFQ
        fields = [
            "id",
            "number",
            "title",
            "company",
            "company_name",
            "contact_person",
            "sales_manager",
            "sales_manager_username",
            "status",
            "priority",
            "description",
            "deadline",
            "delivery_address",
            "payment_terms",
            "delivery_terms",
            "notes",
            "created_at",
            "updated_at",
            "items",
        ]
        read_only_fields = [
            "number",
            "created_at",
            "updated_at",
        ]

class RFQCreateSerializer(serializers.Serializer):
    # Вариант 1 (упрощенный): partnumber/brand/qty(+target_price)
    partnumber = serializers.CharField(required=False)
    brand = serializers.CharField(required=False)
    qty = serializers.IntegerField(min_value=1, required=False)
    target_price = serializers.FloatField(required=False, allow_null=True)
    # Вариант 2 (полный): items[]
    items = serializers.ListSerializer(child=RFQItemCreateSerializer(), required=False)
    # Шапка RFQ
    company_id = serializers.IntegerField(required=False)
    title = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=RFQ.PriorityChoices.choices, required=False)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    delivery_address = serializers.CharField(required=False, allow_blank=True)
    payment_terms = serializers.CharField(required=False, allow_blank=True)
    delivery_terms = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    contact_person_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        # Должен быть либо набор (partnumber, brand, qty), либо items[]
        has_simple = all(k in attrs and attrs.get(k) not in [None, ""] for k in ["partnumber", "brand", "qty"])
        has_items = bool(attrs.get("items"))
        if not has_simple and not has_items:
            raise serializers.ValidationError(
                "Передайте либо поля partnumber, brand, qty, либо список items с позициями RFQ"
            )
        return super().validate(attrs)

