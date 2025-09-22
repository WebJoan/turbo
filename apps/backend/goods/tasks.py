import os
import json
import logging
import mysql.connector
import pandas as pd
import base64
from celery import shared_task
from django.db import transaction
from django.db.models import Q, Count
from mysql.connector import Error
from django.conf import settings
from api.models import User
from goods.indexers import ProductIndexer
from goods.models import Brand, Product, ProductGroup, ProductSubgroup, FileBlob, ProductFile
from datetime import datetime
from io import BytesIO
import hashlib
import mimetypes
import requests

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
def update_products_from_mysql():
    """
    Celery-задача для обновления товаров и связанных данных в локальной базе из удалённой MySQL.
    Обновляет группы товаров, подгруппы, бренды и сами товары с техническими параметрами.
    Устанавливает product_manager на основе invoice_user из MySQL.
    """
    connection = None
    try:
        connection = mysql.connector.connect(**mysql_config)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)

            # Выполняем SQL-запрос для получения данных о товарах
            cursor.execute(
                """
                SELECT
                    i.mainbase AS product_id,
                    m.tovmark AS product_name,
                    b.id AS brand_id,
                    m.brand,
                    m.mgroup AS subgroup_id,
                    g.tovmark AS subgroup_name,
                    g.typecode AS group_id,
                    g.tovgroup AS group_name,
                    w.complex AS complex_name,
                    w.description AS description,
                    i.timestamp AS last_bill,
                    inv.user AS invoice_user,
                    COALESCE(
                        (SELECT
                            CONCAT('{',
                                GROUP_CONCAT(
                                    CONCAT('"', tp.name, '": "', t.fact, '"')
                                    SEPARATOR ', '
                                ),
                            '}')
                         FROM metrinfo t
                         JOIN metrics tp ON t.metrics = tp.id
                         WHERE t.mainbase = m.id
                        ), '{}'
                    ) AS tech_params
                FROM invline i
                INNER JOIN (
                    SELECT
                        mainbase,
                        MAX(timestamp) AS max_timestamp
                    FROM invline
                    WHERE invoice > 0
                      AND mainbase > 0
                    GROUP BY mainbase
                ) latest ON i.mainbase = latest.mainbase
                   AND i.timestamp = latest.max_timestamp
                INNER JOIN mainbase m ON m.id = i.mainbase
                INNER JOIN mainwide w ON w.mainbase = m.id
                INNER JOIN brand b ON m.brand = b.name
                INNER JOIN invoice inv ON inv.id = i.invoice
                INNER JOIN groupsb g ON m.mgroup = g.mgroup
                WHERE inv.user <> '';
            """
            )

            product_data = cursor.fetchall()

            if not product_data:
                logger.warning("MySQL-запрос не вернул данных")
                return "Не получено данных для обновления"
        else:
            logger.error("MySQL-соединение не установлено")
            return "Не удалось установить соединение с MySQL"
    except Error as e:
        logger.error(f"Ошибка при подключении к MySQL: {e}")
        return f"Ошибка при получении данных: {e}"
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            logger.info("MySQL-соединение закрыто")

    # Счетчики для отчета
    groups_created = 0
    groups_updated = 0
    subgroups_created = 0
    subgroups_updated = 0
    brands_created = 0
    brands_updated = 0
    products_created = 0
    products_updated = 0
    managers_linked = 0
    params_updated = 0

    try:
        # Сначала получаем всех product-менеджеров и создаем словарь {old_db_name: user_instance}
        product_managers = {
            pm.old_db_name: pm for pm in User.objects.filter(role=User.Role.PURCHASER)
        }

        # Обновляем данные в Django моделях
        with transaction.atomic():
            # Словари для хранения уже обработанных объектов
            processed_groups = {}
            processed_subgroups = {}
            processed_brands = {}

            for item in product_data:
                # 1. Обработка группы товаров
                if item["group_id"] not in processed_groups:
                    group, group_created = (
                        ProductGroup.objects.update_or_create(
                            ext_id=item["group_id"],
                            defaults={"name": item["group_name"]},
                        )
                    )
                    processed_groups[item["group_id"]] = group
                    if group_created:
                        groups_created += 1
                    else:
                        groups_updated += 1
                else:
                    group = processed_groups[item["group_id"]]

                # 2. Обработка подгруппы товаров
                if item["subgroup_id"] not in processed_subgroups:
                    subgroup, subgroup_created = (
                        ProductSubgroup.objects.update_or_create(
                            ext_id=item["subgroup_id"],
                            defaults={
                                "name": item["subgroup_name"],
                                "group": group,
                            },
                        )
                    )
                    processed_subgroups[item["subgroup_id"]] = subgroup
                    if subgroup_created:
                        subgroups_created += 1
                    else:
                        subgroups_updated += 1
                else:
                    subgroup = processed_subgroups[item["subgroup_id"]]

                # 3. Обработка бренда
                if item["brand_id"] not in processed_brands:
                    brand, brand_created = Brand.objects.update_or_create(
                        ext_id=item["brand_id"],
                        defaults={"name": item["brand"]},
                    )
                    processed_brands[item["brand_id"]] = brand
                    if brand_created:
                        brands_created += 1
                    else:
                        brands_updated += 1
                else:
                    brand = processed_brands[item["brand_id"]]

                # Определяем product-менеджера для товара
                product_manager = None
                if (
                    item["invoice_user"]
                    and item["invoice_user"] in product_managers
                ):
                    product_manager = product_managers[item["invoice_user"]]

                # Подготовка технических параметров
                try:
                    tech_params = json.loads(item["tech_params"])
                    has_params = len(tech_params) > 0
                except (json.JSONDecodeError, TypeError):
                    tech_params = {}
                    has_params = False

                # 4. Обработка товара
                product, product_created = Product.objects.update_or_create(
                    ext_id=item["product_id"],
                    defaults={
                        "name": item["product_name"],
                        "subgroup": subgroup,
                        "brand": brand,
                        "product_manager": product_manager,
                        "tech_params": tech_params,
                        "complex_name": item["complex_name"],
                        "description": item["description"],
                    },
                )

                if product_created:
                    products_created += 1
                else:
                    products_updated += 1

                # Подсчитываем количество товаров, к которым были добавлены параметры
                if has_params:
                    params_updated += 1

                # Подсчитываем количество товаров, к которым был привязан менеджер
                if product_manager:
                    managers_linked += 1

        logger.info(
            f"Обновлены данные товаров: группы {groups_updated}/{groups_created}, "
            f"подгруппы {subgroups_updated}/{subgroups_created}, "
            f"бренды {brands_updated}/{brands_created}, "
            f"товары {products_updated}/{products_created}, "
            f"привязано менеджеров: {managers_linked}, "
            f"обновлено параметров: {params_updated}"
        )
    except Exception as e:
        logger.error(f"Ошибка при обновлении данных в базе Django: {e}")
        return f"Ошибка при обновлении данных: {e}"

    return (
        f"Обновлено данных:\n"
        f"Группы: {groups_updated} (создано: {groups_created})\n"
        f"Подгруппы: {subgroups_updated} (создано: {subgroups_created})\n"
        f"Бренды: {brands_updated} (создано: {brands_created})\n"
        f"Товары: {products_updated} (создано: {products_created})\n"
        f"Привязано менеджеров: {managers_linked}\n"
        f"Обновлено параметров: {params_updated}"
    )


