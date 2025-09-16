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
)
from goods.views import (
    ProductViewSet, ProductGroupViewSet, 
    ProductSubgroupViewSet, BrandViewSet,
    export_products_descriptions, check_export_task,
)
from rfqs.views import RFQViewSet, RFQItemViewSet, RFQItemFileViewSet, get_rfq_item_quotations, debug_rfq_items, upload_rfq_item_files, get_rfq_item_last_prices, create_quotation_for_rfq_item, QuotationItemFileViewSet, upload_quotation_item_files
from customers.views import CompanyViewSet
from persons.views import PersonViewSet

router = routers.DefaultRouter()
router.register("users", UserViewSet, basename="api-users")
router.register("products", ProductViewSet, basename="api-products")
router.register("product-groups", ProductGroupViewSet, basename="api-product-groups")
router.register("product-subgroups", ProductSubgroupViewSet, basename="api-product-subgroups")
router.register("brands", BrandViewSet, basename="api-brands")
router.register("rfqs", RFQViewSet, basename="api-rfqs")
router.register("rfq-items", RFQItemViewSet, basename="api-rfq-items")
router.register("rfq-item-files", RFQItemFileViewSet, basename="api-rfq-item-files")
router.register("quotation-item-files", QuotationItemFileViewSet, basename="api-quotation-item-files")
router.register("companies", CompanyViewSet, basename="api-companies")
router.register("persons", PersonViewSet, basename="api-persons")

urlpatterns = [
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
    ),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Custom endpoints должны идти ДО router.urls, чтобы избежать конфликтов
    path("api/debug/ping/", ping_post),
    path("api/products/export-descriptions/", export_products_descriptions, name="export-products-descriptions"),
    path("api/products/export-status/<str:task_id>/", check_export_task, name="check-export-task"),
    path("api/rfq-items/<int:rfq_item_id>/quotations/", get_rfq_item_quotations, name="rfq-item-quotations"),
    path("api/rfq-items/<int:rfq_item_id>/last-prices/", get_rfq_item_last_prices, name="rfq-item-last-prices"),
    path("api/rfq-items/<int:rfq_item_id>/create-quotation/", create_quotation_for_rfq_item, name="rfq-item-create-quotation"),
    path("api/rfq-items/<int:rfq_item_id>/files/", upload_rfq_item_files, name="rfq-item-files-upload"),
    path("api/quotation-items/<int:quotation_item_id>/files/", upload_quotation_item_files, name="quotation-item-files-upload"),
    path("api/debug/rfq-items/", debug_rfq_items, name="debug-rfq-items"),
    path("api/", include(router.urls)),
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
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)