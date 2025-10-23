from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Person


@admin.register(Person)
class PersonAdmin(ModelAdmin):
    list_display = (
        'last_name',
        'first_name',
        'middle_name',
        'company',
        'email',
        'phone',
        'status',
        'is_primary_contact',
        'created_at',
    )
    list_filter = ('status', 'is_primary_contact', 'company')
    search_fields = (
        'last_name',
        'first_name',
        'middle_name',
        'email',
        'phone',
        'company__name',
        'company__short_name',
        'ext_id',
    )
    autocomplete_fields = ('company',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('company', 'last_name', 'first_name')
    list_select_related = ('company',)
    date_hierarchy = 'created_at'
