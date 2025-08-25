from django.contrib import admin
from .models import Company
from persons.models import Person


class PersonInline(admin.TabularInline):
    model = Person
    extra = 0
    fields = (
        'last_name',
        'first_name',
        'middle_name',
        'email',
        'phone',
        'status',
        'is_primary_contact',
    )
    show_change_link = True


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'short_name',
        'company_type',
        'status',
        'email',
        'phone',
        'sales_manager',
        'created_at',
    )
    list_filter = ('company_type', 'status')
    search_fields = (
        'name',
        'short_name',
        'inn',
        'ogrn',
        'email',
        'phone',
        'ext_id',
    )
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('name',)
    inlines = [PersonInline]
    raw_id_fields = ('sales_manager',)
