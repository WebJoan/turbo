from django.contrib import admin

from .models import (
    Competitor,
    CompetitorProduct,
    CompetitorProductMatch,
    CompetitorPriceStockSnapshot,
    OurPriceHistory,
    CompetitorBrand,
    CompetitorCategory,
)


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display = ("name", "data_source_type", "data_url")
    search_fields = ("name",)
    list_filter = ("data_source_type",)


@admin.register(CompetitorBrand)
class CompetitorBrandAdmin(admin.ModelAdmin):
    list_display = ("competitor", "name", "ext_id")
    search_fields = ("competitor", "name", "ext_id")
    list_filter = ("competitor",)


@admin.register(CompetitorCategory)
class CompetitorCategoryAdmin(admin.ModelAdmin):
    list_display = ("competitor", "title", "ext_id")
    search_fields = ("competitor", "title", "ext_id")
    list_filter = ("competitor",)


@admin.register(CompetitorProduct)
class CompetitorProductAdmin(admin.ModelAdmin):
    list_display = ("competitor", "part_number", "mapped_product", "category")
    search_fields = ("part_number", "name", "ext_id")
    list_filter = ("competitor",)


@admin.register(CompetitorProductMatch)
class CompetitorProductMatchAdmin(admin.ModelAdmin):
    list_display = ("competitor_product", "product", "match_type", "confidence")
    list_filter = ("match_type", "competitor_product__competitor")
    search_fields = ("competitor_product__part_number", "product__name")


@admin.register(CompetitorPriceStockSnapshot)
class CompetitorPriceStockSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "competitor",
        "competitor_product",
        "collected_at",
        "price_ex_vat",
        "vat_rate",
        "stock_qty",
        "stock_status",
    )
    list_filter = ("competitor", "stock_status")
    date_hierarchy = "collected_at"


@admin.register(OurPriceHistory)
class OurPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("product", "moment", "price_ex_vat", "vat_rate")
    date_hierarchy = "moment"
    search_fields = ("product__name", "product__ext_id")