def _ensure_blob_from_response(resp, filename_hint: str | None) -> FileBlob:
    """Читает HTTP-ответ один раз: одновременно считает SHA-256 и накапливает содержимое."""
    content_type = resp.headers.get("Content-Type", "")
    buffer = BytesIO()
    hasher = hashlib.sha256()
    total = 0
    for chunk in resp.iter_content(chunk_size=8192):
        if not chunk:
            continue
        hasher.update(chunk)
        buffer.write(chunk)
        total += len(chunk)
    sha = hasher.hexdigest()

    # Дедуп по sha
    existing = FileBlob.objects.filter(sha256=sha).first()
    if existing:
        return existing

    # Вычисление имени и MIME
    filename = filename_hint or "file"
    cd = resp.headers.get("Content-Disposition")
    if cd and "filename=" in cd:
        filename = cd.split("filename=")[-1].strip('"')
    mime = content_type or (mimetypes.guess_type(filename)[0] or "application/octet-stream")

    from django.core.files.base import ContentFile

    buffer.seek(0)
    blob = FileBlob(sha256=sha, size=total, mime_type=mime)
    blob.file.save(name=filename, content=ContentFile(buffer.read()), save=True)
    return blob


def _fetch_zip2002_file(product_ext_id: str, file_type: str) -> tuple[FileBlob | None, str | None]:
    # file_type: "datasheet" -> type=file_p, "drawing" -> type=file_i
    if file_type == ProductFile.FileType.DATASHEET:
        url = f"https://www.zip-2002.ru/zip-download.php/?type=file_p&id={product_ext_id}"
    else:
        url = f"https://www.zip-2002.ru/zip-download.php/?type=file_i&id={product_ext_id}"

    try:
        resp = requests.get(url, stream=True, timeout=30)
        if resp.status_code == 404:
            return None, url
        resp.raise_for_status()
        blob = _ensure_blob_from_response(resp, filename_hint=None)
        return blob, url
    except Exception as e:
        logger.warning(f"Не удалось скачать файл для id={product_ext_id} ({file_type}): {e}")
        return None, url


