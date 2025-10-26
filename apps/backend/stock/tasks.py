import os
import logging
import csv
from datetime import datetime
import asyncio
from ftplib import FTP
from pathlib import Path
from decimal import Decimal, InvalidOperation
import base64
from io import BytesIO

import mysql.connector
import pandas as pd
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
    
    Оптимизированная версия с bulk-операциями:
    1. Подключается к FTP серверу конкурента PROM
    2. Скачивает файл Item.csv
    3. Парсит CSV и создает/обновляет записи CompetitorProduct батчами
    4. Создает снимки цен CompetitorPriceStockSnapshot батчами
    
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
        
        # Проверяем наличие необходимых колонок
        if rows:
            required_columns = ['ITEM_ID', 'NAME']
            available_columns = list(rows[0].keys())
            missing_columns = [col for col in required_columns if col not in available_columns]
            if missing_columns:
                error_msg = f"В CSV файле отсутствуют обязательные колонки: {missing_columns}. Доступные колонки: {available_columns}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            logger.info(f"Колонки CSV: {available_columns[:15]}{'...' if len(available_columns) > 15 else ''}")
        
        # Счетчики для пропущенных записей
        skipped_no_item_id = 0
        skipped_no_part_number = 0
        skipped_parse_errors = 0
        processed_rows = 0
        
        # Предзагрузка всех существующих брендов для кэширования
        logger.info("Загружаем существующие бренды...")
        existing_brands = {
            brand.name: brand 
            for brand in CompetitorBrand.objects.filter(competitor=competitor).select_related('competitor')
        }
        logger.info(f"Загружено {len(existing_brands)} существующих брендов")
        
        # Предзагрузка всех существующих продуктов для обновления
        # ИСПРАВЛЕНО: загружаем по ext_id, т.к. constraint в БД на (competitor_id, ext_id)
        logger.info("Загружаем существующие продукты...")
        existing_products_by_ext_id = {
            prod.ext_id: prod
            for prod in CompetitorProduct.objects.filter(competitor=competitor).select_related('brand', 'competitor')
        }
        existing_products_by_part = {
            prod.part_number: prod
            for prod in CompetitorProduct.objects.filter(competitor=competitor).select_related('brand', 'competitor')
        }
        logger.info(f"Загружено {len(existing_products_by_ext_id)} существующих продуктов")
        
        # Обрабатываем батчами для оптимизации
        batch_size = 2000
        batch_num = 0
        for i in range(0, total_rows, batch_size):
            batch_num += 1
            batch = rows[i:i + batch_size]
            logger.info(f"Обрабатываем батч {batch_num} ({len(batch)} строк, строки {i+1}-{min(i+len(batch), total_rows)})")
            
            # Для первого батча показываем пример структуры данных
            if batch_num == 1 and batch:
                logger.info(f"Пример первой строки CSV: {list(batch[0].keys())[:10]}...")
            
            # Коллекции для bulk операций
            brands_to_create = []
            products_to_create = []
            products_to_update = []
            snapshots_to_create = []
            
            # Временный кэш новых брендов в этом батче
            new_brands_cache = {}
            
            # Кэш для отслеживания дубликатов ext_id в текущем батче
            seen_ext_ids = set()
            
            with transaction.atomic():
                # Первый проход: собираем данные и создаем бренды
                parsed_rows = []
                for row in batch:
                    try:
                        # Извлекаем данные из CSV
                        item_id = row.get('ITEM_ID', '').strip()
                        if not item_id:
                            skipped_no_item_id += 1
                            continue
                        
                        # Проверяем дубликат ext_id в текущем батче
                        if item_id in seen_ext_ids:
                            # Пропускаем дубликаты в пределах одного батча
                            if len([err for err in errors if 'дубликат ITEM_ID' in err]) < 5:
                                errors.append(f"Пропущен дубликат ITEM_ID={item_id} в батче {batch_num}")
                            skipped_parse_errors += 1
                            continue
                        seen_ext_ids.add(item_id)
                        
                        part_number = row.get('NAME', '').strip()
                        if not part_number:
                            skipped_no_part_number += 1
                            continue
                        
                        producer = row.get('PRODUCER', '').strip()
                        
                        # Цена (формат: "1 642,42" - пробел как разделитель тысяч, запятая как десятичная)
                        price_ex_vat = None
                        price_str = row.get('PB_5', '').strip()
                        if price_str:
                            try:
                                # Убираем все пробелы и неразрывные пробелы, заменяем запятую на точку
                                price_clean = price_str.replace(' ', '').replace('\xa0', '').replace(',', '.')
                                price_ex_vat = Decimal(price_clean)
                            except (InvalidOperation, ValueError) as e:
                                # Логируем только первые 5 ошибок парсинга цены в батче для отладки
                                if len([err for err in errors if 'цены' in err]) < 5:
                                    errors.append(f"Ошибка парсинга цены '{price_str}' для ITEM_ID={item_id}: {e}")
                                pass
                        
                        # ИСПРАВЛЕНО: Количество на складе - складываем числа, а не строки
                        stock_qty = 0
                        for_sale = row.get('FOR_SALE', '0').strip()
                        for_sale2 = row.get('FOR_SALE2', '0').strip()
                        
                        try:
                            # Убираем пробелы из числа перед конвертацией
                            for_sale_clean = for_sale.replace(' ', '').replace('\xa0', '') if for_sale else '0'
                            stock_qty += int(for_sale_clean) if for_sale_clean else 0
                        except ValueError:
                            pass
                        
                        try:
                            # Убираем пробелы из числа перед конвертацией
                            for_sale2_clean = for_sale2.replace(' ', '').replace('\xa0', '') if for_sale2 else '0'
                            stock_qty += int(for_sale2_clean) if for_sale2_clean else 0
                        except ValueError:
                            pass
                        
                        # Определяем статус наличия
                        if stock_qty > 10:
                            stock_status = CompetitorPriceStockSnapshot.StockStatus.IN_STOCK
                        elif stock_qty > 0:
                            stock_status = CompetitorPriceStockSnapshot.StockStatus.LOW_STOCK
                        else:
                            stock_status = CompetitorPriceStockSnapshot.StockStatus.OUT_OF_STOCK
                        
                        # Создаем/находим бренд
                        brand = None
                        if producer:
                            # Проверяем в кэше существующих
                            if producer in existing_brands:
                                brand = existing_brands[producer]
                            # Проверяем в кэше новых в этом батче
                            elif producer in new_brands_cache:
                                brand = new_brands_cache[producer]
                            # Создаем новый бренд
                            else:
                                brand = CompetitorBrand(
                                    competitor=competitor,
                                    name=producer,
                                    ext_id=''
                                )
                                brands_to_create.append(brand)
                                new_brands_cache[producer] = brand
                        
                        # Сохраняем распарсенные данные
                        parsed_rows.append({
                            'item_id': item_id,
                            'part_number': part_number,
                            'brand': brand,
                            'producer': producer,
                            'price_ex_vat': price_ex_vat,
                            'stock_qty': stock_qty,
                            'stock_status': stock_status,
                            'row': row
                        })
                        
                    except Exception as e:
                        error_msg = f"Ошибка при парсинге строки {row.get('ITEM_ID', 'unknown')}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        skipped_parse_errors += 1
                        continue
                
                processed_rows += len(parsed_rows)
                
                logger.info(f"Распарсено {len(parsed_rows)} валидных строк из {len(batch)} в батче {batch_num}")
                
                # Создаем новые бренды батчем
                # ИСПРАВЛЕНО: используем ignore_conflicts=True для обработки дубликатов
                if brands_to_create:
                    created_brand_names = [b.name for b in brands_to_create]
                    CompetitorBrand.objects.bulk_create(brands_to_create, ignore_conflicts=True)
                    brands_created += len(brands_to_create)
                    logger.info(f"Создано {len(brands_to_create)} новых брендов")
                    
                    # ВАЖНО: Перезагружаем созданные бренды из БД для получения id
                    # bulk_create с ignore_conflicts=True не возвращает id
                    freshly_created_brands = CompetitorBrand.objects.filter(
                        competitor=competitor,
                        name__in=created_brand_names
                    ).select_related('competitor')
                    
                    # Обновляем кэш существующих брендов со свежими объектами из БД
                    for brand in freshly_created_brands:
                        existing_brands[brand.name] = brand
                        # Также обновляем в new_brands_cache для текущего батча
                        if brand.name in new_brands_cache:
                            new_brands_cache[brand.name] = brand
                
                # Второй проход: создаем/обновляем продукты
                for parsed in parsed_rows:
                    try:
                        # ИСПРАВЛЕНО: проверяем по ext_id (ITEM_ID), т.к. constraint на (competitor_id, ext_id)
                        existing_product = existing_products_by_ext_id.get(parsed['item_id'])
                        
                        # Получаем бренд из кэша (с актуальным id из БД)
                        brand = None
                        if parsed['producer']:
                            brand = existing_brands.get(parsed['producer'])
                        
                        if existing_product:
                            # Обновляем существующий продукт
                            existing_product.ext_id = parsed['item_id']
                            existing_product.name = parsed['part_number']
                            existing_product.brand = brand
                            existing_product.tech_params = {
                                'body': parsed['row'].get('BODY', ''),
                                'year': parsed['row'].get('YEAR_', ''),
                                'country': parsed['row'].get('COUNTRY', ''),
                                'packname': parsed['row'].get('PACKNAME', ''),
                                'pack_quant': parsed['row'].get('PACK_QUANT', ''),
                                'weight': parsed['row'].get('WEIGHT', ''),
                                'datasheet': parsed['row'].get('DATASHEET', ''),
                                'photo_url': parsed['row'].get('PHOTO_URL', ''),
                            }
                            products_to_update.append(existing_product)
                            parsed['product'] = existing_product
                        else:
                            # Создаем новый продукт
                            new_product = CompetitorProduct(
                                competitor=competitor,
                                part_number=parsed['part_number'],
                                ext_id=parsed['item_id'],
                                name=parsed['part_number'],
                                brand=brand,
                                tech_params={
                                    'body': parsed['row'].get('BODY', ''),
                                    'year': parsed['row'].get('YEAR_', ''),
                                    'country': parsed['row'].get('COUNTRY', ''),
                                    'packname': parsed['row'].get('PACKNAME', ''),
                                    'pack_quant': parsed['row'].get('PACK_QUANT', ''),
                                    'weight': parsed['row'].get('WEIGHT', ''),
                                    'datasheet': parsed['row'].get('DATASHEET', ''),
                                    'photo_url': parsed['row'].get('PHOTO_URL', ''),
                                }
                            )
                            products_to_create.append(new_product)
                            parsed['product'] = new_product
                            
                    except Exception as e:
                        error_msg = f"Ошибка при подготовке продукта {parsed['part_number']}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue
                
                # Bulk create новых продуктов
                # ИСПРАВЛЕНО: используем ignore_conflicts=True для обработки дубликатов
                if products_to_create:
                    created_ext_ids = [p.ext_id for p in products_to_create]
                    CompetitorProduct.objects.bulk_create(products_to_create, ignore_conflicts=True)
                    products_created += len(products_to_create)
                    logger.info(f"Создано {len(products_to_create)} новых продуктов")
                    
                    # ВАЖНО: Перезагружаем созданные продукты из БД для получения id
                    # bulk_create с ignore_conflicts=True не возвращает id
                    freshly_created = CompetitorProduct.objects.filter(
                        competitor=competitor,
                        ext_id__in=created_ext_ids
                    ).select_related('brand', 'competitor')
                    
                    # Обновляем кэш существующих продуктов со свежими объектами из БД
                    for product in freshly_created:
                        existing_products_by_ext_id[product.ext_id] = product
                        existing_products_by_part[product.part_number] = product
                
                # Bulk update существующих продуктов
                if products_to_update:
                    CompetitorProduct.objects.bulk_update(
                        products_to_update,
                        ['ext_id', 'name', 'brand', 'tech_params', 'updated_at'],
                        batch_size=1000
                    )
                    products_updated += len(products_to_update)
                    logger.info(f"Обновлено {len(products_to_update)} продуктов")
                
                # Третий проход: создаем снимки
                for parsed in parsed_rows:
                    try:
                        if 'product' not in parsed:
                            continue
                        
                        # ВАЖНО: Используем продукт из кэша (с актуальным id из БД)
                        product = existing_products_by_ext_id.get(parsed['item_id'])
                        if not product:
                            # Если по какой-то причине не нашли, пропускаем
                            logger.warning(f"Не найден продукт с ext_id={parsed['item_id']} для создания снимка")
                            continue
                        
                        snapshot = CompetitorPriceStockSnapshot(
                            competitor=competitor,
                            competitor_product=product,
                            collected_at=collected_at,
                            price_ex_vat=parsed['price_ex_vat'],
                            stock_qty=parsed['stock_qty'],
                            stock_status=parsed['stock_status'],
                            currency='RUB',
                            raw_payload=dict(parsed['row'])
                        )
                        snapshots_to_create.append(snapshot)
                        
                    except Exception as e:
                        error_msg = f"Ошибка при создании снимка для {parsed.get('part_number', 'unknown')}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue
                
                # Bulk create снимков
                if snapshots_to_create:
                    CompetitorPriceStockSnapshot.objects.bulk_create(
                        snapshots_to_create, 
                        ignore_conflicts=True,
                        batch_size=1000
                    )
                    snapshots_created += len(snapshots_to_create)
                    logger.info(f"Создано {len(snapshots_to_create)} снимков")
            
            logger.info(
                f"Батч завершен. Всего создано: продуктов={products_created}, "
                f"обновлено={products_updated}, брендов={brands_created}, снимков={snapshots_created}"
            )
        
        result = {
            "success": True,
            "total_rows": total_rows,
            "processed_rows": processed_rows,
            "products_created": products_created,
            "products_updated": products_updated,
            "brands_created": brands_created,
            "snapshots_created": snapshots_created,
            "skipped_no_item_id": skipped_no_item_id,
            "skipped_no_part_number": skipped_no_part_number,
            "skipped_parse_errors": skipped_parse_errors,
            "errors_count": len(errors),
            "errors": errors[:10] if errors else []  # Первые 10 ошибок
        }
        
        logger.info(
            f"✅ Импорт PROM завершен успешно! "
            f"Всего строк в CSV: {total_rows}, обработано валидных: {processed_rows} ({processed_rows/total_rows*100:.1f}%). "
            f"Создано: {products_created} продуктов, {brands_created} брендов, {snapshots_created} снимков. "
            f"Обновлено: {products_updated} продуктов. "
            f"Пропущено: {skipped_no_item_id} без ITEM_ID, {skipped_no_part_number} без NAME, {skipped_parse_errors} с ошибками парсинга. "
            f"Всего ошибок: {len(errors)}"
        )
        return result
        
    except Exception as e:
        error_msg = f"Ошибка при парсинге CSV файла: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}


