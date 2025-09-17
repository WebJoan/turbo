import os
import logging
from datetime import datetime

import mysql.connector
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from mysql.connector import Error

from goods.models import Product
from .models import OurPriceHistory


logger = logging.getLogger(__name__)

mysql_config = {
    "host": os.getenv("MYSQL_HOST"),
    "port": os.getenv("MYSQL_PORT"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASS"),
    "database": os.getenv("MYSQL_DB"),
    "charset": os.getenv("MYSQL_CHARSET"),
}


@shared_task
def import_histprice_from_mysql(batch_size: int = 5000):
    """
    Импортирует историю наших цен из таблицы MySQL `histprice` в модель OurPriceHistory.

    Ожидаемые поля в MySQL:
      - mainbase: внешний ID товара (равен Product.ext_id)
      - moment: дата/время изменения цены
      - price: цена без НДС
      - nds: ставка НДС (доля, например 0.20)
    """
    connection = None
    total_rows = 0
    created = 0
    updated = 0
    skipped = 0

    try:
        connection = mysql.connector.connect(**mysql_config)
        if not connection.is_connected():
            logger.error("MySQL-соединение не установлено")
            return {
                "success": False,
                "error": "Не удалось установить соединение с MySQL",
            }

        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT mainbase, moment, price, nds
            FROM histprice
            WHERE mainbase IS NOT NULL
            ORDER BY moment ASC
            """
        )

        rows = cursor.fetchmany(batch_size)
        while rows:
            total_rows += len(rows)
            with transaction.atomic():
                # Сбор уникальных mainbase для батч-загрузки Product
                mainbase_ids = {str(r["mainbase"]) for r in rows if r.get("mainbase") is not None}
                products_by_ext = {
                    p.ext_id: p for p in Product.objects.filter(ext_id__in=mainbase_ids)
                }

                for r in rows:
                    ext_id = str(r.get("mainbase")) if r.get("mainbase") is not None else None
                    if not ext_id:
                        skipped += 1
                        continue

                    product = products_by_ext.get(ext_id)
                    if not product:
                        # Нет соответствующего товара в нашей БД
                        skipped += 1
                        continue

                    # Приведение moment к datetime
                    moment_val = r.get("moment")
                    if isinstance(moment_val, str):
                        try:
                            # Попытка ISO8601
                            moment = datetime.fromisoformat(moment_val)
                        except Exception:
                            # На всякий случай универсальный парсинг
                            from dateutil import parser  # type: ignore

                            moment = parser.parse(moment_val)
                    else:
                        moment = moment_val

                    if moment is None:
                        skipped += 1
                        continue

                    # Делаем datetime timezone-aware если он naive
                    if moment.tzinfo is None or moment.utcoffset() is None:
                        moment = timezone.make_aware(moment)

                    price = r.get("price")
                    vat = r.get("nds")

                    obj, is_created = OurPriceHistory.objects.get_or_create(
                        product=product,
                        moment=moment,
                        defaults={
                            "price_ex_vat": price if price is not None else 0,
                            "vat_rate": vat if vat is not None else 0,
                        },
                    )
                    if is_created:
                        created += 1
                    else:
                        # Обновляем при изменении
                        changed = False
                        if price is not None and obj.price_ex_vat != price:
                            obj.price_ex_vat = price
                            changed = True
                        if vat is not None and obj.vat_rate != vat:
                            obj.vat_rate = vat
                            changed = True
                        if changed:
                            obj.save(update_fields=["price_ex_vat", "vat_rate", "updated_at"])
                            updated += 1
                        else:
                            skipped += 1

            rows = cursor.fetchmany(batch_size)

        logger.info(
            "Импорт histprice завершён: всего=%s, создано=%s, обновлено=%s, пропущено=%s",
            total_rows,
            created,
            updated,
            skipped,
        )
        return {
            "success": True,
            "total": total_rows,
            "created": created,
            "updated": updated,
            "skipped": skipped,
        }

    except Error as e:
        logger.error(f"Ошибка при подключении к MySQL: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        logger.error(f"Ошибка при импорте histprice: {e}")
        return {"success": False, "error": str(e)}
    finally:
        try:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
        except Exception:  # noqa: BLE001
            pass


