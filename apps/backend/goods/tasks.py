import os
import json
import logging
import mysql.connector
from celery import shared_task
from django.db import transaction
from django.db.models import Q
from mysql.connector import Error
from django.conf import settings
from api.models import User
from goods.indexers import ProductIndexer
from goods.models import Brand, Product, ProductGroup, ProductSubgroup

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