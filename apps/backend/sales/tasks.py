import logging
import os
import pandas as pd
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError
from celery import shared_task
from .models import Invoice, InvoiceLine
from customers.models import Company
from goods.models import Product, ProductSubgroup, ProductGroup, Brand

logger = logging.getLogger(__name__)

# Конфигурация подключения к MySQL (должна быть в settings)
mysql_config = {
    "host": os.getenv("MYSQL_HOST"),
    "port": os.getenv("MYSQL_PORT"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASS"),
    "database": os.getenv("MYSQL_DB"),
    "charset": os.getenv("MYSQL_CHARSET"),
}


@shared_task
def update_sales_from_mysql():
    """
    Оптимизированная Celery-задача для загрузки миллионов записей о продажах из удалённой MySQL в локальную базу Django.
    Получает данные из таблиц listdoc и chek, преобразует их в объекты Invoice и InvoiceLine.
    Определяет тип продажи по наличию слова "заказ" в поле prim таблицы listdoc.
    """
    connection = None
    try:
        connection = mysql.connector.connect(**mysql_config)
        if connection.is_connected():
            # Используем пагинацию для получения данных большими блоками
            BATCH_SIZE = 100000
            offset = 0
            total_sales_data = []

            while True:
                cursor = connection.cursor(dictionary=True)  # Создаем новый курсор для каждого запроса

                # Выполняем SQL-запрос с LIMIT и OFFSET для пагинации
                query = """
                SELECT
                   l.idklient,
                   l.moment,
                   c.tovmark,
                   c.tovcode,
                   cast(c.prise * (1-c.proc4/100) as decimal(15,2)) as prise,
                   c.fost,
                   c.idlist,
                   l.prim,
                   l.id as listdoc_id
                FROM
                   listdoc l
                INNER JOIN
                   chek c ON l.id = c.idlist
                WHERE
                   l.g1 < 3
                   AND (l.g1 = 1 OR l.cf > 0)
                   AND l.year > 2024
                   AND l.idklient != 14783
                LIMIT %s OFFSET %s;
                """
                cursor.execute(query, (BATCH_SIZE, offset))
                batch_data = cursor.fetchall()
                cursor.close()  # Закрываем курсор после извлечения всех данных

                if not batch_data:
                    break  # Выходим из цикла, если больше нет данных

                total_sales_data.extend(batch_data)
                offset += BATCH_SIZE

                logger.info(f"Получено {len(batch_data)} записей (всего: {len(total_sales_data)})")

            if not total_sales_data:
                logger.warning("MySQL-запрос не вернул данных о продажах")
                return "Нет данных о продажах для обновления"
        else:
            logger.error("MySQL-соединение не установлено")
            return "Не удалось установить соединение с MySQL"
    except Error as e:
        logger.error(f"Ошибка при подключении к MySQL: {e}")
        return f"Ошибка при получении данных о продажах: {e}"
    finally:
        if connection and connection.is_connected():
            connection.close()
            logger.info("MySQL-соединение закрыто")

    # Счетчики для отчета
    invoices_created = 0
    invoices_updated = 0
    lines_created = 0
    lines_updated = 0
    skipped_items = 0

    # Предварительно кэшируем все необходимые справочные данные
    logger.info("Начинаем кэширование справочных данных...")

    # Получаем все уникальные ID клиентов из импортируемых данных для фильтрации
    client_ids = set()
    for item in total_sales_data:
        if item['idklient']:
            # Унифицируем тип данных - преобразуем все к строке
            client_ids.add(str(item['idklient']))

    logger.info(f"Найдено {len(client_ids)} уникальных клиентов в импортируемых данных")

    # Кэшируем только компании, которые встречаются в данных
    existing_companies = {}
    if client_ids:
        for cp in Company.objects.filter(ext_id__in=client_ids):
            # Ключевое улучшение - всегда преобразуем ext_id к строке для единообразия
            existing_companies[str(cp.ext_id)] = cp

    logger.info(f"Загружено {len(existing_companies)} существующих компаний")
    # Логи для диагностики
    if len(existing_companies) > 0:
        first_keys = list(existing_companies.keys())[:5]
        logger.info(f"Примеры ключей компаний в кэше: {first_keys}")

    # Получаем все уникальные коды товаров
    product_codes = set()
    for item in total_sales_data:
        if item['tovcode']:
            # Унифицируем тип данных - преобразуем все к строке
            product_codes.add(str(item['tovcode']))

    logger.info(f"Найдено {len(product_codes)} уникальных товаров в импортируемых данных")

    # Кэшируем только товары, которые встречаются в данных
    existing_products = {}
    if product_codes:
        for prod in Product.objects.filter(ext_id__in=product_codes):
            # Ключевое улучшение - всегда преобразуем ext_id к строке для единообразия
            existing_products[str(prod.ext_id)] = prod

    logger.info(f"Загружено {len(existing_products)} существующих товаров")

    # Логи для диагностики
    if len(existing_products) > 0:
        first_keys = list(existing_products.keys())[:5]
        logger.info(f"Примеры ключей товаров в кэше: {first_keys}")

    # Получаем все уникальные ID счетов
    invoice_ids = set()
    for item in total_sales_data:
        if item['listdoc_id'] is not None:
            # Унифицируем тип данных - преобразуем все к строке
            invoice_ids.add(str(item['listdoc_id']))

    logger.info(f"Найдено {len(invoice_ids)} уникальных счетов в импортируемых данных")

    # Кэшируем только счета, которые встречаются в данных
    existing_invoices = {}
    if invoice_ids:
        for inv in Invoice.objects.filter(ext_id__in=invoice_ids):
            # Ключевое улучшение - всегда преобразуем ext_id к строке для единообразия
            existing_invoices[str(inv.ext_id)] = inv

    logger.info(f"Загружено {len(existing_invoices)} существующих счетов")

    # Логи для диагностики
    if len(existing_invoices) > 0:
        first_keys = list(existing_invoices.keys())[:5]
        logger.info(f"Примеры ключей счетов в кэше: {first_keys}")

    # Получаем или создаем временные объекты для неизвестных товаров заранее
    unknown_subgroup, _ = ProductSubgroup.objects.get_or_create(
        ext_id='-1',
        defaults={
            'name': 'Неизвестная подгруппа',
            'group': ProductGroup.objects.get_or_create(
                ext_id='-1',
                defaults={'name': 'Неизвестная группа'}
            )[0]
        }
    )

    unknown_brand, _ = Brand.objects.get_or_create(
        ext_id='-1',
        defaults={'name': 'Неизвестный бренд'}
    )

    # Группируем данные по номеру счета (listdoc_id)
    invoices_by_id = {}
    for item in total_sales_data:
        invoice_id = item['listdoc_id']
        if invoice_id is None:
            skipped_items += 1
            continue

        # Унифицируем тип данных - преобразуем к строке
        invoice_id_str = str(invoice_id)

        if invoice_id_str not in invoices_by_id:
            invoices_by_id[invoice_id_str] = {
                'header': item,
                'lines': []
            }

        # Добавляем строку, если есть код товара и цена
        # Проверяем только tovcode и prise, fost может быть 0
        if item['tovcode'] and item['prise'] is not None:
            # Добавляем защиту от None в fost
            if item['fost'] is None:
                item['fost'] = 0
            invoices_by_id[invoice_id_str]['lines'].append(item)

        # Отладочное логирование для первых нескольких записей
        if len(invoices_by_id) <= 5:
            logger.info(f"Пример записи: {item}")

    # Подготавливаем массивы объектов для пакетной обработки
    new_companies = []
    new_products = []
    new_invoices = []
    new_invoice_lines = []

    # Сначала обработаем компании и товары, которых нет в базе
    # Затем создадим счета и строки счетов пакетно

    # Шаг 1: Подготовка новых компаний
    companies_to_create = {}
    for invoice_id_str, invoice_data in invoices_by_id.items():
        header = invoice_data['header']
        lines = invoice_data['lines']

        if not lines:
            logger.warning(f"Счет {invoice_id_str} не имеет строк с товарами, пропускаем")
            skipped_items += 1
            continue

        # Обрабатываем компанию
        if header['idklient']:
            # Унифицируем тип данных
            client_id_str = str(header['idklient'])
            if client_id_str not in existing_companies:
                companies_to_create[client_id_str] = Company(
                    ext_id=client_id_str,
                    name=f"Клиент #{client_id_str}",
                    company_type=Company.CompanyTypeChoices.END_USER
                )

    # Пакетно создаем компании
    if companies_to_create:
        # Дополнительная проверка существующих компаний непосредственно перед созданием
        existing_ext_ids = set(Company.objects.filter(
            ext_id__in=list(companies_to_create.keys())
        ).values_list('ext_id', flat=True))

        # Преобразуем к строкам для единообразия
        existing_ext_ids = set(str(ext_id) for ext_id in existing_ext_ids)

        # Удаляем уже существующие компании из списка создаваемых
        for ext_id in existing_ext_ids:
            if ext_id in companies_to_create:
                del companies_to_create[ext_id]

        # Создаем только новые компании с игнорированием конфликтов
        if companies_to_create:
            Company.objects.bulk_create(
                companies_to_create.values(),
                batch_size=1000,
                ignore_conflicts=True  # Игнорировать дубликаты
            )

        # Обновляем кэш компаний всех необходимых записей
        # (и новых, и тех, что уже существовали)
        all_needed_ids = list(companies_to_create.keys()) + list(existing_ext_ids)
        if all_needed_ids:
            for cp in Company.objects.filter(ext_id__in=all_needed_ids):
                existing_companies[str(cp.ext_id)] = cp

    # Шаг 3: Обработка счетов и строк пакетами
    invoice_objects_to_create = []
    invoice_objects_to_update = []

    # Выведем количество счетов для обработки
    logger.info(f"Начинаем обработку {len(invoices_by_id)} счетов")

    # Счетчик для отладки
    processed_count = 0

    # Подготавливаем счета и их строки
    skipped_no_klient = 0
    skipped_no_lines = 0
    skipped_no_company = 0

    # Словарь для хранения строк счетов по ext_id счета
    invoice_lines_by_invoice_ext_id = {}

    for invoice_id_str, invoice_data in invoices_by_id.items():
        header = invoice_data['header']
        lines = invoice_data['lines']

        # Отладочная информация для первых 10 счетов
        if processed_count < 10:
            logger.info(f"Проверка счета {invoice_id_str}: idklient={header['idklient']}, строк={len(lines)}")

        if not header['idklient']:
            skipped_no_klient += 1
            if processed_count < 10:
                logger.info(f"Счет {invoice_id_str} пропущен: нет idklient")
            continue

        if not lines:
            skipped_no_lines += 1
            if processed_count < 10:
                logger.info(f"Счет {invoice_id_str} пропущен: нет строк")
            continue

        # Логика определения компании - используем унифицированные строковые ключи
        client_id_str = str(header['idklient'])
        company = existing_companies.get(client_id_str)

        if not company:
            skipped_no_company += 1
            if processed_count < 10:
                logger.warning(f"Счет {invoice_id_str} пропущен: не найдена компания {client_id_str}")

                # Дополнительное логирование для отладки
                logger.warning(f"Доступные ключи в кэше компаний: {list(existing_companies.keys())[:20]}")
                if client_id_str in existing_companies:
                    logger.warning(f"Компания найдена в кэше, но почему-то не определилась при поиске!")
            continue

        # Определяем тип продажи на основе поля prim
        sale_type = Invoice.SaleType.STOCK  # По умолчанию - со склада
        if header['prim'] and 'заказ' in header['prim'].lower():
            sale_type = Invoice.SaleType.ORDER  # Под заказ

        # Формируем номер счета на основе ID
        invoice_number = f"S-{invoice_id_str}"
        invoice_date = header['moment']

        # Проверяем существование счета - используем унифицированные строковые ключи
        if invoice_id_str in existing_invoices:
            # Счет существует - обновляем
            invoice = existing_invoices[invoice_id_str]
            invoice.invoice_number = invoice_number
            invoice.invoice_date = invoice_date
            invoice.company = company
            invoice.sale_type = sale_type
            invoice_objects_to_update.append(invoice)
            invoices_updated += 1
        else:
            # Счет не существует - создаем
            try:
                invoice = Invoice(
                    ext_id=invoice_id_str,  # Используем строковую версию
                    invoice_number=invoice_number,
                    invoice_date=invoice_date,
                    company=company,
                    invoice_type=Invoice.InvoiceType.SALE,
                    sale_type=sale_type,
                    currency=Invoice.Currency.RUB
                )
                invoice_objects_to_create.append(invoice)
                invoices_created += 1
            except Exception as e:
                logger.error(f"Ошибка при создании счета {invoice_id_str}: {e}")
                continue

        # Отладочный вывод по первым нескольким счетам
        processed_count += 1
        if processed_count <= 5:
            logger.info(f"Обработан счет {invoice_id_str}, строк: {len(lines)}, создается: {invoice_id_str not in existing_invoices}")

        # Обрабатываем строки счета
        invoice_lines = []

        for line in lines:
            if not line['tovcode'] or line['prise'] is None:
                continue

            # Унифицируем тип данных - преобразуем к строке
            tovcode_str = str(line['tovcode'])
            product = existing_products.get(tovcode_str)

            if not product:
                if processed_count < 10:
                    logger.warning(f"Товар с кодом {tovcode_str} не найден в кэше")
                continue

            price = float(line['prise']) if line['prise'] is not None else 0
            quantity = int(line['fost']) if line['fost'] is not None else 0

            # Сохраняем информацию для создания строки счета
            invoice_lines.append({
                'product': product,
                'ext_id': f"{invoice_id_str}-{tovcode_str}",
                'quantity': quantity,
                'price': price
            })

        # Добавляем все строки данного счета в словарь по ext_id счета
        if invoice_lines:
            invoice_lines_by_invoice_ext_id[invoice_id_str] = invoice_lines

    try:
        # ВАЖНОЕ ИЗМЕНЕНИЕ: Разделяем транзакции на два независимых блока
        # Первая транзакция: создание и обновление счетов
        with transaction.atomic():
            # Предварительная проверка перед созданием/обновлением
            logger.info(f"Подготовлено счетов к созданию: {len(invoice_objects_to_create)}")
            logger.info(f"Подготовлено счетов к обновлению: {len(invoice_objects_to_update)}")
            logger.info(f"Статистика пропущенных счетов: без клиента: {skipped_no_klient}, без строк: {skipped_no_lines}, без компании: {skipped_no_company}")

            # Проверяем, есть ли что создавать
            if not invoice_objects_to_create and not invoice_objects_to_update:
                logger.warning("Нет счетов для создания или обновления. Проверьте условия фильтрации.")
                return "Нет счетов для обновления после фильтрации"

            # Обновляем существующие счета
            if invoice_objects_to_update:
                logger.info(f"Обновляем {len(invoice_objects_to_update)} существующих счетов")
                Invoice.objects.bulk_update(
                    invoice_objects_to_update,
                    ['invoice_number', 'invoice_date', 'company', 'sale_type'],
                    batch_size=1000
                )

            # Создаем новые счета
            if invoice_objects_to_create:
                logger.info(f"Создаем {len(invoice_objects_to_create)} новых счетов")
                # Создаем небольшими пакетами на случай большого количества
                batch_size = 1000
                for i in range(0, len(invoice_objects_to_create), batch_size):
                    batch = invoice_objects_to_create[i:i+batch_size]
                    logger.info(f"Создаю пакет счетов {i+1}-{i+len(batch)} из {len(invoice_objects_to_create)}")
                    Invoice.objects.bulk_create(batch, batch_size=batch_size, ignore_conflicts=True)

        # ВАЖНОЕ ИЗМЕНЕНИЕ: Вторая транзакция для создания строк
        # К этому моменту первая транзакция уже завершена и счета созданы в базе
        with transaction.atomic():
            # Удаляем старые строки счетов для обновляемых счетов
            if invoice_objects_to_update:
                invoice_ext_ids = [str(inv.ext_id) for inv in invoice_objects_to_update]
                logger.info(f"Удаление старых строк счетов для {len(invoice_ext_ids)} обновляемых счетов")
                # Делаем удаление небольшими пакетами, если много счетов
                batch_size = 1000
                for i in range(0, len(invoice_ext_ids), batch_size):
                    batch = invoice_ext_ids[i:i+batch_size]
                    InvoiceLine.objects.filter(invoice__ext_id__in=batch).delete()

            # Получаем все ext_id из нашего списка счетов
            all_invoice_ext_ids = list(invoice_lines_by_invoice_ext_id.keys())

            if not all_invoice_ext_ids:
                logger.warning("Нет данных о строках счетов для создания")
                return "Обработка завершена: нет строк счетов для создания"

            logger.info(f"Запрашиваем данные о {len(all_invoice_ext_ids)} счетах из базы данных")

            # Получаем соответствие ext_id -> id для всех счетов
            ext_id_to_id_map = {}

            # Делаем запрос пакетами
            batch_size = 1000
            for i in range(0, len(all_invoice_ext_ids), batch_size):
                batch = all_invoice_ext_ids[i:i+batch_size]

                # Используем values() для получения только нужных полей
                mapping_query = Invoice.objects.filter(ext_id__in=batch).values('id', 'ext_id')

                for item in mapping_query:
                    # Сохраняем соответствие: str(ext_id) -> id
                    ext_id_to_id_map[str(item['ext_id'])] = item['id']

            logger.info(f"Получено маппингов ext_id -> id: {len(ext_id_to_id_map)}")

            # Проверяем, какие ext_id не найдены в базе
            missing_ext_ids = [ext_id for ext_id in all_invoice_ext_ids
                              if ext_id not in ext_id_to_id_map]

            if missing_ext_ids:
                logger.warning(f"Не найдено {len(missing_ext_ids)} счетов в базе данных")
                if len(missing_ext_ids) <= 20:
                    logger.warning(f"Отсутствующие ext_id: {missing_ext_ids}")
                else:
                    logger.warning(f"Примеры отсутствующих ext_id: {missing_ext_ids[:20]}")

                # Проверим, существуют ли счета с такими ext_id в другом формате
                for missing_id in missing_ext_ids[:5]:
                    # Проверяем как число, если возможно
                    try:
                        numeric_id = int(missing_id)
                        exists_as_int = Invoice.objects.filter(ext_id=numeric_id).exists()
                        if exists_as_int:
                            logger.info(f"Счет с ext_id={missing_id} существует как int, но не найден как string")
                    except ValueError:
                        pass

            # Создаем строки счетов пакетно
            all_invoice_lines = []

            for ext_id, lines_data in invoice_lines_by_invoice_ext_id.items():
                # Получаем ID счета из маппинга
                invoice_id = ext_id_to_id_map.get(ext_id)

                if not invoice_id:
                    logger.warning(f"Не найден ID для счета с ext_id={ext_id}, пропускаем создание строк")
                    continue

                # Создаем строки для этого счета, используя ID вместо объекта
                for line_data in lines_data:
                    try:
                        invoice_line = InvoiceLine(
                            invoice_id=invoice_id,  # Используем ID вместо объекта
                            product=line_data['product'],
                            ext_id=line_data['ext_id'],
                            quantity=line_data['quantity'],
                            price=line_data['price']
                        )
                        all_invoice_lines.append(invoice_line)
                        lines_created += 1
                    except Exception as e:
                        logger.error(f"Ошибка при создании строки счета для ext_id={ext_id}: {e}")

            # Создаем строки счетов
            if all_invoice_lines:
                # Разбиваем на пакеты, так как могут быть миллионы записей
                batch_size = 10000
                logger.info(f"Создаём {len(all_invoice_lines)} строк счетов пакетами по {batch_size}")

                for i in range(0, len(all_invoice_lines), batch_size):
                    batch = all_invoice_lines[i:i+batch_size]
                    logger.info(f"Создаю пакет строк {i+1}-{i+len(batch)} из {len(all_invoice_lines)}")
                    InvoiceLine.objects.bulk_create(batch, batch_size=1000, ignore_conflicts=True)
            else:
                logger.warning("Не создано ни одной строки счета! Проверьте логику создания.")

        logger.info(
            f"Обновлены данные о продажах: счета {invoices_created} (создано)/{invoices_updated} (обновлено), "
            f"строки {lines_created} (создано), "
            f"пропущено: {skipped_items}"
        )
    except Exception as e:
        logger.error(f"Ошибка при обновлении данных о продажах: {e}")
        return f"Ошибка при обновлении данных: {e}"

    return (
        f"Обновлено данных о продажах:\n"
        f"Счета: создано {invoices_created}, обновлено {invoices_updated}\n"
        f"Строки: создано {lines_created}\n"
        f"Пропущено элементов: {skipped_items}"
    )


@shared_task
def export_sales_to_excel(year_from=2022, exclude_client_id=14783):
    """
    Celery-задача для экспорта данных о продажах в Excel файл.

    Excel файл будет сохранен в корневой директории проекта (рядом с manage.py).

    Parameters:
    year_from (int): Минимальный год для выборки данных (по умолчанию 2022)
    exclude_client_id (int): ID клиента, которого нужно исключить из выборки (по умолчанию 14783)

    Returns:
    str: Сообщение о результате операции
    """
    connection = None
    try:
        connection = mysql.connector.connect(**mysql_config)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)

            # Выполняем SQL запрос для получения данных о продажах
            query = """
            SELECT
                l.id,
                l.g1,
                l.idklient,
                k.kontr1,
                l.moment,
                c.tovmark,
                c.tovcode,
                c.prise,
                cast(c.prise * (1-c.proc4/100) as decimal(15,2)) as discounted_price,
                c.fost,
                l.year
            FROM
                listdoc l
            INNER JOIN
                chek c ON l.id = c.idlist
            INNER JOIN
                kontr k ON l.idklient = k.id
            WHERE
                l.g1 < 3
                AND (l.g1 = 1 OR l.cf > 0)
                AND l.year > %s
            """

            params = [year_from]

            if exclude_client_id is not None:
                query += " AND l.idklient != %s"
                params.append(exclude_client_id)

            # Добавляем сортировку для удобства анализа
            query += " ORDER BY l.moment DESC"

            cursor.execute(query, params)
            sales_data = cursor.fetchall()

            if not sales_data:
                logger.warning(f"Нет данных о продажах для указанных параметров")
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

    # Обработка данных и создание Excel файла с помощью pandas
    try:
        # Создаем DataFrame
        df = pd.DataFrame(sales_data)

        # Переименовываем колонки для лучшей читаемости
        column_mapping = {
            'id': 'ID документа',
            'g1': 'Тип документа',
            'idklient': 'ID клиента',
            'kontr1': 'Наименование клиента',
            'moment': 'Дата/время',
            'tovmark': 'Наименование товара',
            'tovcode': 'Код товара',
            'prise': 'Цена',
            'discounted_price': 'Цена со скидкой',
            'fost': 'Количество',
            'year': 'Год'
        }
        df = df.rename(columns=column_mapping)

        # Добавляем расчетный столбец для суммы
        df['Сумма'] = df['Цена со скидкой'] * df['Количество']

        # Определяем директорию проекта, где находится manage.py
        # settings.BASE_DIR обычно указывает на директорию проекта
        project_dir = settings.BASE_DIR

        # Формируем имя файла с текущей датой и временем
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = os.path.join(project_dir, f'sales_export_{timestamp}.xlsx')

        # Сохраняем данные в Excel файл
        df.to_excel(excel_filename, sheet_name='Продажи', index=False)

        logger.info(f"Данные о продажах успешно экспортированы в Excel файл: {excel_filename}")
        return f"Экспортировано {len(sales_data)} записей в файл {os.path.basename(excel_filename)} в директории проекта"
    except Exception as e:
        logger.error(f"Ошибка при создании Excel-файла: {e}")
        return f"Ошибка экспорта: {str(e)}"