@shared_task
def download_all_datasheets(batch_size: int = 500):
    """
    Скачивает даташиты для всех товаров, у которых их ещё нет.
    Дедупликация через FileBlob.sha256 и уникальность ProductFile(product, file_type).
    """
    qs = (
        Product.objects.exclude(ext_id__isnull=True)
        .exclude(ext_id__exact="")
        .select_related("brand", "subgroup")
    )
    processed = 0
    created = 0
    skipped = 0
    for product in qs.iterator(chunk_size=batch_size):
        # пропускаем, если уже есть датащит
        if ProductFile.objects.filter(product=product, file_type=ProductFile.FileType.DATASHEET).exists():
            skipped += 1
            continue
        blob, src = _fetch_zip2002_file(product.ext_id, ProductFile.FileType.DATASHEET)
        if blob:
            try:
                ProductFile.objects.create(
                    product=product,
                    blob=blob,
                    file_type=ProductFile.FileType.DATASHEET,
                    source_url=src or "",
                )
                created += 1
            except Exception as e:
                logger.info(f"Файл уже привязан или конфликт: {e}")
        processed += 1
    return {"processed": processed, "created": created, "skipped": skipped}


@shared_task
def download_all_drawings(batch_size: int = 500):
    """
    Скачивает чертежи для всех товаров, у которых их ещё нет.
    """
    qs = (
        Product.objects.exclude(ext_id__isnull=True)
        .exclude(ext_id__exact="")
        .select_related("brand", "subgroup")
    )
    processed = 0
    created = 0
    skipped = 0
    for product in qs.iterator(chunk_size=batch_size):
        if ProductFile.objects.filter(product=product, file_type=ProductFile.FileType.DRAWING).exists():
            skipped += 1
            continue
        blob, src = _fetch_zip2002_file(product.ext_id, ProductFile.FileType.DRAWING)
        if blob:
            try:
                ProductFile.objects.create(
                    product=product,
                    blob=blob,
                    file_type=ProductFile.FileType.DRAWING,
                    source_url=src or "",
                )
                created += 1
            except Exception as e:
                logger.info(f"Файл уже привязан или конфликт: {e}")
        processed += 1
    return {"processed": processed, "created": created, "skipped": skipped}


@shared_task
def export_parts_to_csv():
    """
    Celery-задача для экспорта деталей брендов RUICHI, SZC, ZTM-ELECTRO
    из удалённой MySQL базы в CSV файл.

    CSV файл будет сохранен в корневой директории проекта (рядом с manage.py).
    """
    import csv
    from datetime import datetime
    
    connection = None
    try:
        connection = mysql.connector.connect(**mysql_config)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)

            # Выполняем запрос
            query = """
            SELECT
                m.id,
                m.tovmark AS part,
                m.brand,
                m.excode AS img_code,
                w.subgroup_ruelcom AS subgroup,
                w.complex,
                COALESCE(
                    (SELECT
                        CONCAT('{',
                            GROUP_CONCAT(
                                CONCAT('"', tp.name, '": "', t.fact, '"')
                                SEPARATOR ', '
                            ),
                        '}')
                     FROM metrinfo t
                     JOIN metrics tp ON t.metrics = tp.id
                     WHERE t.mainbase = i.mainbase
                    ), '{}'
                ) AS tech_params
            FROM mainbase m
            INNER JOIN mainwide w ON w.mainbase = m.id
            WHERE m.brand IN ('RUICHI', 'SZC', 'ZTM-ELECTRO')
            AND m.ruelsite <> 0;
            """

            cursor.execute(query)
            parts_data = cursor.fetchall()

            if not parts_data:
                logger.warning("Запрос не вернул данных")
                return "Данные не найдены"
        else:
            logger.error("MySQL-соединение не установлено")
            return "Ошибка соединения с базой данных"

    except Error as e:
        logger.error(f"Ошибка при подключении к MySQL: {e}")
        return f"Ошибка: {str(e)}"
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            logger.info("MySQL соединение закрыто")

    # Определяем директорию проекта, где находится manage.py
    project_dir = settings.BASE_DIR

    # Формируем имя файла с текущей датой и временем
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = os.path.join(project_dir, f'parts_export_{timestamp}.csv')

    # Записываем данные в CSV файл
    try:
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            if parts_data:
                # Используем ключи первого словаря как заголовки столбцов
                fieldnames = parts_data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                writer.writerows(parts_data)

                logger.info(f"Данные успешно экспортированы в {csv_filename}")
                return f"Экспортировано {len(parts_data)} записей в файл {os.path.basename(csv_filename)} в директории проекта"
            else:
                return "Нет данных для экспорта"
    except Exception as e:
        logger.error(f"Ошибка при записи в CSV файл: {e}")


