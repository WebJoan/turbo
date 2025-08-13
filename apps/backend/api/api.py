from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from django.db.models import Q

from goods.models import Product, ProductGroup, ProductSubgroup, Brand
from customers.models import Company
from rfqs.models import RFQ, RFQItem
from .serializers import (
    # existing
    UserChangePasswordErrorSerializer,
    UserChangePasswordSerializer,
    UserCreateErrorSerializer,
    UserCreateSerializer,
    UserCurrentErrorSerializer,
    UserCurrentSerializer,
    ProductSerializer,
    ProductListSerializer,
    ProductGroupSerializer,
    ProductSubgroupSerializer,
    BrandSerializer,
    CompanySerializer,
    # new
    RFQSerializer,
    RFQItemSerializer,
    RFQCreateSerializer,
)
from .serializers import (
    UserChangePasswordErrorSerializer,
    UserChangePasswordSerializer,
    UserCreateErrorSerializer,
    UserCreateSerializer,
    UserCurrentErrorSerializer,
    UserCurrentSerializer,
    ProductSerializer,
    ProductListSerializer,
    ProductGroupSerializer,
    ProductSubgroupSerializer,
    BrandSerializer,
    CompanySerializer,
)

User = get_user_model()


class UserViewSet(
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.all()
    serializer_class = UserCurrentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(pk=self.request.user.pk)

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]

        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        elif self.action == "me":
            return UserCurrentSerializer
        elif self.action == "change_password":
            return UserChangePasswordSerializer

        return super().get_serializer_class()

    @extend_schema(
        responses={
            200: UserCreateSerializer,
            400: UserCreateErrorSerializer,
        }
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        responses={
            200: UserCurrentSerializer,
            400: UserCurrentErrorSerializer,
        }
    )
    @action(["get", "put", "patch"], detail=False)
    def me(self, request, *args, **kwargs):
        if request.method == "GET":
            serializer = self.get_serializer(self.request.user)
            return Response(serializer.data)
        elif request.method == "PUT":
            serializer = self.get_serializer(
                self.request.user, data=request.data, partial=False
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        elif request.method == "PATCH":
            serializer = self.get_serializer(
                self.request.user, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

    @extend_schema(
        responses={
            204: None,
            400: UserChangePasswordErrorSerializer,
        }
    )
    @action(["post"], url_path="change-password", detail=False)
    def change_password(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self.request.user.set_password(serializer.data["password_new"])
        self.request.user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["delete"], url_path="delete-account", detail=False)
    def delete_account(self, request, *args, **kwargs):
        self.request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
def ping_post(request):
    return Response({"ok": True}, status=status.HTTP_200_OK)


# Фильтры для товаров
class ProductFilter(FilterSet):
    ext_id = CharFilter(field_name="ext_id", lookup_expr="exact")
    ext_id_contains = CharFilter(field_name="ext_id", lookup_expr="icontains")
    name = CharFilter(field_name="name", lookup_expr="icontains")
    complex_name = CharFilter(field_name="complex_name", lookup_expr="icontains")
    brand_name = CharFilter(field_name="brand__name", lookup_expr="icontains")
    group_name = CharFilter(field_name="subgroup__group__name", lookup_expr="icontains")
    subgroup_name = CharFilter(field_name="subgroup__name", lookup_expr="icontains")
    manager_id = NumberFilter(method="filter_by_manager")
    search = CharFilter(method="filter_search")
    
    class Meta:
        model = Product
        fields = ["ext_id", "name", "brand_name", "group_name", "subgroup_name"]
    
    def filter_by_manager(self, queryset, name, value):
        """Фильтрация по назначенному менеджеру (учитывает иерархию)"""
        return queryset.filter(
            Q(product_manager_id=value) |
            Q(brand__product_manager_id=value) |
            Q(subgroup__product_manager_id=value)
        )
    
    def filter_search(self, queryset, name, value):
        """Общий поиск по ключевым полям"""
        return queryset.filter(
            Q(ext_id__icontains=value) |
            Q(name__icontains=value) |
            Q(complex_name__icontains=value) |
            Q(description__icontains=value) |
            Q(brand__name__icontains=value) |
            Q(subgroup__name__icontains=value) |
            Q(subgroup__group__name__icontains=value)
        )


# ViewSets для товаров
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.select_related(
        'brand', 'subgroup__group', 'product_manager',
        'brand__product_manager', 'subgroup__product_manager'
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["ext_id", "name", "complex_name", "description", "brand__name"]
    ordering_fields = ["name", "ext_id"]
    ordering = ["name"]
    
    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductSerializer
    
    @action(detail=False, methods=["get"])
    def by_ext_id(self, request):
        """Поиск товара по точному ext_id"""
        ext_id = request.query_params.get("ext_id")
        if not ext_id:
            return Response({"error": "Параметр ext_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product = self.get_queryset().get(ext_id=ext_id)
            serializer = ProductSerializer(product)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({"error": f"Товар с ext_id '{ext_id}' не найден"}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=["get"])
    def by_manager(self, request):
        """Получить товары по менеджеру"""
        manager_id = request.query_params.get("manager_id")
        if not manager_id:
            return Response({"error": "Параметр manager_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.filter_queryset(
            self.get_queryset().filter(
                Q(product_manager_id=manager_id) |
                Q(brand__product_manager_id=manager_id) |
                Q(subgroup__product_manager_id=manager_id)
            )
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(queryset, many=True)
        return Response(serializer.data)


class ProductGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductGroup.objects.all()
    serializer_class = ProductGroupSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "ext_id"]
    ordering = ["name"]


class ProductSubgroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductSubgroup.objects.select_related('group', 'product_manager').all()
    serializer_class = ProductSubgroupSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "ext_id", "group__name"]
    ordering = ["group__name", "name"]
    filterset_fields = ["group"]


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "short_name", "inn", "ext_id"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.select_related('product_manager').all()
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "ext_id"]
    ordering = ["name"]


# --- RFQ API ---

class RFQFilter(FilterSet):
    partnumber = CharFilter(method="filter_partnumber")
    brand = CharFilter(method="filter_brand")

    class Meta:
        model = RFQ
        fields = []

    def filter_partnumber(self, queryset, name, value):
        return queryset.filter(items__part_number__icontains=value).distinct()

    def filter_brand(self, queryset, name, value):
        return queryset.filter(items__manufacturer__icontains=value).distinct()


class RFQViewSet(viewsets.ModelViewSet):
    queryset = RFQ.objects.select_related("company", "sales_manager", "contact_person").prefetch_related("items")
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = RFQFilter
    search_fields = ["number", "title", "description", "company__name", "items__part_number", "items__manufacturer"]
    ordering_fields = ["created_at", "updated_at", "number"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve", "update", "partial_update"]:
            return RFQSerializer
        if self.action == "create":
            return RFQCreateSerializer
        return RFQSerializer

    @extend_schema(
        request=RFQCreateSerializer,
        responses={201: RFQSerializer}
    )
    def create(self, request, *args, **kwargs):
        """Создание RFQ с поддержкой как упрощенного, так и полного формата.

        Вариант А (упрощенный): partnumber, brand, qty, target_price (опц.), company_id (опц.), title/description (опц.)
        — создаёт черновик RFQ и одну строку RFQItem.

        Вариант Б (полный): items = [...], а также поля шапки RFQ
        — создаёт RFQ и строки согласно переданному массиву.
        """
        ser = RFQCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Определяем компанию: если не пришла, попробуем первую
        company = None
        company_id = data.get("company_id")
        if company_id:
            try:
                from customers.models import Company
                company = Company.objects.get(id=company_id)
            except Exception:
                pass
        if not company:
            from customers.models import Company
            company = Company.objects.order_by("id").first()
            if not company:
                return Response({"error": "Нет компаний для привязки RFQ. Создайте компанию и повторите."}, status=status.HTTP_400_BAD_REQUEST)

        # Поля шапки RFQ
        rfq_kwargs = {
            "company": company,
            "sales_manager": request.user if getattr(request.user, "is_authenticated", False) else None,
        }

        # Заголовок и описание
        title = data.get("title")
        description = data.get("description")

        # Контактное лицо, приоритет и прочие расширенные поля
        contact_person_id = data.get("contact_person_id")
        if contact_person_id:
            try:
                from persons.models import Person
                rfq_kwargs["contact_person"] = Person.objects.get(id=contact_person_id)
            except Exception:
                pass

        for optional_field in [
            "priority",
            "deadline",
            "delivery_address",
            "payment_terms",
            "delivery_terms",
            "notes",
        ]:
            if optional_field in data:
                rfq_kwargs[optional_field] = data.get(optional_field)

        # Если это упрощённый вариант и title не задан — соберём его из partnumber/brand
        if not title and all(k in data for k in ["partnumber", "brand"]):
            title = f"Запрос: {data['partnumber']} / {data['brand']}"

        rfq_kwargs["title"] = str(title or "RFQ").strip()[:200]
        if description is not None:
            rfq_kwargs["description"] = str(description)[:2000]

        # Создаём RFQ
        rfq = RFQ.objects.create(**rfq_kwargs)

        # Создание строк
        items = data.get("items") or []
        if items:
            from goods.models import Product
            next_line = 1
            used_line_numbers = set()
            for item in items:
                # line_number: если не задан — автоинкремент
                line_number = item.get("line_number") or next_line
                try:
                    line_number = int(line_number)
                except Exception:
                    line_number = next_line
                # Обеспечим уникальность line_number в рамках RFQ
                while line_number in used_line_numbers or line_number < 1:
                    line_number += 1

                product_obj = None
                product_id = item.get("product")
                if product_id:
                    try:
                        product_obj = Product.objects.get(id=product_id)
                    except Product.DoesNotExist:
                        product_obj = None

                is_new_product = item.get("is_new_product")
                if is_new_product is None:
                    is_new_product = product_obj is None

                RFQItem.objects.create(
                    rfq=rfq,
                    line_number=line_number,
                    product=product_obj,
                    product_name=str(item.get("product_name") or ""),
                    manufacturer=str(item.get("manufacturer") or ""),
                    part_number=str(item.get("part_number") or ""),
                    quantity=int(item.get("quantity")),
                    unit=str(item.get("unit") or "шт"),
                    specifications=str(item.get("specifications") or ""),
                    comments=str(item.get("comments") or ""),
                    is_new_product=bool(is_new_product),
                )
                used_line_numbers.add(line_number)
                next_line = max(next_line + 1, line_number + 1)
        else:
            # Упрощённый сценарий (одна строка)
            RFQItem.objects.create(
                rfq=rfq,
                line_number=1,
                product=None,
                product_name="",
                manufacturer=data["brand"],
                part_number=data["partnumber"],
                quantity=int(data["qty"]),
                unit="шт",
                specifications="",
                comments=(f"target_price={data['target_price']}" if data.get("target_price") is not None else ""),
                is_new_product=True,
            )

        out = RFQSerializer(rfq)
        headers = self.get_success_headers(out.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)