@shared_task
def export_company_sales_to_excel(company_id, date_from=None, date_to=None, user_id=None):
    """
    Celery-задача для экспорта продаж конкретной компании в Excel.
    
    Parameters:
    company_id (int): ID компании
    date_from (str): Начальная дата в формате YYYY-MM-DD
    date_to (str): Конечная дата в формате YYYY-MM-DD
    user_id (int): ID пользователя, запросившего экспорт
    
    Returns:
    str: Путь к созданному файлу или сообщение об ошибке
    """
    try:
        # Получаем компанию
        company = Company.objects.get(id=company_id)
        
        # Формируем запрос
        queryset = Invoice.objects.filter(
            company=company,
            invoice_type=Invoice.InvoiceType.SALE
        ).prefetch_related('lines__product')
        
        # Применяем фильтры по датам
        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)
        
        if not queryset.exists():
            return "Нет данных для экспорта с указанными параметрами"
        
        # Подготавливаем данные
        data = []
        for invoice in queryset:
            for line in invoice.lines.all():
                data.append({
                    'Номер счета': invoice.invoice_number,
                    'Дата счета': invoice.invoice_date,
                    'Компания': invoice.company.name,
                    'Тип продажи': invoice.get_sale_type_display() if invoice.sale_type else '',
                    'Валюта': invoice.currency,
                    'Товар': line.product.name if line.product else '',
                    'Артикул': line.product.article if line.product else '',
                    'Количество': line.quantity,
                    'Цена': float(line.price),
                    'Сумма': float(line.total_price),
                })
        
        # Создаем DataFrame
        df = pd.DataFrame(data)
        
        # Формируем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        company_name = company.short_name or company.name
        safe_company_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f'sales_{safe_company_name}_{timestamp}.xlsx'
        
        # Определяем путь к файлу
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)
        
        # Сохраняем Excel файл
        df.to_excel(file_path, sheet_name='Продажи', index=False)
        
        logger.info(f"Экспорт продаж для компании {company.name} завершен: {file_path}")
        return file_path
        
    except Company.DoesNotExist:
        logger.error(f"Компания с ID {company_id} не найдена")
        return f"Компания с ID {company_id} не найдена"
    except Exception as e:
        logger.error(f"Ошибка при экспорте продаж для компании {company_id}: {e}")
        return f"Ошибка экспорта: {str(e)}"