@shared_task
def index_products_atomically():
    """
    Задача для атомарной индексации всех товаров в MeiliSearch.
    Очищает индекс и создает его заново.
    """
    try:
        logger.info("Начинаем полную переиндексацию товаров в MeiliSearch")
        
        # Получаем все товары
        products = Product.objects.select_related('brand', 'subgroup__group', 'product_manager').all()
        
        # Очищаем индекс и создаем заново
        ProductIndexer.index_all_atomically()
        
        logger.info(f"Успешно проиндексировано {products.count()} товаров в MeiliSearch")
        return f"Проиндексировано {products.count()} товаров"
        
    except Exception as e:
        logger.error(f"Ошибка при полной индексации товаров: {e}")
        raise


@shared_task
def index_products(product_ids):
    """
    Задача для индексации конкретных товаров по их ID.
    """
    try:
        logger.info(f"Начинаем индексацию товаров с ID: {product_ids}")
        
        # Индексируем товары используя Q-объект
        ProductIndexer.index_from_query(Q(pk__in=product_ids))
        
        logger.info(f"Успешно проиндексировано {len(product_ids)} товаров")
        return f"Проиндексировано {len(product_ids)} товаров"
        
    except Exception as e:
        logger.error(f"Ошибка при индексации товаров {product_ids}: {e}")
        raise


@shared_task
def unindex_products(product_ids):
    """
    Задача для удаления товаров из индекса MeiliSearch.
    """
    try:
        logger.info(f"Начинаем удаление товаров из индекса: {product_ids}")
        
        # Удаляем товары из индекса
        ProductIndexer.unindex_multiple(product_ids)
        
        logger.info(f"Успешно удалено {len(product_ids)} товаров из индекса")
        return f"Удалено {len(product_ids)} товаров из индекса"
        
    except Exception as e:
        logger.error(f"Ошибка при удалении товаров из индекса {product_ids}: {e}")
        raise


