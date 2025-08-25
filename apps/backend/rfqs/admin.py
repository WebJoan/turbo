from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    RFQ,
    RFQItem,
    RFQItemFile,
    Quotation,
    QuotationItem,
    Currency,
)


class RFQItemInline(admin.TabularInline):
    model = RFQItem
    extra = 0
    fields = (
        'line_number',
        'product',
        'product_name',
        'manufacturer',
        'part_number',
        'quantity',
        'unit',
        'is_new_product',
        'created_at',
        'updated_at',
    )
    readonly_fields = ('created_at', 'updated_at')


class QuotationInline(admin.TabularInline):
    model = Quotation
    extra = 0
    fields = (
        'number',
        'product_manager',
        'status',
        'title',
        'currency',
        'valid_until',
        'created_at',
        'updated_at',
    )
    readonly_fields = ('number', 'created_at', 'updated_at')


@admin.register(RFQ)
class RFQAdmin(ModelAdmin):
    list_display = (
        'number',
        'company',
        'contact_person',
        'sales_manager',
        'status',
        'priority',
        'created_at',
        'items_count',
        'quotations_count',
    )
    list_filter = (
        'status',
        'priority',
        'company',
        'sales_manager',
        'created_at',
    )
    search_fields = (
        'number',
        'description',
        'company__name',
        'contact_person__first_name',
        'contact_person__last_name',
    )
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [RFQItemInline, QuotationInline]

    fieldsets = (
        ('Основная информация', {'fields': ('number', 'description')}),
        ('Связи', {'fields': ('company', 'contact_person', 'sales_manager')}),
        (
            'Условия',
            {
                'fields': (
                    'status',
                    'priority',
                    'deadline',
                    'delivery_address',
                    'payment_terms',
                    'delivery_terms',
                )
            },
        ),
        (
            'Системная информация',
            {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)},
        ),
    )

    def items_count(self, obj):
        return obj.items.count()

    items_count.short_description = 'Строк'

    def quotations_count(self, obj):
        return obj.quotations.count()

    quotations_count.short_description = 'Предложений'


@admin.register(Currency)
class CurrencyAdmin(ModelAdmin):
    list_display = (
        'code',
        'name',
        'symbol',
        'exchange_rate_to_rub',
        'is_active',
        'updated_at',
    )
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'symbol')


class RFQItemFileInline(admin.TabularInline):
    model = RFQItemFile
    extra = 0
    fields = ('file', 'file_type', 'description', 'uploaded_at')
    readonly_fields = ('uploaded_at', 'file_type')


@admin.register(RFQItem)
class RFQItemAdmin(ModelAdmin):
    list_display = (
        'rfq',
        'line_number',
        'product',
        'product_name',
        'manufacturer',
        'part_number',
        'quantity',
        'unit',
        'is_new_product',
        'created_at',
        'updated_at',
    )
    list_filter = ('rfq', 'is_new_product', 'product')
    search_fields = (
        'rfq__number',
        'product__name',
        'product_name',
        'manufacturer',
        'part_number',
    )
    readonly_fields = ('created_at', 'updated_at')
    inlines = [RFQItemFileInline]


@admin.register(RFQItemFile)
class RFQItemFileAdmin(ModelAdmin):
    list_display = ('rfq_item', 'file', 'file_type', 'description', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at')
    search_fields = ('rfq_item__rfq__number', 'description')


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 0
    fields = (
        'rfq_item',
        'product',
        'proposed_product_name',
        'proposed_manufacturer',
        'proposed_part_number',
        'quantity',
        'unit_cost_price',
        'cost_markup_percent',
        'unit_price',
        'delivery_time',
        'notes',
    )


@admin.register(Quotation)
class QuotationAdmin(ModelAdmin):
    list_display = (
        'number',
        'rfq',
        'product_manager',
        'status',
        'title',
        'currency',
        'get_total_amount',
        'created_at',
    )
    list_filter = ('status', 'product_manager', 'currency', 'created_at')
    search_fields = ('number', 'title', 'rfq__number')
    readonly_fields = ('created_at', 'updated_at', 'number')
    inlines = [QuotationItemInline]

    fieldsets = (
        ('Основная информация', {'fields': ('number', 'rfq', 'title', 'description')}),
        (
            'Параметры',
            {
                'fields': (
                    'product_manager',
                    'status',
                    'currency',
                    'valid_until',
                    'delivery_time',
                    'payment_terms',
                    'delivery_terms',
                )
            },
        ),
        (
            'Системная информация',
            {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)},
        ),
    )

    def get_total_amount(self, obj):
        return obj.total_amount

    get_total_amount.short_description = 'Сумма предложения'


@admin.register(QuotationItem)
class QuotationItemAdmin(ModelAdmin):
    list_display = (
        'quotation',
        'rfq_item',
        'product',
        'proposed_product_name',
        'quantity',
        'unit_cost_price',
        'cost_markup_percent',
        'unit_price',
        'total_price',
    )
    list_filter = ('quotation',)
    search_fields = (
        'quotation__number',
        'rfq_item__rfq__number',
        'proposed_product_name',
        'product__name',
    )

