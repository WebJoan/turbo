from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from core.mixins import TimestampsMixin


class Competitor(TimestampsMixin, models.Model):
    class DataSourceType(models.TextChoices):
         FTP_CSV = 'ftp', _("FTP")
         HTTPS = 'https', _("HTTPS")
    data_source_type = models.CharField(
         max_length=20,
         choices=DataSourceType.choices,
         blank=True,
         null=True,
         verbose_name=_("Тип источника данных"),
         help_text=_("Как получаем данные от конкурента")
    )
    data_url = models.CharField(
         max_length=500,
         blank=True,
         verbose_name=_("URL или хост"),
         help_text=_("Для FTP: хост (напр. ftp.example.com); для HTTPS: ссылка на файл")
    )
    username = models.CharField(
         max_length=200,
         blank=True,
         verbose_name=_("Логин")
    )
    password = models.CharField(
         max_length=200,
         blank=True,
         verbose_name=_("Пароль")
    )
    name = models.CharField(max_length=200, verbose_name=_("Название"))

    class Meta:
        verbose_name = _("Конкурент")
        verbose_name_plural = _("Конкуренты")

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name}"


class CompetitorBrand(TimestampsMixin, models.Model):
    competitor = models.ForeignKey(
        Competitor,
        on_delete=models.CASCADE,
        related_name="brands",
        verbose_name=_("Конкурент"),
    )
    name = models.CharField(max_length=200, verbose_name=_("Бренд"))
    ext_id = models.CharField(max_length=100, blank=True, verbose_name=_("Внешний ID у конкурента"))
    is_active = models.BooleanField(default=True, verbose_name=_("Активен"))
    
    class Meta:
        verbose_name = _("Бренд конкурента")
        verbose_name_plural = _("Бренды конкурентов")
        indexes = [
            models.Index(fields=["competitor", "name"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["competitor", "name"], name="uniq_competitor_brand")
        ]
    
    def __str__(self) -> str:  # pragma: no cover
        return f"{self.competitor.name}:{self.name}"


class CompetitorCategory(TimestampsMixin, models.Model):
    competitor = models.ForeignKey(
        "Competitor",
        on_delete=models.CASCADE,
        related_name="categories",
        verbose_name=_("Конкурент"),
    )
    # внешний ID узла у конкурента
    ext_id = models.CharField(max_length=50, verbose_name=_("Внешний ID"))
    title = models.CharField(max_length=255, verbose_name=_("Название"))
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
        verbose_name=_("Родитель"),
    )
    level = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name=_("Уровень"))

    class Meta:
        verbose_name = _("Категория конкурента")
        verbose_name_plural = _("Категории конкурентов")
        indexes = [
            models.Index(fields=["competitor", "ext_id"]),
            models.Index(fields=["competitor", "parent", "title"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["competitor", "ext_id"], name="uniq_competitor_category_ext"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.competitor.name}:{self.title} ({self.ext_id})"


class CompetitorProduct(TimestampsMixin, models.Model):
    competitor = models.ForeignKey(
        Competitor,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name=_("Конкурент"),
    )
    ext_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Внешний ID у конкурента"),
        help_text=_("Идентификатор позиции у источника"),
    )
    part_number = models.CharField(
        max_length=512,
        verbose_name=_("Part number / SKU"),
        help_text=_("Обозначение позиции у конкурента"),
    )
    brand = models.ForeignKey(
        CompetitorBrand,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name=_("Бренд"),
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        CompetitorCategory,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name=_("Категория"),
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=512, blank=True, verbose_name=_("Наименование"))
    tech_params = models.JSONField(default=dict, blank=True, verbose_name=_("Параметры"))

    # Прямая ручная привязка к нашему товару (может быть пустой)
    mapped_product = models.ForeignKey(
        "goods.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="competitor_items",
        verbose_name=_("Соответствующий наш товар"),
    )

    class Meta:
        verbose_name = _("Позиция конкурента")
        verbose_name_plural = _("Позиции конкурентов")
        indexes = [
            models.Index(fields=["competitor", "part_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["competitor", "ext_id"], name="uniq_competitor_part"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.competitor.name}:{self.part_number}"


class CompetitorProductMatch(TimestampsMixin, models.Model):
    class MatchType(models.TextChoices):
        EXACT = "exact", _("Точный")
        EQUIVALENT = "equivalent", _("Эквивалент")
        ANALOG = "analog", _("Аналог")
        SIMILAR = "similar", _("Похожий")

    competitor_product = models.ForeignKey(
        CompetitorProduct,
        on_delete=models.CASCADE,
        related_name="matches",
        verbose_name=_("Позиция конкурента"),
    )
    product = models.ForeignKey(
        "goods.Product",
        on_delete=models.CASCADE,
        related_name="competitor_matches",
        verbose_name=_("Наш товар"),
    )
    match_type = models.CharField(
        max_length=20, choices=MatchType.choices, default=MatchType.SIMILAR, verbose_name=_("Тип соответствия")
    )
    confidence = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Уверенность"),
        help_text=_("0.00–1.00, насколько уверенно сопоставление"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Заметки"))

    class Meta:
        verbose_name = _("Сопоставление с товаром")
        verbose_name_plural = _("Сопоставления с товарами")
        constraints = [
            models.UniqueConstraint(
                fields=["competitor_product", "product"], name="uniq_comp_match_pair"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.competitor_product} -> {self.product} ({self.match_type})"


class CompetitorPriceStockSnapshot(TimestampsMixin, models.Model):
    class StockStatus(models.TextChoices):
        IN_STOCK = "in_stock", _("В наличии")
        LOW_STOCK = "low_stock", _("Мало")
        OUT_OF_STOCK = "out_of_stock", _("Нет в наличии")
        ON_REQUEST = "on_request", _("Под заказ")

    competitor = models.ForeignKey(
        Competitor,
        on_delete=models.CASCADE,
        related_name="snapshots",
        verbose_name=_("Конкурент"),
    )
    competitor_product = models.ForeignKey(
        CompetitorProduct,
        on_delete=models.CASCADE,
        related_name="snapshots",
        verbose_name=_("Позиция конкурента"),
    )
    collected_at = models.DateTimeField(db_index=True, verbose_name=_("Момент сбора"))

    price_ex_vat = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, verbose_name=_("Цена без НДС")
    )
    vat_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Ставка НДС"),
        help_text=_("Доля, например 0.20"),
    )
    price_inc_vat = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, verbose_name=_("Цена с НДС")
    )
    currency = models.CharField(max_length=10, default="RUB", verbose_name=_("Валюта"))

    stock_qty = models.IntegerField(null=True, blank=True, verbose_name=_("Количество на складе"))
    stock_status = models.CharField(
        max_length=20, choices=StockStatus.choices, default=StockStatus.ON_REQUEST, verbose_name=_("Статус наличия")
    )
    delivery_days_min = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Поставка, дней от"))
    delivery_days_max = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Поставка, дней до"))
    raw_payload = models.JSONField(default=dict, blank=True, verbose_name=_("Сырые данные"))

    class Meta:
        verbose_name = _("Снимок цены/склада конкурента")
        verbose_name_plural = _("Снимки цен/складов конкурентов")
        indexes = [
            models.Index(fields=["competitor", "collected_at"]),
            models.Index(fields=["competitor_product", "collected_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["competitor_product", "collected_at"], name="uniq_comp_snapshot_per_moment"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.competitor}:{self.competitor_product} @ {self.collected_at}"


class OurPriceHistory(TimestampsMixin, models.Model):
    product = models.ForeignKey(
        "goods.Product", on_delete=models.CASCADE, related_name="price_history", verbose_name=_("Товар")
    )
    moment = models.DateTimeField(db_index=True, verbose_name=_("Момент изменения"))
    price_ex_vat = models.DecimalField(max_digits=14, decimal_places=2, verbose_name=_("Цена без НДС"))
    vat_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        verbose_name=_("Ставка НДС"),
        help_text=_("Доля, например 0.20"),
    )

    class Meta:
        verbose_name = _("История цен (наши)")
        verbose_name_plural = _("История цен (наши)")
        ordering = ["-moment"]
        constraints = [
            models.UniqueConstraint(fields=["product", "moment"], name="uniq_our_price_per_moment")
        ]
        indexes = [models.Index(fields=["product", "moment"])]

    @property
    def price_inc_vat(self):  # pragma: no cover
        try:
            return (self.price_ex_vat or 0) * (1 + (self.vat_rate or 0))
        except Exception:
            return None

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.product_id}: {self.price_ex_vat} (+{self.vat_rate}) @ {self.moment}"


class OurStockSnapshot(TimestampsMixin, models.Model):
    product = models.ForeignKey(
        "goods.Product", on_delete=models.CASCADE, related_name="stock_snapshots", verbose_name=_("Товар")
    )
    moment = models.DateTimeField(db_index=True, verbose_name=_("Момент изменения"))
    stock_qty = models.IntegerField(null=True, blank=True, verbose_name=_("Количество на складе"))
    markup_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name=_("Наценка"))
    cost_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name=_("Затраты"))
    rmb_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name=_("Курс юаня"))
    usd_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name=_("Курс доллара"))

    class Meta:
        verbose_name = _("Снимок склада (наши)")
        verbose_name_plural = _("Снимки складов (наши)")
        ordering = ["-moment"]
        constraints = [
            models.UniqueConstraint(fields=["product", "moment"], name="uniq_our_stock_per_moment")
        ]
        indexes = [models.Index(fields=["product", "moment"])]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.product_id}: {self.stock_qty} @ {self.moment}"