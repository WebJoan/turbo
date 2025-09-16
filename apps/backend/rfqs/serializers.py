from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers

from rfqs.models import RFQ, RFQItem, Quotation, QuotationItem, RFQItemFile, QuotationItemFile
class RFQItemFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RFQItemFile
        fields = [
            "id",
            "file",
            "file_type",
            "description",
            "uploaded_at",
        ]



class QuotationItemFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationItemFile
        fields = [
            "id",
            "file",
            "file_type",
            "description",
            "uploaded_at",
        ]


class RFQItemSerializer(serializers.ModelSerializer):
    files = RFQItemFileSerializer(many=True, read_only=True)
    # ID товара из базы (внешний идентификатор Product.ext_id)
    product_ext_id = serializers.CharField(source="product.ext_id", read_only=True)
    # Полный объект выбранного товара для предзаполнения селекта на фронте
    product_display = serializers.SerializerMethodField(read_only=True)
    # Флаг наличия хотя бы одного предложения по данной строке RFQ
    has_quotations = serializers.SerializerMethodField(read_only=True)
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Если строка связана с товаром из базы, возвращаем краткое имя (part number)
        # вместо возможного длинного свободного текста
        try:
            if instance.product_id and instance.product:
                data["product_name"] = instance.product.name
        except Exception:
            # В случае любых проблем с доступом к связанному объекту, оставляем исходное значение
            pass
        return data

    def get_product_display(self, instance):
        try:
            if instance.product_id and instance.product:
                return {
                    "id": instance.product.id,
                    "ext_id": getattr(instance.product, "ext_id", None),
                    "name": getattr(instance.product, "name", None),
                }
        except Exception:
            pass
        return None

    def get_has_quotations(self, instance):
        """Возвращает True, если по строке RFQ есть хотя бы один QuotationItem.

        Использует предзагруженные данные, если они есть, иначе выполняет exists().
        """
        try:
            prefetched = getattr(instance, "_prefetched_objects_cache", {})
            if isinstance(prefetched, dict) and "quotation_items" in prefetched:
                return len(prefetched["quotation_items"]) > 0
            # fallback на exists()
            return instance.quotation_items.exists()
        except Exception:
            return False

    class Meta:
        model = RFQItem
        fields = [
            "id",
            "line_number",
            "product",
            "product_ext_id",
            "product_display",
            "product_name",
            "manufacturer",
            "part_number",
            "quantity",
            "unit",
            "specifications",
            "comments",
            "is_new_product",
            "has_quotations",
            "files",
        ]


class RFQItemWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания/обновления строк RFQ.

    Допускает передачу полей напрямую. Поле files не поддерживается здесь
    (файлы загружаются через отдельный endpoint /api/rfq-items/<id>/files/).
    """

    class Meta:
        model = RFQItem
        fields = [
            "id",
            "rfq",
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

    def validate(self, attrs):
        # Обеспечиваем единицу измерения по умолчанию
        if not attrs.get("unit"):
            attrs["unit"] = "шт"

        # Если не передан product, то позиция считается новой (если явно не указано иначе)
        if attrs.get("product") is None and "is_new_product" not in attrs:
            attrs["is_new_product"] = True

        return super().validate(attrs)

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
    # Файлы приходят отдельным multipart-запросом; поле оставляем для совместимости фронта, но игнорируем
    files = serializers.ListField(child=serializers.FileField(), required=False, write_only=True)

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


class QuotationItemSerializer(serializers.ModelSerializer):
    """Сериализатор для строк предложения"""
    product_name = serializers.CharField(source="product.name", read_only=True)
    proposed_product_name = serializers.CharField(read_only=True)
    total_price = serializers.DecimalField(max_digits=15, decimal_places=4, read_only=True)
    files = QuotationItemFileSerializer(many=True, read_only=True)
    
    class Meta:
        model = QuotationItem
        fields = [
            "id",
            "product",
            "product_name", 
            "proposed_product_name",
            "proposed_manufacturer",
            "proposed_part_number",
            "quantity",
            "unit_cost_price",
            "cost_markup_percent",
            "unit_price",
            "total_price",
            "delivery_time",
            "notes",
            "files",
        ]

class QuotationSerializer(serializers.ModelSerializer):
    """Сериализатор для предложений"""
    product_manager_username = serializers.CharField(source="product_manager.username", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    currency_symbol = serializers.CharField(source="currency.symbol", read_only=True)
    items = QuotationItemSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=4, read_only=True)
    
    class Meta:
        model = Quotation
        fields = [
            "id",
            "number",
            "title",
            "product_manager",
            "product_manager_username",
            "status",
            "currency",
            "currency_code",
            "currency_symbol",
            "description",
            "valid_until",
            "delivery_time",
            "payment_terms", 
            "delivery_terms",
            "notes",
            "total_amount",
            "created_at",
            "updated_at",
            "items"
        ]


class RFQSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    sales_manager_username = serializers.CharField(source="sales_manager.username", read_only=True)
    items = RFQItemSerializer(many=True, read_only=True)
    quotations_count = serializers.SerializerMethodField()

    def get_quotations_count(self, obj):
        count = getattr(obj, "quotations_count", None)
        if count is not None:
            return count
        # Fallback, если не было аннотации
        try:
            return obj.quotations.count()
        except Exception:
            return 0

    class Meta:
        model = RFQ
        fields = [
            "id",
            "number",
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
            "quotations_count",
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

