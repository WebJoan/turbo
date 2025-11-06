from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Invoice, InvoiceLine

class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    fields = ('product', 'quantity', 'price')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'

@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = ('invoice_number', 'invoice_date', 'company', 'invoice_type', 'sale_type', 'currency')
    list_filter = ('invoice_type', 'sale_type', 'currency')
    search_fields = ('invoice_number', 'company__name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [InvoiceLineInline]


@admin.register(InvoiceLine)
class InvoiceLineAdmin(ModelAdmin):
    list_display = ('invoice', 'product', 'quantity', 'price')
    list_filter = ('invoice', 'product')
    search_fields = ('invoice__invoice_number', 'product__name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'