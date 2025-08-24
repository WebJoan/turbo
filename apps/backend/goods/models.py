from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from api.models import User
from core.mixins import ExtIdMixin
from django_softdelete.models import SoftDeleteModel
from django.conf import settings
import os


class ProductGroup(ExtIdMixin, models.Model):
    name = models.CharField(
        max_length=200, 
        verbose_name=_('Название группы')
    )

    class Meta:
        verbose_name = _('Группа товаров')
        verbose_name_plural = _('Группы товаров')

    def __str__(self):
        return self.name
    

class ProductSubgroup(ExtIdMixin, models.Model):
    group = models.ForeignKey(
        ProductGroup, 
        on_delete=models.CASCADE, 
        related_name='subgroups',
        verbose_name=_('Группа товаров')
    )
    name = models.CharField(
        max_length=200, 
        verbose_name=_('Название подгруппы')
    )
    # Подгруппа закреплена за конкретным product-менеджером
    product_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': User.Role.PURCHASER},
        related_name='product_subgroups',
        verbose_name=_('Ответственный менеджер'),
        help_text=_('Менеджер, отвечающий за данную подгруппу')
    )

    class Meta:
        verbose_name = _('Подгруппа товаров')
        verbose_name_plural = _('Подгруппы товаров')

    def __str__(self):
        return f"{self.group.name} - {self.name}"
    

class Brand(ExtIdMixin, models.Model):
    name = models.CharField(
        max_length=200, 
        verbose_name=_('Название бренда')
    )
    # Если за бренд закреплён конкретный менеджер:
    product_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': User.Role.PURCHASER},
        related_name='brands',
        verbose_name=_('Ответственный менеджер за бренд'),
        help_text=_('Менеджер, отвечающий за данный бренд')
    )

    class Meta:
        verbose_name = _('Бренд')
        verbose_name_plural = _('Бренды')

    def __str__(self):
        return self.name
    

class Product(SoftDeleteModel, ExtIdMixin):
    subgroup = models.ForeignKey(
        ProductSubgroup, 
        on_delete=models.CASCADE, 
        related_name='products',
        verbose_name=_('Подгруппа')
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name=_('Бренд')
    )
    name = models.CharField(
        max_length=200, 
        verbose_name=_('Part number')
    )
    # Переопределение менеджера для конкретного товара:
    product_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': User.Role.PURCHASER},
        related_name='products',
        verbose_name=_('Ответственный менеджер'),
        help_text=_('Если не указан, используется менеджер бренда или подгруппы')
    )
    
    # Технические параметры товара в формате JSON
    tech_params = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Технические параметры'),
        help_text=_('Технические характеристики товара в формате JSON')
    )
    complex_name = models.CharField(
        max_length=512,
        verbose_name=_('Комплексное наименование'),
        help_text=_('Комплексное наименование товара')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Описание'),
        help_text=_('Описание товара')
    )

    class Meta:
        verbose_name = _('Товар')
        verbose_name_plural = _('Товары')

    def __str__(self):
        return self.name

    def get_manager(self):
        """
        Определяет менеджера товара по следующему порядку приоритета:
        1. Если для товара явно указан менеджер, возвращает его.
        2. Если у товара есть бренд и для бренда назначен менеджер, возвращает его.
        3. Иначе возвращает менеджера подгруппы.
        """
        if self.product_manager:
            return self.product_manager
        if self.brand and self.brand.product_manager:
            return self.brand.product_manager
        return self.subgroup.product_manager


def file_blob_upload_path(instance, filename):
    sha = instance.sha256
    return f"files/{sha[:2]}/{sha[2:4]}/{sha}/{filename}"


class FileBlob(models.Model):
    sha256 = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_("SHA-256"),
        help_text=_("Уникальный хэш содержимого"),
    )

    file = models.FileField(
        upload_to=file_blob_upload_path,
        verbose_name=_("Файл"),
    )

    size = models.BigIntegerField(default=0, verbose_name=_("Размер, байт"))
    mime_type = models.CharField(max_length=100, blank=True, verbose_name=_("MIME"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Бинарный файл")
        verbose_name_plural = _("Бинарные файлы")

    def __str__(self):
        return f"{self.sha256} ({self.size} B)"


class ProductFile(models.Model):
    class FileType(models.TextChoices):
        DATASHEET = "datasheet", _("Даташит")
        DRAWING = "drawing", _("Чертеж")
        OTHER = "other", _("Другое")

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name=_("Товар"),
    )

    blob = models.ForeignKey(
        FileBlob,
        on_delete=models.PROTECT,
        related_name="product_files",
        verbose_name=_("Файл"),
    )

    file_type = models.CharField(
        max_length=20,
        choices=FileType.choices,
        default=FileType.OTHER,
        verbose_name=_("Тип файла"),
    )

    source_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_("Источник"),
        help_text=_("URL, откуда файл был скачан"),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Файл товара")
        verbose_name_plural = _("Файлы товара")
        indexes = [
            models.Index(fields=["product", "file_type"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["product", "file_type"], name="uniq_product_type"),
        ]

    def __str__(self):
        return f"{self.product_id}:{self.file_type}"