@shared_task
def export_competitor_price_comparison_task():
    """
    Celery-задача для экспорта сравнения цен с конкурентами в Excel файл.
    ОПТИМИЗИРОВАННАЯ ВЕРСИЯ с предзагрузкой данных.
    
    Берёт все наши товары (part number) и находит точные совпадения
    по part_number у конкурентов, затем формирует таблицу сравнения цен.
    
    Returns:
        dict: Словарь с результатом экспорта и бинарным содержимым файла в base64
    """
    from collections import defaultdict
    from django.db.models import Prefetch, OuterRef, Subquery
    
    try:
        logger.info("Начинаем экспорт сравнения цен с конкурентами (оптимизированная версия)")
        
        # ШАГ 1: Предзагружаем все наши товары с последними ценами
        logger.info("Загружаем наши товары и последние цены...")
        our_products = list(Product.objects.select_related('brand').all())
        total_products = len(our_products)
        logger.info(f"Загружено {total_products} наших товаров")
        
        # ШАГ 2: Загружаем все последние цены одним запросом
        logger.info("Загружаем последние цены наших товаров...")
        product_ids = [p.id for p in our_products]
        
        # Получаем последние цены для каждого товара используя подзапрос
        latest_prices_subquery = OurPriceHistory.objects.filter(
            product_id=OuterRef('product_id')
        ).order_by('-moment').values('id')[:1]
        
        our_prices_dict = {}
        our_prices = OurPriceHistory.objects.filter(
            id__in=Subquery(latest_prices_subquery),
            product_id__in=product_ids
        ).select_related('product')
        
        for price in our_prices:
            our_prices_dict[price.product_id] = price
        
        logger.info(f"Загружено {len(our_prices_dict)} последних цен")
        
        # ШАГ 3: Загружаем все товары конкурентов и группируем по part_number
        logger.info("Загружаем товары конкурентов...")
        competitor_products = CompetitorProduct.objects.select_related(
            'competitor', 'brand'
        ).all()
        
        # Группируем по part_number (нижний регистр для сравнения)
        comp_products_by_part = defaultdict(list)
        for comp_prod in competitor_products:
            comp_products_by_part[comp_prod.part_number.lower()].append(comp_prod)
        
        logger.info(f"Загружено {len(competitor_products)} товаров конкурентов, уникальных part_number: {len(comp_products_by_part)}")
        
        # ШАГ 4: Загружаем все последние snapshots для товаров конкурентов
        logger.info("Загружаем последние snapshots цен конкурентов...")
        comp_product_ids = [cp.id for cp in competitor_products]
        
        latest_snapshots_subquery = CompetitorPriceStockSnapshot.objects.filter(
            competitor_product_id=OuterRef('competitor_product_id')
        ).order_by('-collected_at').values('id')[:1]
        
        snapshots_dict = {}
        snapshots = CompetitorPriceStockSnapshot.objects.filter(
            id__in=Subquery(latest_snapshots_subquery),
            competitor_product_id__in=comp_product_ids
        ).select_related('competitor_product')
        
        for snapshot in snapshots:
            snapshots_dict[snapshot.competitor_product_id] = snapshot
        
        logger.info(f"Загружено {len(snapshots_dict)} последних snapshots")
        
        # ШАГ 5: Обрабатываем данные (теперь все данные в памяти!)
        logger.info("Начинаем обработку товаров...")
        comparison_data = []
        processed = 0
        matches_found = 0
        
        for product in our_products:
            processed += 1
            if processed % 1000 == 0:  # Увеличили до 1000 т.к. теперь быстро
                logger.info(f"Обработано {processed}/{total_products} товаров...")
            
            part_number = product.name
            
            # Получаем цену из предзагруженного словаря
            our_latest_price = our_prices_dict.get(product.id)
            
            our_price_ex_vat = None
            our_price_date = None
            
            if our_latest_price:
                our_price_ex_vat = float(our_latest_price.price_ex_vat) if our_latest_price.price_ex_vat else None
                our_price_date = our_latest_price.moment
            
            # Ищем совпадения в предзагруженном словаре
            comp_products = comp_products_by_part.get(part_number.lower(), [])
            
            if comp_products:
                matches_found += 1
                # Обрабатываем каждый товар конкурента
                for comp_product in comp_products:
                    # Получаем snapshot из предзагруженного словаря
                    latest_snapshot = snapshots_dict.get(comp_product.id)
                    
                    comp_price_ex_vat = None
                    comp_stock_qty = None
                    comp_price_date = None
                    price_difference = None
                    price_difference_pct = None
                    
                    if latest_snapshot:
                        comp_price_ex_vat = float(latest_snapshot.price_ex_vat) if latest_snapshot.price_ex_vat else None
                        comp_stock_qty = latest_snapshot.stock_qty
                        comp_price_date = latest_snapshot.collected_at
                        
                        # Вычисляем разницу в ценах
                        if our_price_ex_vat and comp_price_ex_vat:
                            price_difference = our_price_ex_vat - comp_price_ex_vat
                            price_difference_pct = (price_difference / comp_price_ex_vat) * 100
                    
                    comparison_data.append({
                        'Part Number': part_number,
                        'Наш бренд': product.brand.name if product.brand else '',
                        'Наша цена': our_price_ex_vat,
                        'Дата нашей цены': our_price_date.strftime('%Y-%m-%d %H:%M') if our_price_date else '',
                        'Конкурент': comp_product.competitor.name,
                        'Бренд конкурента': comp_product.brand.name if comp_product.brand else '',
                        'Цена конкурента': comp_price_ex_vat,
                        'Дата цены конкурента': comp_price_date.strftime('%Y-%m-%d %H:%M') if comp_price_date else '',
                        'Остаток у конкурента': comp_stock_qty,
                        'Разница в цене': round(price_difference, 2) if price_difference is not None else None,
                        'Разница в цене (%)': round(price_difference_pct, 2) if price_difference_pct is not None else None,
                    })
            else:
                # Товар без совпадений у конкурентов
                comparison_data.append({
                    'Part Number': part_number,
                    'Наш бренд': product.brand.name if product.brand else '',
                    'Наша цена (без НДС)': our_price_ex_vat,
                    'Дата нашей цены': our_price_date.strftime('%Y-%m-%d %H:%M') if our_price_date else '',
                    'Конкурент': 'Нет совпадений',
                    'Бренд конкурента': '',
                    'Цена конкурента (без НДС)': None,
                    'Дата цены конкурента': '',
                    'Остаток у конкурента': None,
                    'Разница в цене': None,
                    'Разница в цене (%)': None,
                })
        
        logger.info(f"Обработка завершена. Всего товаров: {total_products}, найдено совпадений: {matches_found}")
        
        # Создаём DataFrame
        df = pd.DataFrame(comparison_data)
        
        # Создаём Excel файл в памяти
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Сравнение цен', index=False)
            
            # Получаем workbook и worksheet для форматирования
            workbook = writer.book
            worksheet = writer.sheets['Сравнение цен']
            
            # Автоподбор ширины столбцов
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Максимум 50 символов
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Закрепляем первую строку (заголовки)
            worksheet.freeze_panes = 'A2'
        
        # Получаем содержимое буфера
        excel_buffer.seek(0)
        file_data = excel_buffer.getvalue()
        
        # Преобразуем бинарные данные в base64 для безопасной передачи через JSON
        encoded_data = base64.b64encode(file_data).decode('utf-8')
        
        # Формируем результат
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"price_comparison_{timestamp}.xlsx"
        
        logger.info(f"✅ Excel файл создан успешно: {filename}, записей: {len(comparison_data)}")
        
        return {
            'success': True,
            'filename': filename,
            'data': encoded_data,
            'records': len(comparison_data),
            'total_products': total_products,
            'matches_found': matches_found
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка при экспорте сравнения цен: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f"Ошибка при экспорте: {str(e)}"
        }
