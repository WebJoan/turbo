from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import ProductGroup, ProductSubgroup, Brand, Product, FileBlob, ProductFile


class ProductSubgroupInline(admin.TabularInline):
    model = ProductSubgroup
    extra = 0
    fields = ('name', 'product_manager')


class ProductInline(admin.TabularInline):
    model = Product
    extra = 0
    fields = ('name', 'brand', 'product_manager')
    readonly_fields = ('ext_id',)


@admin.register(ProductGroup)
class ProductGroupAdmin(ModelAdmin):
    list_display = ('name', 'ext_id', 'subgroup_count')
    search_fields = ('name',)
    readonly_fields = ('ext_id',)
    inlines = [ProductSubgroupInline]
    
    def subgroup_count(self, obj):
        return obj.subgroups.count()
    subgroup_count.short_description = 'Количество подгрупп'


@admin.register(ProductSubgroup)
class ProductSubgroupAdmin(ModelAdmin):
    list_display = ('name', 'group', 'product_manager', 'product_count', 'ext_id')
    list_filter = ('group', 'product_manager')
    search_fields = ('name', 'group__name')
    readonly_fields = ('ext_id',)
    inlines = [ProductInline]
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Количество товаров'


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ('name', 'product_manager', 'product_count', 'ext_id')
    list_filter = ('product_manager',)
    search_fields = ('name',)
    readonly_fields = ('ext_id',)
    inlines = [ProductInline]
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Количество товаров'


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ('name', 'subgroup', 'brand', 'get_assigned_manager', 'complex_name', 'deleted_at', 'ext_id')
    list_filter = ('subgroup__group', 'subgroup', 'brand', 'product_manager', 'deleted_at')
    search_fields = ('name', 'complex_name', 'description')
    readonly_fields = ('ext_id', 'deleted_at')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'complex_name', 'description', 'ext_id')
        }),
        ('Категоризация', {
            'fields': ('subgroup', 'brand')
        }),
        ('Менеджмент', {
            'fields': ('product_manager',),
            'description': 'Если не указан, используется менеджер бренда или подгруппы'
        }),
        ('Технические характеристики', {
            'fields': ('tech_params',),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('deleted_at',),
            'classes': ('collapse',)
        })
    )
    
    def get_assigned_manager(self, obj):
        manager = obj.get_manager()
        return manager.get_full_name() if manager else 'Не назначен'
    get_assigned_manager.short_description = 'Ответственный менеджер'
    
    actions = ['restore_deleted']
    
    def restore_deleted(self, request, queryset):
        count = 0
        for obj in queryset:
            if obj.deleted_at:
                obj.restore()
                count += 1
        self.message_user(request, f'Восстановлено товаров: {count}')
    restore_deleted.short_description = 'Восстановить удалённые товары'


@admin.register(FileBlob)
class FileBlobAdmin(ModelAdmin):
    list_display = ('sha256', 'size', 'mime_type', 'created_at')
    search_fields = ('sha256', 'mime_type')


@admin.register(ProductFile)
class ProductFileAdmin(ModelAdmin):
    list_display = ('product', 'file_type', 'blob', 'created_at')
    list_filter = ('file_type',)
    search_fields = ('product__name', 'product__ext_id', 'source_url')
