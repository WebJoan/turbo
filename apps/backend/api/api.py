from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from django.db.models import Q

from goods.models import Product, ProductGroup, ProductSubgroup, Brand
from goods.indexers import ProductIndexer
from django.conf import settings
from customers.models import Company
from rfqs.models import RFQ, RFQItem
from goods.tasks import export_products_by_typecode, export_products_by_filters
from celery.result import AsyncResult
import base64
import logging
from django.http import HttpResponse

logger = logging.getLogger(__name__)
from .serializers import (
    # existing
    UserChangePasswordErrorSerializer,
    UserChangePasswordSerializer,
    UserCreateErrorSerializer,
    UserCreateSerializer,
    UserCurrentErrorSerializer,
    UserCurrentSerializer,
    UserInfoSerializer,
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

    @extend_schema(
        responses={
            200: UserInfoSerializer,
            404: {"description": "Пользователь не найден"},
        }
    )
    @action(["get"], detail=True, url_path="info")
    def get_user_info(self, request, pk=None, *args, **kwargs):
        """Получить информацию о пользователе по ID, включая old_db_name."""
        try:
            user = User.objects.get(pk=pk)
            serializer = UserInfoSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {"detail": f"Пользователь с ID {pk} не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(["delete"], url_path="delete-account", detail=False)
    def delete_account(self, request, *args, **kwargs):
        self.request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
def ping_post(request):
    return Response({"ok": True}, status=status.HTTP_200_OK)
