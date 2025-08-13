from django.contrib import admin
from django.urls import include, path
from dj_rest_auth.jwt_auth import get_refresh_view
from rest_framework_simplejwt.views import (
    TokenVerifyView,
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework import routers
from django.conf import settings
from django.conf.urls.static import static

from .api import (
    UserViewSet, ping_post,
    ProductViewSet, ProductGroupViewSet, 
    ProductSubgroupViewSet, BrandViewSet, RFQViewSet
)

router = routers.DefaultRouter()
router.register("users", UserViewSet, basename="api-users")
router.register("products", ProductViewSet, basename="api-products")
router.register("product-groups", ProductGroupViewSet, basename="api-product-groups")
router.register("product-subgroups", ProductSubgroupViewSet, basename="api-product-subgroups")
router.register("brands", BrandViewSet, basename="api-brands")
router.register("rfqs", RFQViewSet, basename="api-rfqs")

urlpatterns = [
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
    ),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/", include(router.urls)),
    path("api/debug/ping/", ping_post),
    # dj-rest-auth endpoints
    path("api/auth/", include("dj_rest_auth.urls")),
    # JWT helpers
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    # используем уникальное имя, чтобы не конфликтовать с dj-rest-auth refresh
    path("api/token/refresh/", TokenRefreshView.as_view(), name="jwt_token_refresh"),
    path("api/auth/token/refresh/", get_refresh_view().as_view(), name="token_refresh"),
    path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/auth/token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),
    path("admin/", admin.site.urls),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)