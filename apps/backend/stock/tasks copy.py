import os
import logging
import csv
from datetime import datetime
import asyncio
from ftplib import FTP
from pathlib import Path
from decimal import Decimal, InvalidOperation

import mysql.connector
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from mysql.connector import Error
from asgiref.sync import sync_to_async

from goods.models import Product
from .models import (
    OurPriceHistory,
    Competitor,
    CompetitorBrand,
    CompetitorCategory,
    CompetitorProduct,
    CompetitorPriceStockSnapshot,
)
from django.utils import timezone
from decimal import Decimal, InvalidOperation


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


@shared_task
def import_prom_from_ftp():
    """
    Импортирует данные о товарах конкурента PROM из FTP.
    
    1. Подключается к FTP серверу конкурента PROM
    2. Скачивает файл Item.csv
    3. Парсит CSV и создает/обновляет записи CompetitorProduct
    4. Создает снимки цен CompetitorPriceStockSnapshot
    
    Возвращает статистику по импортированным данным.
    """
    from django.conf import settings
    from django.utils import timezone
    
    logger.info("Начинаем импорт PROM из FTP")
    
    # Находим конкурента PROM в базе
    try:
        competitor = Competitor.objects.get(name="PROM", data_source_type=Competitor.DataSourceType.FTP_CSV)
    except Competitor.DoesNotExist:
        error_msg = "Конкурент PROM с типом FTP не найден в базе данных"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    logger.info(f"Найден конкурент: {competitor.name}")
    logger.info(f"FTP настройки: host={competitor.data_url}, user={competitor.username}")
    
    # Очищаем FTP хост от протокола
    ftp_host = competitor.data_url.strip()
    if ftp_host.startswith('ftp://'):
        ftp_host = ftp_host[6:]
    elif ftp_host.startswith('ftps://'):
        ftp_host = ftp_host[7:]
    ftp_host = ftp_host.rstrip('/')
    
    logger.info(f"Очищенный FTP хост: '{ftp_host}'")
    
    # Создаем директорию для скачивания
    base_download_dir = Path(settings.MEDIA_ROOT) / "ftp_downloads"
    competitor_dir = base_download_dir / competitor.name
    competitor_dir.mkdir(parents=True, exist_ok=True)
    
    csv_file_path = competitor_dir / "Item.csv"
    
    try:
        # Подключаемся к FTP и скачиваем файл
        logger.info("Подключаемся к FTP серверу...")
        ftp = FTP(ftp_host)
        ftp.login(user=competitor.username or 'anonymous', passwd=competitor.password or '')
        
        logger.info("Скачиваем файл Item.csv...")
        with open(csv_file_path, 'wb') as local_file:
            ftp.retrbinary('RETR Item.csv', local_file.write)
        
        ftp.quit()
        logger.info(f"Файл успешно скачан: {csv_file_path}")
        
    except Exception as e:
        error_msg = f"Ошибка при скачивании файла с FTP: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    # Парсим CSV файл
    try:
        logger.info("Начинаем парсинг CSV файла...")
        
        products_created = 0
        products_updated = 0
        brands_created = 0
        snapshots_created = 0
        errors = []
        
        collected_at = timezone.now()
        
        # Пробуем разные кодировки для чтения файла
        encodings_to_try = ['windows-1251', 'cp1251', 'utf-8-sig', 'utf-8', 'latin-1']
        csv_data = None
        used_encoding = None
        
        for encoding in encodings_to_try:
            try:
                with open(csv_file_path, 'r', encoding=encoding) as f:
                    # Используем точку с запятой как разделитель
                    reader = csv.DictReader(f, delimiter=';')
                    csv_data = list(reader)
                    used_encoding = encoding
                    break
            except UnicodeDecodeError:
                continue
        
        if csv_data is None:
            raise ValueError("Не удалось определить кодировку файла")
        
        logger.info(f"Файл прочитан с кодировкой: {used_encoding}")
        
        rows = csv_data
        total_rows = len(rows)
        logger.info(f"Прочитано {total_rows} строк из Item.csv")
        
        # Обрабатываем батчами для оптимизации
        batch_size = 5000
        for i in range(0, total_rows, batch_size):
            batch = rows[i:i + batch_size]
            logger.info(f"Обрабатываем батч {i // batch_size + 1} ({len(batch)} строк)")
            
            # Обрабатываем каждую строку в отдельной транзакции
            for row in batch:
                try:
                    # Извлекаем данные из CSV
                    item_id = row.get('ITEM_ID', '').strip()
                    if not item_id:
                        continue
                    
                    part_number = row.get('NAME', '').strip()
                    if not part_number:
                        continue
                    
                    fullname = row.get('FULLNAME', '').strip()
                    description = row.get('DESCRIPTION', '').strip()
                    producer = row.get('PRODUCER', '').strip()
                    
                    # Цена
                    price_ex_vat = None
                    price_str = row.get('PB_5', '').strip()  # PB_5 - самая низкая цена по объему
                    if price_str:
                        try:
                            price_ex_vat = Decimal(price_str.replace(',', '.'))
                        except (InvalidOperation, ValueError):
                            pass
                    
                    # Количество на складе
                    stock_qty = None
                    for_sale = row.get('FOR_SALE', '0').strip()
                    for_sale2 = row.get('FOR_SALE2', '0').strip()

                    stock_qty = for_sale + for_sale2
                    
                    try:
                        stock_qty = int(for_sale) if for_sale else 0
                    except ValueError:
                        stock_qty = 0
                    
                    # Определяем статус наличия
                    if stock_qty > 10:
                        stock_status = CompetitorPriceStockSnapshot.StockStatus.IN_STOCK
                    elif stock_qty > 0:
                        stock_status = CompetitorPriceStockSnapshot.StockStatus.LOW_STOCK
                    else:
                        stock_status = CompetitorPriceStockSnapshot.StockStatus.OUT_OF_STOCK
                    
                    with transaction.atomic():
                        # Создаем/находим бренд
                        brand = None
                        if producer:
                            brand, brand_created = CompetitorBrand.objects.get_or_create(
                                competitor=competitor,
                                name=producer,
                                defaults={'ext_id': ''}
                            )
                            if brand_created:
                                brands_created += 1
                        
                        # Создаем/обновляем продукт
                        product, product_created = CompetitorProduct.objects.update_or_create(
                            competitor=competitor,
                            part_number=part_number,
                            defaults={
                                'ext_id': item_id,
                                'name': part_number,
                                'brand': brand,
                                'tech_params': {
                                    'body': row.get('BODY', ''),
                                    'year': row.get('YEAR_', ''),
                                    'country': row.get('COUNTRY', ''),
                                    'packname': row.get('PACKNAME', ''),
                                    'pack_quant': row.get('PACK_QUANT', ''),
                                    'weight': row.get('WEIGHT', ''),
                                    'datasheet': row.get('DATASHEET', ''),
                                    'photo_url': row.get('PHOTO_URL', ''),
                                }
                            }
                        )
                        
                        if product_created:
                            products_created += 1
                        else:
                            products_updated += 1
                        
                        # Создаем или обновляем снимок цены и наличия
                        snapshot, snapshot_created = CompetitorPriceStockSnapshot.objects.update_or_create(
                            competitor=competitor,
                            competitor_product=product,
                            collected_at=collected_at,
                            defaults={
                                'price_ex_vat': price_ex_vat,
                                'stock_qty': stock_qty,
                                'stock_status': stock_status,
                                'currency': 'RUB',
                                'raw_payload': dict(row)
                            }
                        )
                        if snapshot_created:
                            snapshots_created += 1
                        
                except Exception as e:
                    error_msg = f"Ошибка при обработке строки {row.get('ITEM_ID', 'unknown')}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
            logger.info(f"Батч обработан. Создано продуктов: {products_created}, обновлено: {products_updated}")
        
        result = {
            "success": True,
            "total_rows": total_rows,
            "products_created": products_created,
            "products_updated": products_updated,
            "brands_created": brands_created,
            "snapshots_created": snapshots_created,
            "errors_count": len(errors),
            "errors": errors[:10] if errors else []  # Первые 10 ошибок
        }
        
        logger.info(f"Импорт PROM завершен: {result}")
        return result
        
    except Exception as e:
        error_msg = f"Ошибка при парсинге CSV файла: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}


