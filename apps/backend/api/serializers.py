from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers

from goods.models import Product, ProductGroup, ProductSubgroup, Brand
from rfqs.models import RFQ, RFQItem
from customers.models import Company


User = get_user_model()


class UserCurrentSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name"]


class UserCurrentErrorSerializer(serializers.Serializer):
    username = serializers.ListSerializer(child=serializers.CharField(), required=False)
    first_name = serializers.ListSerializer(
        child=serializers.CharField(), required=False
    )
    last_name = serializers.ListSerializer(
        child=serializers.CharField(), required=False
    )


class UserChangePasswordSerializer(serializers.ModelSerializer):
    password = serializers.CharField(style={"input_type": "password"}, write_only=True)
    password_new = serializers.CharField(style={"input_type": "password"})
    password_retype = serializers.CharField(
        style={"input_type": "password"}, write_only=True
    )

    default_error_messages = {
        "password_mismatch": _("Current password is not matching"),
        "password_invalid": _("Password does not meet all requirements"),
        "password_same": _("Both new and current passwords are same"),
    }

    class Meta:
        model = User
        fields = ["password", "password_new", "password_retype"]

    def validate(self, attrs):
        request = self.context.get("request", None)

        if not request.user.check_password(attrs["password"]):
            raise serializers.ValidationError(
                {"password": self.default_error_messages["password_mismatch"]}
            )

        try:
            validate_password(attrs["password_new"])
        except ValidationError as e:
            raise exceptions.ValidationError({"password_new": list(e.messages)}) from e

        if attrs["password_new"] != attrs["password_retype"]:
            raise serializers.ValidationError(
                {"password_retype": self.default_error_messages["password_invalid"]}
            )

        if attrs["password_new"] == attrs["password"]:
            raise serializers.ValidationError(
                {"password_new": self.default_error_messages["password_same"]}
            )
        return super().validate(attrs)


class UserChangePasswordErrorSerializer(serializers.Serializer):
    password = serializers.ListSerializer(child=serializers.CharField(), required=False)
    password_new = serializers.ListSerializer(
        child=serializers.CharField(), required=False
    )
    password_retype = serializers.ListSerializer(
        child=serializers.CharField(), required=False
    )


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(style={"input_type": "password"}, write_only=True)
    password_retype = serializers.CharField(
        style={"input_type": "password"}, write_only=True
    )

    default_error_messages = {
        "password_mismatch": _("Password are not matching."),
        "password_invalid": _("Password does not meet all requirements."),
    }

    class Meta:
        model = User
        fields = ["username", "password", "password_retype"]

    def validate(self, attrs):
        password_retype = attrs.pop("password_retype")

        try:
            validate_password(attrs.get("password"))
        except exceptions.ValidationError:
            self.fail("password_invalid")

        if attrs["password"] == password_retype:
            return attrs

        return self.fail("password_mismatch")

    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(**validated_data)

            # By default newly registered accounts are inactive.
            user.is_active = False
            user.save(update_fields=["is_active"])

        return user


class UserCreateErrorSerializer(serializers.Serializer):
    username = serializers.ListSerializer(child=serializers.CharField(), required=False)
    password = serializers.ListSerializer(child=serializers.CharField(), required=False)
    password_retype = serializers.ListSerializer(
        child=serializers.CharField(), required=False
    )


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "ext_id",
            "name",
            "short_name",
            "inn",
        ]


class UserDetailsSerializer(serializers.ModelSerializer):
    """
    Serializer для dj-rest-auth для работы с данными пользователя
    """
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "is_staff"]
        read_only_fields = ["id", "is_staff"]


class UserInfoSerializer(serializers.ModelSerializer):
    """
    Serializer для получения полной информации о пользователе включая old_db_name
    """
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role", "old_db_name", "created_at", "modified_at"]
        read_only_fields = ["id", "created_at", "modified_at"]


# Serializers для товаров
class ProductGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductGroup
        fields = ["id", "ext_id", "name"]


class ProductSubgroupSerializer(serializers.ModelSerializer):
    group = ProductGroupSerializer(read_only=True)
    product_manager = UserCurrentSerializer(read_only=True)
    
    class Meta:
        model = ProductSubgroup
        fields = ["id", "ext_id", "name", "group", "product_manager"]


class BrandSerializer(serializers.ModelSerializer):
    product_manager = UserCurrentSerializer(read_only=True)
    
    class Meta:
        model = Brand
        fields = ["id", "ext_id", "name", "product_manager"]


class ProductSerializer(serializers.ModelSerializer):
    subgroup = ProductSubgroupSerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    product_manager = UserCurrentSerializer(read_only=True)
    assigned_manager = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            "id", "ext_id", "name", "complex_name", "description", 
            "subgroup", "brand", "product_manager", "assigned_manager",
            "tech_params"
        ]
        
    def get_assigned_manager(self, obj):
        """Получает назначенного менеджера товара согласно логике get_manager()"""
        manager = obj.get_manager()
        if manager:
            return UserCurrentSerializer(manager).data
        return None


class ProductListSerializer(serializers.ModelSerializer):
    """Упрощенный serializer для списка товаров"""
    subgroup_name = serializers.CharField(source="subgroup.name", read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True)
    group_name = serializers.CharField(source="subgroup.group.name", read_only=True)
    assigned_manager = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            "id", "ext_id", "name", "complex_name",
            "group_name", "subgroup_name", "brand_name", 
            "assigned_manager"
        ]
        
    def get_assigned_manager(self, obj):
        """Получает назначенного менеджера товара"""
        manager = obj.get_manager()
        if manager:
            return {
                "id": manager.id,
                "username": manager.username,
                "first_name": manager.first_name,
                "last_name": manager.last_name
            }
        return None


# --- RFQ Serializers ---

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

