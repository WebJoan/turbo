from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import User

admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    
    # Добавляем кастомные поля в список отображения
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'created_at')
    list_filter = BaseUserAdmin.list_filter + ('role', 'created_at')
    
    # Добавляем кастомные поля в форму редактирования
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Дополнительная информация', {
            'fields': ('role', 'old_db_name', 'created_at', 'modified_at')
        }),
    )
    
    # Делаем поля created_at и modified_at только для чтения
    readonly_fields = BaseUserAdmin.readonly_fields + ('created_at', 'modified_at')


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