@shared_task
def prom_import_brands(username: str | None = None, password: str | None = None, headless: bool = True):
    """
    Логинится на https://office.promelec.ru/ и парсит страницу "Все бренды",
    затем сохраняет бренды в модель stock.CompetitorBrand для конкурента Promelec
    (upsert по паре competitor+name, обновляя ext_id).

    Args:
        username: Логин PROM (если не указан, берётся из переменной окружения PROM_LOGIN)
        password: Пароль PROM (если не указан, берётся из переменной окружения PROM_PASSWORD)
        headless: Запуск браузера Playwright в headless-режиме

    Returns:
        dict: Результат с количеством созданных/обновлённых брендов конкурента
    """
    import re
    import asyncio
    from stock.clients.prom import PromClient, PromAuthError
    from stock.models import Competitor, CompetitorBrand

    user = username or os.getenv("PROM_LOGIN")
    pwd = password or os.getenv("PROM_PASSWORD")
    if not user or not pwd:
        logger.error("Не заданы переменные PROM_LOGIN/PROM_PASSWORD и не переданы аргументы задачи")
        return {"success": False, "error": "PROM_LOGIN/PROM_PASSWORD не заданы"}

    async def _run() -> dict:
        async with PromClient(headless=headless) as client:
            await client.login_and_get_session(user, pwd)
            url = "https://office.promelec.ru/all-brands"
            html, soup = await client.get_and_parse(url)
            anchors = soup.select("section.all-brands a[href^='/all-brands/']")
            # Нормализуем в мапу name -> ext_id (имя — ключ уникальности в CompetitorBrand)
            items: dict[str, str] = {}
            for a in anchors:
                name_raw = a.get_text(" ", strip=True)
                name = name_raw.strip()
                href = a.get("href") or ""
                m = re.search(r"/all-brands/(\d+)", href)
                if not name or not m:
                    continue
                ext_id = m.group(1)
                items[name] = ext_id
            return {"items": items, "count": len(items)}

    try:
        result = asyncio.run(_run())
    except PromAuthError as e:
        logger.error(f"Ошибка авторизации PROM: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Ошибка при получении списка брендов: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

    # Ищем/создаём конкурента для PROM
    competitor, _ = Competitor.objects.get_or_create(
        name="Promelec",
        defaults={
            "site_url": "",
            "b2b_site_url": "https://office.promelec.ru/",
            "is_active": True,
        },
    )
    # Обновим b2b_site_url, если он пустой
    if not competitor.b2b_site_url:
        competitor.b2b_site_url = "https://office.promelec.ru/"
        competitor.save(update_fields=["b2b_site_url"])

    created = 0
    updated = 0
    skipped = 0
    with transaction.atomic():
        for name, ext_id in result["items"].items():
            obj, is_created = CompetitorBrand.objects.update_or_create(
                competitor=competitor,
                name=name,
                defaults={"ext_id": str(ext_id), "is_active": True},
            )
            if is_created:
                created += 1
            else:
                changed_fields: list[str] = []
                if obj.ext_id != str(ext_id):
                    obj.ext_id = str(ext_id)
                    changed_fields.append("ext_id")
                if not obj.is_active:
                    obj.is_active = True
                    changed_fields.append("is_active")
                if changed_fields:
                    obj.save(update_fields=changed_fields)
                    updated += 1
                else:
                    skipped += 1

    msg = {"success": True, "total": result["count"], "created": created, "updated": updated, "skipped": skipped}
    logger.info(f"Импорт брендов PROM (CompetitorBrand) завершён: {msg}")
    return msg

@shared_task
def reindex_products_smart():
    """
    Улучшенная задача для переиндексации товаров с настройками для умного поиска.
    
    Эта задача:
    1. Очищает старый индекс
    2. Применяет обновленные настройки индексации с улучшенными фильтрами
    3. Переиндексирует все товары
    4. Проверяет корректность индексации
    """
    try:
        logger.info("🚀 Начинаем улучшенную переиндексацию товаров в MeiliSearch")
        
        # Импорт здесь чтобы избежать циклических зависимостей при старте
        from meilisearch import Client
        from django.conf import settings
        
        # Подключаемся к MeiliSearch
        client = Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_API_KEY)
        index_name = ProductIndexer.index_name()
        
        # Получаем статистику до переиндексации
        products_count = Product.objects.count()
        st_products_count = Product.objects.filter(brand__name__icontains="ST").count()
        
        logger.info(f"📊 Статистика товаров в БД:")
        logger.info(f"   • Всего товаров: {products_count}")
        logger.info(f"   • ST товаров: {st_products_count}")
        
        # 1. Создаем/обновляем индекс с новыми настройками
        logger.info("🔧 Обновляем настройки индекса...")
        index = client.index(index_name)
        
        # Применяем настройки из ProductIndexer
        settings_update = ProductIndexer.SETTINGS
        logger.info(f"   • Применяем filterable attributes: {settings_update['filterableAttributes']}")
        
        try:
            # Обновляем настройки индекса
            task = index.update_settings(settings_update)
            client.wait_for_task(task.task_uid)
            logger.info("   ✅ Настройки индекса обновлены")
        except Exception as e:
            logger.warning(f"   ⚠️  Не удалось обновить настройки: {e}")
        
        # 2. Очищаем индекс и переиндексируем
        logger.info("🗑️  Очищаем старый индекс...")
        ProductIndexer.index_all_atomically()
        
        # 3. Проверяем результат
        logger.info("🔍 Проверяем результат переиндексации...")
        
        # Ждем немного для завершения индексации
        import time
        time.sleep(2)
        
        try:
            # Проверяем количество документов в индексе
            index_info = index.get_stats()
            indexed_count = index_info.number_of_documents
            
            logger.info(f"✅ Переиндексация завершена:")
            logger.info(f"   • Документов в индексе: {indexed_count}")
            logger.info(f"   • Покрытие: {(indexed_count/products_count*100):.1f}%" if products_count > 0 else "   • Покрытие: N/A")
            
            # Тестируем поиск ST товаров
            test_result = index.search("ST", {"filter": 'brand_name = "ST"', "limit": 1})
            st_found = test_result.estimated_total_hits
            logger.info(f"   • ST товаров найдено при тесте: {st_found}")
            
            success_message = f"Переиндексировано {indexed_count} товаров. ST товаров найдено: {st_found}"
            
        except Exception as e:
            logger.warning(f"⚠️  Не удалось получить статистику индекса: {e}")
            success_message = f"Переиндексация завершена (статистика недоступна)"
        
        logger.info(f"🎉 {success_message}")
        return success_message
        
    except Exception as e:
        error_msg = f"Ошибка при улучшенной переиндексации товаров: {e}"
        logger.error(f"❌ {error_msg}")
        raise 


