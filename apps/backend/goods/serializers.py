from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers
from api.serializers import UserCurrentSerializer

from goods.models import Product, ProductGroup, ProductSubgroup, Brand


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