@shared_task
def export_products_by_typecode(typecode):
    """
    Celery-задача для экспорта описательных свойств товаров по ID подгруппы (typecode) в Excel файл.
    Возвращает словарь с бинарным содержимым файла вместо пути.
    """
    connection = None
    try:
        connection = mysql.connector.connect(**mysql_config)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
           
            # Выполняем SQL запрос с фильтрацией по typecode
            query = """
            SELECT
                mainbase.id AS 'Артикул',
                CASE 
                    WHEN LEFT(TRIM(REVERSE(gg.tovgroup)), 1) = '*' 
                    THEN TRIM(REVERSE(SUBSTRING(TRIM(REVERSE(gg.tovgroup)), 2))) 
                    ELSE gg.tovgroup 
                END AS 'Группа',
                gg.tovmark AS 'Подгруппа',
                mainwide.head AS 'Тип продукции',
                mainwide.brand AS 'Брэнд',
                mainbase.tovmark AS 'Простое название',
                mainwide.complex AS 'Комплексное название',
                mainwide.description AS 'Описание',
                mainwide.keywords AS 'Ключевые слова'
            FROM groupsb gg
            JOIN mainbase ON mainbase.mgroup = gg.mgroup
            LEFT JOIN mainwide ON mainwide.mainbase = mainbase.id
            WHERE gg.mgroup = %s
            AND mainbase.ruelsite <> 0
            ORDER BY 3, 4, 7
            """
            cursor.execute(query, (typecode,))
            products = cursor.fetchall()
           
            if not products:
                logger.warning(f"Нет данных для typecode={typecode}")
                return {
                    'success': False,
                    'error': f"Нет данных для указанного typecode: {typecode}"
                }
        else:
            logger.error("MySQL-соединение не установлено")
            return {
                'success': False,
                'error': "Ошибка: не удалось подключиться к базе данных"
            }
    except Error as e:
        logger.error(f"Ошибка при подключении к MySQL: {e}")
        return {
            'success': False,
            'error': f"Ошибка при работе с базой данных: {str(e)}"
        }
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
   
    # Создаем Excel файл в памяти
    try:
        # Создаем DataFrame
        df = pd.DataFrame(products)
        
        # Удаляем временную колонку @rev
        if '@rev' in df.columns:
            df = df.drop(columns=['@rev'])
        
        # Вместо сохранения на диск используем BytesIO
        excel_buffer = BytesIO()
        
        # Сохраняем данные в буфер
        df.to_excel(excel_buffer, sheet_name='Товары', index=False)
        
        # Получаем содержимое буфера
        excel_buffer.seek(0)
        file_data = excel_buffer.getvalue()
        
        # Преобразуем бинарные данные в base64 для безопасной передачи через JSON
        encoded_data = base64.b64encode(file_data).decode('utf-8')
        
        # Формируем результат
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"products_typecode_{typecode}_{timestamp}.xlsx"
        
        logger.info(f"Создан Excel файл в памяти для typecode={typecode} с {len(products)} записями")
        
        return {
            'success': True,
            'filename': filename,
            'data': encoded_data,
            'records': len(products)
        }
    except Exception as e:
        logger.error(f"Ошибка при создании Excel-файла: {e}")
        return {
            'success': False,
            'error': f"Ошибка при создании Excel-файла: {str(e)}"
        }


@shared_task
def export_products_by_filters(subgroup_ids=None, brand_names=None, only_two_params=False, no_description=False):
    """
    Celery-задача для экспорта описательных свойств товаров с фильтрацией 
    по подгруппам, брендам, количеству технических параметров и наличию описания в Excel файл.
    
    Args:
        subgroup_ids (list): Список ext_id подгрупп для фильтрации (может быть None для всех)
        brand_names (list): Список названий брендов для фильтрации (может быть None для всех)  
        only_two_params (bool): Если True, экспортируются только товары с двумя техническими параметрами
        no_description (bool): Если True, экспортируются только товары без описания
    
    Returns:
        dict: Словарь с результатом экспорта и бинарным содержимым файла
    """
    connection = None
    try:
        connection = mysql.connector.connect(**mysql_config)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
           
            # Базовый SQL запрос
            base_query = """
            SELECT
                mainbase.id AS 'Артикул',
                CASE 
                    WHEN LEFT(TRIM(REVERSE(gg.tovgroup)), 1) = '*' 
                    THEN TRIM(REVERSE(SUBSTRING(TRIM(REVERSE(gg.tovgroup)), 2))) 
                    ELSE gg.tovgroup 
                END AS 'Группа',
                gg.tovmark AS 'Подгруппа',
                mainwide.head AS 'Тип продукции',
                mainwide.brand AS 'Брэнд',
                mainbase.tovmark AS 'Простое название',
                mainwide.complex AS 'Комплексное название',
                mainwide.description AS 'Описание',
                mainwide.keywords AS 'Ключевые слова'
            FROM groupsb gg
            JOIN mainbase ON mainbase.mgroup = gg.mgroup
            LEFT JOIN mainwide ON mainwide.mainbase = mainbase.id
            WHERE mainbase.ruelsite <> 0
            """
            
            # Добавляем условия фильтрации
            where_conditions = []
            query_params = []
            
            if subgroup_ids:
                # Фильтр по подгруппам
                placeholders = ', '.join(['%s'] * len(subgroup_ids))
                where_conditions.append(f"gg.mgroup IN ({placeholders})")
                query_params.extend(subgroup_ids)
            
            if brand_names:
                # Фильтр по брендам
                placeholders = ', '.join(['%s'] * len(brand_names))
                where_conditions.append(f"mainwide.brand IN ({placeholders})")
                query_params.extend(brand_names)
            
            if only_two_params:
                # Фильтр по количеству технических параметров (ровно 2)
                tech_params_filter = """
                    (SELECT COUNT(*) 
                     FROM metrinfo t 
                     JOIN metrics tp ON t.metrics = tp.id 
                     WHERE t.mainbase = mainbase.id) = 2
                """
                where_conditions.append(tech_params_filter)
            
            if no_description:
                # Фильтр для товаров без описания (пустое или NULL описание)
                no_description_filter = "(mainwide.description IS NULL OR TRIM(mainwide.description) = '')"
                where_conditions.append(no_description_filter)
            
            # Собираем финальный запрос
            if where_conditions:
                query = base_query + " AND " + " AND ".join(where_conditions)
            else:
                query = base_query
                
            query += " ORDER BY 3, 4, 7"
            
            logger.info(f"Выполняем SQL запрос с параметрами: subgroups={subgroup_ids}, brands={brand_names}, only_two_params={only_two_params}, no_description={no_description}")
            cursor.execute(query, query_params)
            products = cursor.fetchall()
           
            if not products:
                logger.warning("Нет данных для экспорта с заданными фильтрами")
                return {
                    'success': False,
                    'error': "Нет данных для экспорта с заданными фильтрами"
                }
        else:
            logger.error("MySQL-соединение не установлено")
            return {
                'success': False,
                'error': "Ошибка: не удалось подключиться к базе данных"
            }
    except Error as e:
        logger.error(f"Ошибка при подключении к MySQL: {e}")
        return {
            'success': False,
            'error': f"Ошибка при работе с базой данных: {str(e)}"
        }
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
   
    # Создаем Excel файл в памяти
    try:
        # Создаем DataFrame
        df = pd.DataFrame(products)
        
        # Удаляем временную колонку @rev если есть
        if '@rev' in df.columns:
            df = df.drop(columns=['@rev'])
        
        # Используем BytesIO для создания файла в памяти
        excel_buffer = BytesIO()
        
        # Сохраняем данные в буфер
        df.to_excel(excel_buffer, sheet_name='Товары', index=False)
        
        # Получаем содержимое буфера
        excel_buffer.seek(0)
        file_data = excel_buffer.getvalue()
        
        # Преобразуем бинарные данные в base64 для безопасной передачи через JSON
        encoded_data = base64.b64encode(file_data).decode('utf-8')
        
        # Формируем результат
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Создаем описательное имя файла
        filename_parts = ["products"]
        if subgroup_ids:
            filename_parts.append(f"subgroups_{len(subgroup_ids)}")
        if brand_names:
            filename_parts.append(f"brands_{len(brand_names)}")
        if only_two_params:
            filename_parts.append("2params")
        if no_description:
            filename_parts.append("no_desc")
        filename_parts.append(timestamp)
        
        filename = f"{'_'.join(filename_parts)}.xlsx"
        
        logger.info(f"Создан Excel файл в памяти с {len(products)} записями. Фильтры: подгруппы={subgroup_ids}, бренды={brand_names}, only_two_params={only_two_params}, no_description={no_description}")
        
        return {
            'success': True,
            'filename': filename,
            'data': encoded_data,
            'records': len(products),
            'filters': {
                'subgroups': subgroup_ids or [],
                'brands': brand_names or [],
                'only_two_params': only_two_params,
                'no_description': no_description
            }
        }
    except Exception as e:
        logger.error(f"Ошибка при создании Excel-файла: {e}")
        return {
            'success': False,
            'error': f"Ошибка при создании Excel-файла: {str(e)}"
        }


@shared_task
def assign_product_managers():
    """
    Celery-задача для автоматического назначения менеджеров товарам без менеджера.

    Алгоритм:
    1. Находит все товары без менеджера
    2. Группирует их по подгруппам
    3. Для каждой подгруппы находит менеджера, у которого больше всего товаров в этой подгруппе
    4. Устанавливает этого менеджера на товары без менеджера в данной подгруппе
    """
    try:
        logger.info("Начинаем автоматическое назначение менеджеров товарам")

        # Получаем всех менеджеров (пользователей с ролью PURCHASER)
        managers = User.objects.filter(role=User.Role.PURCHASER)
        if not managers.exists():
            logger.warning("Не найдено ни одного менеджера для назначения")
            return "Не найдено менеджеров для назначения"

        # Находим товары без менеджера
        products_without_manager = Product.objects.filter(product_manager__isnull=True).select_related('subgroup')
        if not products_without_manager.exists():
            logger.info("Все товары уже имеют назначенных менеджеров")
            return "Все товары уже имеют менеджеров"

        total_products = products_without_manager.count()
        logger.info(f"Найдено {total_products} товаров без менеджера")

        # Группируем товары по подгруппам
        products_by_subgroup = {}
        for product in products_without_manager:
            subgroup_id = product.subgroup_id
            if subgroup_id not in products_by_subgroup:
                products_by_subgroup[subgroup_id] = []
            products_by_subgroup[subgroup_id].append(product)

        logger.info(f"Товары сгруппированы по {len(products_by_subgroup)} подгруппам")

        assigned_count = 0

        # Обрабатываем каждую подгруппу
        with transaction.atomic():
            for subgroup_id, products in products_by_subgroup.items():
                # Находим менеджера с наибольшим количеством товаров в этой подгруппе
                manager_stats = (
                    Product.objects.filter(subgroup_id=subgroup_id, product_manager__isnull=False)
                    .values('product_manager')
                    .annotate(product_count=Count('id'))
                    .order_by('-product_count')
                )

                if manager_stats.exists():
                    # Берем менеджера с максимальным количеством товаров
                    top_manager_id = manager_stats.first()['product_manager']
                    try:
                        top_manager = User.objects.get(id=top_manager_id, role=User.Role.PURCHASER)
                    except User.DoesNotExist:
                        logger.warning(f"Менеджер с ID {top_manager_id} не найден или не является менеджером, пропускаем подгруппу {subgroup_id}")
                        continue

                    # Назначаем этого менеджера всем товарам без менеджера в подгруппе
                    product_ids = [p.id for p in products]
                    updated_count = Product.objects.filter(
                        id__in=product_ids,
                        product_manager__isnull=True
                    ).update(product_manager=top_manager)

                    assigned_count += updated_count
                    logger.info(f"Подгруппа {subgroup_id}: назначен менеджер {top_manager.username} для {updated_count} товаров")
                else:
                    logger.warning(f"В подгруппе {subgroup_id} нет товаров с менеджерами, пропускаем")

        logger.info(f"Автоматическое назначение менеджеров завершено. Назначено: {assigned_count} товаров")
        return f"Назначено менеджеров для {assigned_count} товаров из {total_products} без менеджера"

    except Exception as e:
        logger.error(f"Ошибка при автоматическом назначении менеджеров: {e}")
        raise