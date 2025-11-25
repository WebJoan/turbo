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


@shared_task
def generate_customer_sales_dynamics_report(date_from=None, date_to=None, company_ids=None, period_type='month'):
    """
    Celery-задача для создания Excel отчета по динамике продаж по клиентам.
    
    Анализирует:
    - Объем выручки
    - Количество заказов
    - Средний чек
    В разрезе времени (день, неделя, месяц, год) и компании-клиента.
    
    Parameters:
    date_from (str): Начальная дата в формате YYYY-MM-DD
    date_to (str): Конечная дата в формате YYYY-MM-DD
    company_ids (list): Список ID компаний для фильтрации (если None - все компании)
    period_type (str): Тип периодизации: 'day', 'week', 'month', 'year'
    
    Returns:
    dict: Информация о созданном файле или сообщение об ошибке
    """
    try:
        from django.db.models import Sum, Count, Avg, F, DecimalField
        from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
        
        # Выбираем функцию группировки в зависимости от типа периода
        period_functions = {
            'day': TruncDay,
            'week': TruncWeek,
            'month': TruncMonth,
            'year': TruncYear
        }
        
        if period_type not in period_functions:
            return {"error": f"Неверный тип периода: {period_type}. Используйте: day, week, month, year"}
        
        trunc_func = period_functions[period_type]
        
        # Формируем базовый запрос
        queryset = Invoice.objects.filter(
            invoice_type=Invoice.InvoiceType.SALE
        ).select_related('company')
        
        # Применяем фильтры
        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)
        if company_ids:
            queryset = queryset.filter(company_id__in=company_ids)
        
        if not queryset.exists():
            return {"error": "Нет данных для создания отчета с указанными параметрами"}
        
        # Аннотируем период и собираем агрегированные данные
        analytics = queryset.annotate(
            period=trunc_func('invoice_date')
        ).values(
            'period',
            'company__id',
            'company__name',
            'company__short_name',
            'company__company_type',
            'company__inn'
        ).annotate(
            # Выручка - сумма всех строк счета
            total_revenue=Sum(
                F('lines__quantity') * F('lines__price'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            ),
            # Количество заказов (счетов)
            order_count=Count('id', distinct=True),
            # Средний чек
            average_check=Avg(
                F('lines__quantity') * F('lines__price'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        ).order_by('period', 'company__name')
        
        # Преобразуем QuerySet в список словарей
        data = []
        for item in analytics:
            data.append({
                'Период': item['period'].strftime('%Y-%m-%d') if item['period'] else '',
                'ID Компании': item['company__id'],
                'Название компании': item['company__short_name'] or item['company__name'],
                'Полное название': item['company__name'],
                'Тип компании': item['company__company_type'],
                'ИНН': item['company__inn'],
                'Выручка (₽)': float(item['total_revenue']) if item['total_revenue'] else 0,
                'Количество заказов': item['order_count'],
                'Средний чек (₽)': float(item['average_check']) if item['average_check'] else 0,
            })
        
        if not data:
            return {"error": "Нет данных для создания отчета после агрегации"}
        
        # Создаем DataFrame
        df = pd.DataFrame(data)
        
        # Создаем дополнительный лист со сводной информацией по компаниям
        summary_data = []
        for company_id in df['ID Компании'].unique():
            company_df = df[df['ID Компании'] == company_id]
            summary_data.append({
                'ID Компании': company_id,
                'Название компании': company_df['Название компании'].iloc[0],
                'Тип компании': company_df['Тип компании'].iloc[0],
                'ИНН': company_df['ИНН'].iloc[0],
                'Общая выручка (₽)': company_df['Выручка (₽)'].sum(),
                'Общее количество заказов': company_df['Количество заказов'].sum(),
                'Средний чек за весь период (₽)': company_df['Выручка (₽)'].sum() / company_df['Количество заказов'].sum() if company_df['Количество заказов'].sum() > 0 else 0,
                'Количество периодов': len(company_df),
            })
        
        summary_df = pd.DataFrame(summary_data).sort_values('Общая выручка (₽)', ascending=False)
        
        # Формируем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        period_labels = {
            'day': 'по_дням',
            'week': 'по_неделям',
            'month': 'по_месяцам',
            'year': 'по_годам'
        }
        period_label = period_labels.get(period_type, period_type)
        filename = f'динамика_продаж_по_клиентам_{period_label}_{timestamp}.xlsx'
        
        # Определяем путь к файлу
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', 'analytics')
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)
        
        # Сохраняем Excel файл с несколькими листами
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Лист с детальной динамикой
            df.to_excel(writer, sheet_name='Динамика по периодам', index=False)
            
            # Лист со сводной информацией
            summary_df.to_excel(writer, sheet_name='Сводная по компаниям', index=False)
            
            # Лист с параметрами отчета
            params_data = {
                'Параметр': ['Дата создания', 'Период с', 'Период по', 'Тип периодизации', 'Количество компаний', 'Всего записей'],
                'Значение': [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    date_from or 'Не указано',
                    date_to or 'Не указано',
                    period_labels.get(period_type, period_type),
                    len(summary_data),
                    len(data)
                ]
            }
            params_df = pd.DataFrame(params_data)
            params_df.to_excel(writer, sheet_name='Параметры отчета', index=False)
        
        logger.info(f"Отчет по динамике продаж создан: {file_path}")
        logger.info(f"Обработано компаний: {len(summary_data)}, записей: {len(data)}")
        
        return {
            "success": True,
            "file_path": file_path,
            "filename": filename,
            "companies_count": len(summary_data),
            "records_count": len(data),
            "total_revenue": float(summary_df['Общая выручка (₽)'].sum()),
        }
        
    except Exception as e:
        logger.error(f"Ошибка при создании отчета по динамике продаж: {e}", exc_info=True)
        return {"error": f"Ошибка создания отчета: {str(e)}"}


@shared_task
def generate_product_sales_dynamics_report(date_from=None, date_to=None, product_ids=None, period_type='month'):
    """
    Celery-задача для создания Excel отчета по динамике продаж по товарам.
    
    Анализирует:
    - Объем выручки
    - Количество заказов
    - Средний чек
    - Количество проданных единиц
    В разрезе времени (день, неделя, месяц, год) и товара.
    
    Parameters:
    date_from (str): Начальная дата в формате YYYY-MM-DD
    date_to (str): Конечная дата в формате YYYY-MM-DD
    product_ids (list): Список ID товаров для фильтрации (если None - все товары)
    period_type (str): Тип периодизации: 'day', 'week', 'month', 'year'
    
    Returns:
    dict: Информация о созданном файле или сообщение об ошибке
    """
    try:
        from django.db.models import Sum, Count, Avg, F, DecimalField
        from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
        
        # Выбираем функцию группировки в зависимости от типа периода
        period_functions = {
            'day': TruncDay,
            'week': TruncWeek,
            'month': TruncMonth,
            'year': TruncYear
        }
        
        if period_type not in period_functions:
            return {"error": f"Неверный тип периода: {period_type}. Используйте: day, week, month, year"}
        
        trunc_func = period_functions[period_type]
        
        # Формируем базовый запрос через строки счетов
        queryset = InvoiceLine.objects.filter(
            invoice__invoice_type=Invoice.InvoiceType.SALE
        ).select_related('invoice', 'product', 'product__brand', 'product__subgroup')
        
        # Применяем фильтры
        if date_from:
            queryset = queryset.filter(invoice__invoice_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(invoice__invoice_date__lte=date_to)
        if product_ids:
            queryset = queryset.filter(product_id__in=product_ids)
        
        if not queryset.exists():
            return {"error": "Нет данных для создания отчета с указанными параметрами"}
        
        # Аннотируем период и собираем агрегированные данные
        analytics = queryset.annotate(
            period=trunc_func('invoice__invoice_date')
        ).values(
            'period',
            'product__id',
            'product__name',
            'product__complex_name',
            'product__brand__name',
            'product__subgroup__name',
            'product__subgroup__group__name'
        ).annotate(
            # Выручка - сумма price * quantity
            total_revenue=Sum(
                F('quantity') * F('price'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            ),
            # Количество заказов (уникальных счетов)
            order_count=Count('invoice', distinct=True),
            # Количество проданных единиц
            quantity_sold=Sum('quantity'),
            # Средняя цена за единицу
            average_price=Avg('price', output_field=DecimalField(max_digits=15, decimal_places=2))
        ).order_by('period', 'product__name')
        
        # Преобразуем QuerySet в список словарей
        data = []
        for item in analytics:
            # Вычисляем средний чек
            avg_check = 0
            if item['order_count'] > 0 and item['total_revenue']:
                avg_check = float(item['total_revenue']) / item['order_count']
            
            data.append({
                'Период': item['period'].strftime('%Y-%m-%d') if item['period'] else '',
                'ID Товара': item['product__id'],
                'Part Number': item['product__name'] or '',
                'Бренд': item['product__brand__name'] or '',
                'Подгруппа': item['product__subgroup__name'] or '',
                'Группа': item['product__subgroup__group__name'] or '',
                'Выручка (₽)': float(item['total_revenue']) if item['total_revenue'] else 0,
                'Количество заказов': item['order_count'],
                'Продано единиц': item['quantity_sold'] or 0,
                'Средняя цена (₽)': float(item['average_price']) if item['average_price'] else 0,
                'Средний чек (₽)': avg_check,
            })
        
        if not data:
            return {"error": "Нет данных для создания отчета после агрегации"}
        
        # Создаем DataFrame
        df = pd.DataFrame(data)
        
        # Создаем дополнительный лист со сводной информацией по товарам
        summary_data = []
        for product_id in df['ID Товара'].unique():
            product_df = df[df['ID Товара'] == product_id]
            summary_data.append({
                'ID Товара': product_id,
                'Part Number': product_df['Part Number'].iloc[0],
                'Бренд': product_df['Бренд'].iloc[0],
                'Подгруппа': product_df['Подгруппа'].iloc[0],
                'Группа': product_df['Группа'].iloc[0],
                'Общая выручка (₽)': product_df['Выручка (₽)'].sum(),
                'Общее количество заказов': product_df['Количество заказов'].sum(),
                'Всего продано единиц': product_df['Продано единиц'].sum(),
                'Средняя цена за весь период (₽)': product_df['Средняя цена (₽)'].mean(),
                'Средний чек за весь период (₽)': product_df['Выручка (₽)'].sum() / product_df['Количество заказов'].sum() if product_df['Количество заказов'].sum() > 0 else 0,
                'Количество периодов': len(product_df),
            })
        
        summary_df = pd.DataFrame(summary_data).sort_values('Общая выручка (₽)', ascending=False)
        
        # Формируем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        period_labels = {
            'day': 'по_дням',
            'week': 'по_неделям',
            'month': 'по_месяцам',
            'year': 'по_годам'
        }
        period_label = period_labels.get(period_type, period_type)
        filename = f'динамика_продаж_по_товарам_{period_label}_{timestamp}.xlsx'
        
        # Определяем путь к файлу
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', 'analytics')
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)
        
        # Сохраняем Excel файл с несколькими листами
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Лист с детальной динамикой
            df.to_excel(writer, sheet_name='Динамика по периодам', index=False)
            
            # Лист со сводной информацией
            summary_df.to_excel(writer, sheet_name='Сводная по товарам', index=False)
            
            # Лист с параметрами отчета
            params_data = {
                'Параметр': ['Дата создания', 'Период с', 'Период по', 'Тип периодизации', 'Количество товаров', 'Всего записей'],
                'Значение': [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    date_from or 'Не указано',
                    date_to or 'Не указано',
                    period_labels.get(period_type, period_type),
                    len(summary_data),
                    len(data)
                ]
            }
            params_df = pd.DataFrame(params_data)
            params_df.to_excel(writer, sheet_name='Параметры отчета', index=False)
        
        logger.info(f"Отчет по динамике продаж товаров создан: {file_path}")
        logger.info(f"Обработано товаров: {len(summary_data)}, записей: {len(data)}")
        
        return {
            "success": True,
            "file_path": file_path,
            "filename": filename,
            "products_count": len(summary_data),
            "records_count": len(data),
            "total_revenue": float(summary_df['Общая выручка (₽)'].sum()),
        }
        
    except Exception as e:
        logger.error(f"Ошибка при создании отчета по динамике продаж товаров: {e}", exc_info=True)
        return {"error": f"Ошибка создания отчета: {str(e)}"}


@shared_task
def generate_customer_cohort_analysis_report(date_from=None, date_to=None, period_type='month'):
    """
    Celery-задача для создания Excel отчета когортного анализа клиентов.
    
    Анализирует:
    - Retention Rate (процент вернувшихся клиентов)
    - Revenue Retention (выручка от когорты по периодам)
    - Размер когорт
    - Количество заказов от когорты
    
    Когорты формируются на основе месяца первой покупки клиента.
    
    Parameters:
    date_from (str): Начальная дата в формате YYYY-MM-DD (для фильтрации когорт)
    date_to (str): Конечная дата в формате YYYY-MM-DD (для фильтрации когорт)
    period_type (str): Тип периодизации: 'week', 'month' (по умолчанию month)
    
    Returns:
    dict: Информация о созданном файле или сообщение об ошибке
    """
    try:
        from django.db.models import Min
        from decimal import Decimal
        
        # Определяем метку периода
        if period_type == 'week':
            period_label = 'по_неделям'
        else:
            period_label = 'по_месяцам'
        
        # Функция для вычисления периода из даты
        def get_period_from_date(date):
            from datetime import timedelta
            if period_type == 'week':
                # Получаем понедельник недели (ISO week)
                return date - timedelta(days=date.weekday())
            else:
                # Получаем первый день месяца
                return date.replace(day=1)
        
        # Получаем все продажи
        sales_queryset = Invoice.objects.filter(
            invoice_type=Invoice.InvoiceType.SALE
        ).select_related('company')
        
        if not sales_queryset.exists():
            return {"error": "Нет данных о продажах для анализа"}
        
        # Определяем первую покупку каждого клиента (когорту)
        first_purchases = sales_queryset.values('company_id').annotate(
            first_purchase_date=Min('invoice_date')
        )
        
        # Создаем словарь: company_id -> cohort_period
        company_cohorts = {
            item['company_id']: get_period_from_date(item['first_purchase_date'])
            for item in first_purchases
        }
        
        # Фильтруем когорты по датам если указаны
        if date_from or date_to:
            filtered_cohorts = {}
            for company_id, cohort_date in company_cohorts.items():
                if date_from and cohort_date < datetime.strptime(date_from, '%Y-%m-%d').date():
                    continue
                if date_to and cohort_date > datetime.strptime(date_to, '%Y-%m-%d').date():
                    continue
                filtered_cohorts[company_id] = cohort_date
            company_cohorts = filtered_cohorts
        
        if not company_cohorts:
            return {"error": "Нет когорт для анализа с указанными параметрами"}
        
        # Получаем все периоды для анализа
        all_periods = set()
        cohort_data = {}  # cohort_period -> {period -> {customers: set, revenue: Decimal, orders: int}}
        
        # Инициализируем структуру данных
        unique_cohorts = sorted(set(company_cohorts.values()))
        
        # Собираем данные по всем счетам
        for invoice in sales_queryset.filter(company_id__in=company_cohorts.keys()):
            company_id = invoice.company_id
            cohort_period = company_cohorts[company_id]
            invoice_period = get_period_from_date(invoice.invoice_date)
            
            all_periods.add(invoice_period)
            
            # Инициализируем структуру если нужно
            if cohort_period not in cohort_data:
                cohort_data[cohort_period] = {}
            if invoice_period not in cohort_data[cohort_period]:
                cohort_data[cohort_period][invoice_period] = {
                    'customers': set(),
                    'revenue': Decimal('0'),
                    'orders': 0
                }
            
            # Добавляем данные
            cohort_data[cohort_period][invoice_period]['customers'].add(company_id)
            cohort_data[cohort_period][invoice_period]['orders'] += 1
            
            # Вычисляем выручку
            lines = InvoiceLine.objects.filter(invoice=invoice)
            for line in lines:
                cohort_data[cohort_period][invoice_period]['revenue'] += line.quantity * line.price
        
        all_periods = sorted(all_periods)
        
        # Функция для расчета разницы периодов
        def period_diff(cohort_period, current_period):
            if period_type == 'week':
                # Разница в неделях
                delta = (current_period - cohort_period).days
                return delta // 7
            else:
                # Разница в месяцах
                return (current_period.year - cohort_period.year) * 12 + (current_period.month - cohort_period.month)
        
        # Создаем таблицу retention
        max_periods = 0
        for cohort_period in unique_cohorts:
            for period in all_periods:
                if period >= cohort_period:
                    diff = period_diff(cohort_period, period)
                    max_periods = max(max_periods, diff)
        
        # Retention Rate таблица
        retention_data = []
        for cohort_period in unique_cohorts:
            if cohort_period not in cohort_data:
                continue
            
            row = {
                'Когорта': cohort_period.strftime('%Y-%m-%d'),
                'Размер когорты': len(cohort_data[cohort_period].get(cohort_period, {}).get('customers', set()))
            }
            
            cohort_size = row['Размер когорты']
            if cohort_size == 0:
                continue
            
            for period_num in range(max_periods + 1):
                target_period = None
                for period in all_periods:
                    if period >= cohort_period and period_diff(cohort_period, period) == period_num:
                        target_period = period
                        break
                
                if target_period and target_period in cohort_data[cohort_period]:
                    active_customers = len(cohort_data[cohort_period][target_period]['customers'])
                    retention_rate = (active_customers / cohort_size * 100) if cohort_size > 0 else 0
                    row[f'Период {period_num}'] = f"{retention_rate:.1f}%"
                else:
                    row[f'Период {period_num}'] = "0.0%"
            
            retention_data.append(row)
        
        # Revenue Retention таблица
        revenue_data = []
        for cohort_period in unique_cohorts:
            if cohort_period not in cohort_data:
                continue
            
            row = {
                'Когорта': cohort_period.strftime('%Y-%m-%d'),
                'Размер когорты': len(cohort_data[cohort_period].get(cohort_period, {}).get('customers', set()))
            }
            
            if row['Размер когорты'] == 0:
                continue
            
            for period_num in range(max_periods + 1):
                target_period = None
                for period in all_periods:
                    if period >= cohort_period and period_diff(cohort_period, period) == period_num:
                        target_period = period
                        break
                
                if target_period and target_period in cohort_data[cohort_period]:
                    revenue = float(cohort_data[cohort_period][target_period]['revenue'])
                    row[f'Период {period_num}'] = revenue
                else:
                    row[f'Период {period_num}'] = 0
            
            revenue_data.append(row)
        
        # Количество заказов таблица
        orders_data = []
        for cohort_period in unique_cohorts:
            if cohort_period not in cohort_data:
                continue
            
            row = {
                'Когорта': cohort_period.strftime('%Y-%m-%d'),
                'Размер когорты': len(cohort_data[cohort_period].get(cohort_period, {}).get('customers', set()))
            }
            
            if row['Размер когорты'] == 0:
                continue
            
            for period_num in range(max_periods + 1):
                target_period = None
                for period in all_periods:
                    if period >= cohort_period and period_diff(cohort_period, period) == period_num:
                        target_period = period
                        break
                
                if target_period and target_period in cohort_data[cohort_period]:
                    orders = cohort_data[cohort_period][target_period]['orders']
                    row[f'Период {period_num}'] = orders
                else:
                    row[f'Период {period_num}'] = 0
            
            orders_data.append(row)
        
        if not retention_data:
            return {"error": "Недостаточно данных для когортного анализа"}
        
        # Создаем DataFrames
        retention_df = pd.DataFrame(retention_data)
        revenue_df = pd.DataFrame(revenue_data)
        orders_df = pd.DataFrame(orders_data)
        
        # Формируем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'когортный_анализ_клиентов_{period_label}_{timestamp}.xlsx'
        
        # Определяем путь к файлу
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', 'analytics')
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)
        
        # Сохраняем Excel файл с несколькими листами
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Лист с Retention Rate
            retention_df.to_excel(writer, sheet_name='Retention Rate (%)', index=False)
            
            # Лист с Revenue Retention
            revenue_df.to_excel(writer, sheet_name='Выручка по когортам (₽)', index=False)
            
            # Лист с количеством заказов
            orders_df.to_excel(writer, sheet_name='Количество заказов', index=False)
            
            # Лист с параметрами отчета
            params_data = {
                'Параметр': [
                    'Дата создания',
                    'Период с',
                    'Период по',
                    'Тип периодизации',
                    'Количество когорт',
                    'Максимальный период анализа'
                ],
                'Значение': [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    date_from or 'Не указано',
                    date_to or 'Не указано',
                    period_label,
                    len(retention_data),
                    max_periods
                ]
            }
            params_df = pd.DataFrame(params_data)
            params_df.to_excel(writer, sheet_name='Параметры отчета', index=False)
            
            # Добавляем лист с пояснениями
            explanation_data = {
                'Метрика': [
                    'Когорта',
                    'Размер когорты',
                    'Retention Rate',
                    'Период 0',
                    'Период N',
                    'Выручка по когортам',
                    'Количество заказов'
                ],
                'Описание': [
                    'Месяц или неделя первой покупки клиентов',
                    'Количество уникальных клиентов в когорте',
                    'Процент клиентов из когорты, совершивших покупку в данном периоде',
                    'Период первой покупки (базовый период когорты)',
                    'N-й период после первой покупки',
                    'Сумма выручки от клиентов когорты в каждом периоде',
                    'Количество заказов от клиентов когорты в каждом периоде'
                ]
            }
            explanation_df = pd.DataFrame(explanation_data)
            explanation_df.to_excel(writer, sheet_name='Пояснения', index=False)
        
        logger.info(f"Когортный анализ создан: {file_path}")
        logger.info(f"Обработано когорт: {len(retention_data)}, максимальный период: {max_periods}")
        
        return {
            "success": True,
            "file_path": file_path,
            "filename": filename,
            "cohorts_count": len(retention_data),
            "max_periods": max_periods,
        }
        
    except Exception as e:
        logger.error(f"Ошибка при создании когортного анализа: {e}", exc_info=True)
        return {"error": f"Ошибка создания отчета: {str(e)}"}


@shared_task
def generate_rfm_segmentation_report(date_from=None, date_to=None, reference_date=None):
    """
    Celery-задача для создания Excel отчета RFM-сегментации клиентов.
    
    RFM анализ сегментирует клиентов на основе:
    - Recency (R): Давность последней покупки (дни с последней покупки)
    - Frequency (F): Частота покупок (количество заказов)
    - Monetary (M): Денежная ценность (общая выручка от клиента)
    
    Каждая метрика оценивается по шкале 1-5, где 5 - лучший показатель.
    
    Parameters:
    date_from (str): Начальная дата для анализа транзакций (YYYY-MM-DD)
    date_to (str): Конечная дата для анализа транзакций (YYYY-MM-DD)
    reference_date (str): Дата для расчета Recency (по умолчанию - сегодня)
    
    Returns:
    dict: Информация о созданном файле или сообщение об ошибке
    """
    try:
        from django.db.models import Sum, Count, Max, F as DjangoF
        from decimal import Decimal
        from datetime import timedelta
        
        # Определяем референсную дату (от которой считаем давность)
        if reference_date:
            ref_date = datetime.strptime(reference_date, '%Y-%m-%d').date()
        else:
            ref_date = datetime.now().date()
        
        # Получаем все продажи
        sales_queryset = Invoice.objects.filter(
            invoice_type=Invoice.InvoiceType.SALE
        ).select_related('company')
        
        # Применяем фильтры по датам
        if date_from:
            sales_queryset = sales_queryset.filter(invoice_date__gte=date_from)
        if date_to:
            sales_queryset = sales_queryset.filter(invoice_date__lte=date_to)
        
        if not sales_queryset.exists():
            return {"error": "Нет данных о продажах для RFM анализа"}
        
        # Собираем данные по каждому клиенту
        customer_data = sales_queryset.values('company_id').annotate(
            last_purchase_date=Max('invoice_date'),
            total_orders=Count('id'),
        )
        
        # Вычисляем RFM метрики для каждого клиента
        rfm_data = []
        company_ids = []
        
        for item in customer_data:
            company_id = item['company_id']
            company_ids.append(company_id)
            
            # R - Recency (дни с последней покупки)
            days_since_purchase = (ref_date - item['last_purchase_date']).days
            
            # F - Frequency (количество заказов)
            frequency = item['total_orders']
            
            # M - Monetary (общая выручка)
            # Вычисляем выручку через строки счетов
            company_invoices = sales_queryset.filter(company_id=company_id)
            invoice_ids = list(company_invoices.values_list('id', flat=True))
            
            monetary = Decimal('0')
            if invoice_ids:
                lines = InvoiceLine.objects.filter(invoice_id__in=invoice_ids)
                for line in lines:
                    monetary += line.quantity * line.price
            
            rfm_data.append({
                'company_id': company_id,
                'recency': days_since_purchase,
                'frequency': frequency,
                'monetary': float(monetary),
                'last_purchase_date': item['last_purchase_date']
            })
        
        if not rfm_data:
            return {"error": "Недостаточно данных для RFM анализа"}
        
        # Создаем DataFrame для удобства расчетов
        df = pd.DataFrame(rfm_data)
        
        # Вычисляем квантили для каждой метрики (разбиваем на 5 сегментов)
        # Для Recency: меньше дней = лучше (поэтому используем ascending=False при присвоении баллов)
        # Для Frequency и Monetary: больше = лучше
        
        # Функция для безопасного квантиля с обработкой дубликатов
        def safe_qcut(series, name, reverse=False):
            try:
                # Пробуем разбить на 5 квантилей
                result = pd.qcut(series, q=5, labels=False, duplicates='drop')
            except ValueError:
                # Если не получается на 5, пробуем на 3
                try:
                    result = pd.qcut(series, q=3, labels=False, duplicates='drop')
                except ValueError:
                    # Если и на 3 не получается, используем ранги
                    result = series.rank(method='dense') - 1
            
            # Нормализуем к диапазону 1-5
            if result.max() > 0:
                result = ((result - result.min()) / (result.max() - result.min()) * 4 + 1).round()
            else:
                result = pd.Series([3] * len(result), index=result.index)
            
            # Для Recency инвертируем (меньше дней = выше балл)
            if reverse:
                result = 6 - result
            
            return result.astype(int)
        
        # R: чем меньше дней, тем выше балл (инверсия)
        df['R_score'] = safe_qcut(df['recency'], 'recency', reverse=True)
        
        # F: чем больше заказов, тем выше балл
        df['F_score'] = safe_qcut(df['frequency'], 'frequency', reverse=False)
        
        # M: чем больше выручка, тем выше балл
        df['M_score'] = safe_qcut(df['monetary'], 'monetary', reverse=False)
        
        # Вычисляем общий RFM балл
        df['RFM_Score'] = df['R_score'].astype(str) + df['F_score'].astype(str) + df['M_score'].astype(str)
        
        # Функция для определения сегмента клиента
        def get_segment(row):
            r, f, m = row['R_score'], row['F_score'], row['M_score']
            
            # Champions - лучшие клиенты
            if r >= 4 and f >= 4 and m >= 4:
                return 'Champions'
            # Loyal Customers - лояльные клиенты
            elif r >= 3 and f >= 4 and m >= 3:
                return 'Loyal Customers'
            # Potential Loyalists - потенциально лояльные
            elif r >= 4 and f >= 2 and m >= 2:
                return 'Potential Loyalists'
            # New Customers - новые клиенты
            elif r >= 4 and f <= 2 and m <= 2:
                return 'New Customers'
            # Promising - перспективные
            elif r >= 3 and f <= 2 and m <= 2:
                return 'Promising'
            # Need Attention - требуют внимания
            elif r == 3 and f == 3 and m == 3:
                return 'Need Attention'
            # About to Sleep - засыпающие
            elif r <= 3 and f <= 3 and m >= 2:
                return 'About to Sleep'
            # At Risk - в зоне риска
            elif r <= 2 and f >= 2 and m >= 2:
                return 'At Risk'
            # Cannot Lose Them - нельзя терять
            elif r <= 2 and f >= 4 and m >= 4:
                return 'Cannot Lose Them'
            # Hibernating - спящие
            elif r <= 2 and f <= 2 and m <= 2:
                return 'Hibernating'
            # Lost - потерянные
            elif r <= 2 and f >= 2 and m <= 2:
                return 'Lost'
            else:
                return 'Other'
        
        df['Segment'] = df.apply(get_segment, axis=1)
        
        # Получаем названия компаний
        companies = Company.objects.filter(id__in=company_ids)
        company_names = {c.id: c.name for c in companies}
        df['company_name'] = df['company_id'].map(company_names)
        
        # Подготавливаем финальный DataFrame
        result_df = df[[
            'company_id', 'company_name', 'recency', 'frequency', 'monetary',
            'R_score', 'F_score', 'M_score', 'RFM_Score', 'Segment', 'last_purchase_date'
        ]].copy()
        
        result_df.columns = [
            'ID Компании', 'Название компании', 'Давность (дней)', 'Частота (заказов)',
            'Выручка (₽)', 'R-балл', 'F-балл', 'M-балл', 'RFM балл', 'Сегмент',
            'Последняя покупка'
        ]
        
        # Сортируем по RFM баллу (от лучших к худшим)
        result_df = result_df.sort_values('RFM балл', ascending=False)
        
        # Создаем сводную таблицу по сегментам
        segment_summary = df.groupby('Segment').agg({
            'company_id': 'count',
            'monetary': 'sum',
            'frequency': 'mean',
            'recency': 'mean'
        }).round(2)
        
        segment_summary.columns = ['Количество клиентов', 'Общая выручка (₽)', 'Средняя частота', 'Средняя давность (дней)']
        segment_summary = segment_summary.sort_values('Общая выручка (₽)', ascending=False)
        segment_summary = segment_summary.reset_index()
        
        # Создаем таблицу с распределением по RFM баллам
        rfm_distribution = df.groupby(['R_score', 'F_score', 'M_score']).agg({
            'company_id': 'count',
            'monetary': 'sum'
        }).round(2)
        rfm_distribution.columns = ['Количество клиентов', 'Общая выручка (₽)']
        rfm_distribution = rfm_distribution.sort_values('Общая выручка (₽)', ascending=False)
        rfm_distribution = rfm_distribution.reset_index()
        rfm_distribution.columns = ['R-балл', 'F-балл', 'M-балл', 'Количество клиентов', 'Общая выручка (₽)']
        
        # Формируем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'rfm_сегментация_клиентов_{timestamp}.xlsx'
        
        # Определяем путь к файлу
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', 'analytics')
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)
        
        # Сохраняем Excel файл с несколькими листами
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Основной лист с RFM данными
            result_df.to_excel(writer, sheet_name='RFM Анализ', index=False)
            
            # Лист с сводкой по сегментам
            segment_summary.to_excel(writer, sheet_name='Сводка по сегментам', index=False)
            
            # Лист с распределением по RFM баллам
            rfm_distribution.to_excel(writer, sheet_name='Распределение RFM', index=False)
            
            # Лист с параметрами отчета
            params_data = {
                'Параметр': [
                    'Дата создания',
                    'Референсная дата',
                    'Период с',
                    'Период по',
                    'Всего клиентов',
                    'Всего сегментов'
                ],
                'Значение': [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    ref_date.strftime('%Y-%m-%d'),
                    date_from or 'Не указано',
                    date_to or 'Не указано',
                    len(result_df),
                    df['Segment'].nunique()
                ]
            }
            params_df = pd.DataFrame(params_data)
            params_df.to_excel(writer, sheet_name='Параметры отчета', index=False)
            
            # Добавляем лист с пояснениями
            explanation_data = {
                'Метрика': [
                    'R (Recency)',
                    'F (Frequency)',
                    'M (Monetary)',
                    'RFM балл',
                    'Сегмент Champions',
                    'Сегмент Loyal Customers',
                    'Сегмент At Risk',
                    'Сегмент Cannot Lose Them',
                    'Сегмент Hibernating',
                    'Шкала оценки'
                ],
                'Описание': [
                    'Давность последней покупки в днях. Чем меньше дней - тем выше балл',
                    'Количество заказов клиента. Чем больше заказов - тем выше балл',
                    'Общая выручка от клиента. Чем больше выручка - тем выше балл',
                    'Комбинация R, F, M баллов (например, 555 - лучший клиент)',
                    'Лучшие клиенты. Покупают часто, недавно и много',
                    'Лояльные клиенты. Регулярно совершают покупки',
                    'Клиенты в зоне риска. Давно не покупали, но раньше были активны',
                    'Ценные клиенты, которых нельзя терять. Были очень активны',
                    'Спящие клиенты. Давно не покупали и покупали мало',
                    'Каждая метрика оценивается от 1 (худший) до 5 (лучший)'
                ]
            }
            explanation_df = pd.DataFrame(explanation_data)
            explanation_df.to_excel(writer, sheet_name='Пояснения', index=False)
        
        logger.info(f"RFM сегментация создана: {file_path}")
        logger.info(f"Обработано клиентов: {len(result_df)}, сегментов: {df['Segment'].nunique()}")
        
        return {
            "success": True,
            "file_path": file_path,
            "filename": filename,
            "customers_count": len(result_df),
            "segments_count": int(df['Segment'].nunique()),
            "total_revenue": float(df['monetary'].sum()),
        }
        
    except Exception as e:
        logger.error(f"Ошибка при создании RFM сегментации: {e}", exc_info=True)
        return {"error": f"Ошибка создания отчета: {str(e)}"}


@shared_task
def generate_ltv_analysis_report(date_from=None, date_to=None):
    """
    Celery-задача для создания Excel отчета по LTV (Customer Lifetime Value) клиентов.
    
    Анализирует пожизненную ценность клиентов:
    - Historical LTV: Реальная выручка от клиента за весь период
    - Average Order Value (AOV): Средний чек клиента
    - Purchase Frequency: Частота покупок
    - Customer Lifespan: Продолжительность жизни клиента (дни)
    - Predicted LTV: Прогнозная пожизненная ценность
    
    Parameters:
    date_from (str): Начальная дата для анализа (YYYY-MM-DD)
    date_to (str): Конечная дата для анализа (YYYY-MM-DD)
    
    Returns:
    dict: Информация о созданном файле или сообщение об ошибке
    """
    try:
        from django.db.models import Sum, Count, Max, Min, Avg, F as DjangoF
        from decimal import Decimal
        from datetime import timedelta
        
        # Получаем все продажи
        sales_queryset = Invoice.objects.filter(
            invoice_type=Invoice.InvoiceType.SALE
        ).select_related('company')
        
        # Применяем фильтры по датам
        if date_from:
            sales_queryset = sales_queryset.filter(invoice_date__gte=date_from)
        if date_to:
            sales_queryset = sales_queryset.filter(invoice_date__lte=date_to)
        
        if not sales_queryset.exists():
            return {"error": "Нет данных о продажах для LTV анализа"}
        
        # Собираем данные по каждому клиенту
        customer_data = sales_queryset.values('company_id').annotate(
            first_purchase_date=Min('invoice_date'),
            last_purchase_date=Max('invoice_date'),
            total_orders=Count('id'),
        )
        
        # Вычисляем LTV метрики для каждого клиента
        ltv_data = []
        company_ids = []
        
        for item in customer_data:
            company_id = item['company_id']
            company_ids.append(company_id)
            
            # Базовые данные
            first_purchase = item['first_purchase_date']
            last_purchase = item['last_purchase_date']
            total_orders = item['total_orders']
            
            # Вычисляем Historical LTV (общая выручка)
            company_invoices = sales_queryset.filter(company_id=company_id)
            invoice_ids = list(company_invoices.values_list('id', flat=True))
            
            historical_ltv = Decimal('0')
            if invoice_ids:
                lines = InvoiceLine.objects.filter(invoice_id__in=invoice_ids)
                for line in lines:
                    historical_ltv += line.quantity * line.price
            
            # Customer Lifespan (в днях)
            lifespan_days = (last_purchase - first_purchase).days
            if lifespan_days == 0:
                lifespan_days = 1  # Минимум 1 день для новых клиентов
            
            # Average Order Value (средний чек)
            aov = float(historical_ltv) / total_orders if total_orders > 0 else 0
            
            # Purchase Frequency (покупок в месяц)
            purchase_frequency_monthly = (total_orders / (lifespan_days / 30.0)) if lifespan_days > 0 else total_orders
            
            # Customer Value (выручка в месяц)
            customer_value_monthly = aov * purchase_frequency_monthly
            
            # Predicted LTV (прогноз на 12 месяцев)
            # Простая модель: текущая месячная выручка * 12 месяцев
            predicted_ltv_12m = customer_value_monthly * 12
            
            # Predicted LTV (прогноз на 24 месяца)
            predicted_ltv_24m = customer_value_monthly * 24
            
            # Количество дней с последней покупки
            if date_to:
                ref_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            else:
                ref_date = datetime.now().date()
            days_since_last_purchase = (ref_date - last_purchase).days
            
            ltv_data.append({
                'company_id': company_id,
                'first_purchase_date': first_purchase,
                'last_purchase_date': last_purchase,
                'total_orders': total_orders,
                'historical_ltv': float(historical_ltv),
                'lifespan_days': lifespan_days,
                'aov': aov,
                'purchase_frequency_monthly': purchase_frequency_monthly,
                'customer_value_monthly': customer_value_monthly,
                'predicted_ltv_12m': predicted_ltv_12m,
                'predicted_ltv_24m': predicted_ltv_24m,
                'days_since_last_purchase': days_since_last_purchase
            })
        
        if not ltv_data:
            return {"error": "Недостаточно данных для LTV анализа"}
        
        # Создаем DataFrame
        df = pd.DataFrame(ltv_data)
        
        # Получаем названия компаний
        companies = Company.objects.filter(id__in=company_ids)
        company_names = {c.id: c.name for c in companies}
        company_types = {c.id: c.company_type for c in companies}
        df['company_name'] = df['company_id'].map(company_names)
        df['company_type'] = df['company_id'].map(company_types)
        
        # Классификация клиентов по LTV
        def classify_ltv(row):
            ltv = row['historical_ltv']
            percentile_75 = df['historical_ltv'].quantile(0.75)
            percentile_50 = df['historical_ltv'].quantile(0.50)
            percentile_25 = df['historical_ltv'].quantile(0.25)
            
            if ltv >= percentile_75:
                return 'High Value'
            elif ltv >= percentile_50:
                return 'Medium-High Value'
            elif ltv >= percentile_25:
                return 'Medium Value'
            else:
                return 'Low Value'
        
        df['ltv_segment'] = df.apply(classify_ltv, axis=1)
        
        # Классификация по статусу активности
        def classify_activity(days_since):
            if days_since <= 30:
                return 'Active'
            elif days_since <= 90:
                return 'At Risk'
            elif days_since <= 180:
                return 'Inactive'
            else:
                return 'Churned'
        
        df['activity_status'] = df['days_since_last_purchase'].apply(classify_activity)
        
        # Подготавливаем финальный DataFrame
        result_df = df[[
            'company_id', 'company_name', 'company_type',
            'first_purchase_date', 'last_purchase_date', 'days_since_last_purchase',
            'total_orders', 'lifespan_days',
            'historical_ltv', 'aov', 'purchase_frequency_monthly', 'customer_value_monthly',
            'predicted_ltv_12m', 'predicted_ltv_24m',
            'ltv_segment', 'activity_status'
        ]].copy()
        
        result_df.columns = [
            'ID Компании', 'Название компании', 'Тип компании',
            'Первая покупка', 'Последняя покупка', 'Дней с последней покупки',
            'Всего заказов', 'Продолжительность жизни (дни)',
            'Historical LTV (₽)', 'Средний чек (₽)', 'Частота покупок (мес⁻¹)', 'Выручка в месяц (₽)',
            'Прогноз LTV 12м (₽)', 'Прогноз LTV 24м (₽)',
            'Сегмент LTV', 'Статус активности'
        ]
        
        # Сортируем по Historical LTV (от лучших к худшим)
        result_df = result_df.sort_values('Historical LTV (₽)', ascending=False)
        
        # Создаем сводную таблицу по сегментам LTV
        ltv_segment_summary = df.groupby('ltv_segment').agg({
            'company_id': 'count',
            'historical_ltv': ['sum', 'mean'],
            'total_orders': 'sum',
            'aov': 'mean',
            'purchase_frequency_monthly': 'mean'
        }).round(2)
        
        ltv_segment_summary.columns = [
            'Количество клиентов',
            'Общая выручка (₽)', 'Средняя LTV (₽)',
            'Всего заказов',
            'Средний чек (₽)', 'Средняя частота (мес⁻¹)'
        ]
        ltv_segment_summary = ltv_segment_summary.reset_index()
        ltv_segment_summary.columns = ['Сегмент LTV'] + list(ltv_segment_summary.columns[1:])
        
        # Создаем сводную по статусу активности
        activity_summary = df.groupby('activity_status').agg({
            'company_id': 'count',
            'historical_ltv': ['sum', 'mean'],
            'predicted_ltv_12m': 'sum'
        }).round(2)
        
        activity_summary.columns = [
            'Количество клиентов',
            'Общая выручка (₽)', 'Средняя LTV (₽)',
            'Прогноз выручки 12м (₽)'
        ]
        activity_summary = activity_summary.reset_index()
        activity_summary.columns = ['Статус активности'] + list(activity_summary.columns[1:])
        
        # Общая статистика
        total_stats = {
            'Метрика': [
                'Всего клиентов',
                'Общая выручка (Historical LTV)',
                'Средняя LTV на клиента',
                'Медианная LTV',
                'Средний чек',
                'Средняя частота покупок (мес⁻¹)',
                'Прогноз выручки 12 месяцев',
                'Прогноз выручки 24 месяца',
                'Средняя продолжительность жизни (дни)',
                'Активных клиентов',
                'Клиентов в зоне риска',
                'Потерянных клиентов (Churned)'
            ],
            'Значение': [
                len(df),
                f"{df['historical_ltv'].sum():,.2f} ₽",
                f"{df['historical_ltv'].mean():,.2f} ₽",
                f"{df['historical_ltv'].median():,.2f} ₽",
                f"{df['aov'].mean():,.2f} ₽",
                f"{df['purchase_frequency_monthly'].mean():.2f}",
                f"{df['predicted_ltv_12m'].sum():,.2f} ₽",
                f"{df['predicted_ltv_24m'].sum():,.2f} ₽",
                f"{df['lifespan_days'].mean():.0f}",
                len(df[df['activity_status'] == 'Active']),
                len(df[df['activity_status'] == 'At Risk']),
                len(df[df['activity_status'] == 'Churned'])
            ]
        }
        stats_df = pd.DataFrame(total_stats)
        
        # Формируем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'ltv_анализ_клиентов_{timestamp}.xlsx'
        
        # Определяем путь к файлу
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', 'analytics')
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)
        
        # Сохраняем Excel файл с несколькими листами
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Основной лист с LTV данными
            result_df.to_excel(writer, sheet_name='LTV Анализ', index=False)
            
            # Лист с общей статистикой
            stats_df.to_excel(writer, sheet_name='Общая статистика', index=False)
            
            # Лист с сегментами LTV
            ltv_segment_summary.to_excel(writer, sheet_name='Сегменты LTV', index=False)
            
            # Лист со статусами активности
            activity_summary.to_excel(writer, sheet_name='Статусы активности', index=False)
            
            # Лист с параметрами отчета
            params_data = {
                'Параметр': [
                    'Дата создания',
                    'Период с',
                    'Период по',
                    'Всего клиентов',
                    'Общая историческая LTV',
                    'Средняя LTV'
                ],
                'Значение': [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    date_from or 'Не указано',
                    date_to or 'Не указано',
                    len(result_df),
                    f"{df['historical_ltv'].sum():,.2f} ₽",
                    f"{df['historical_ltv'].mean():,.2f} ₽"
                ]
            }
            params_df = pd.DataFrame(params_data)
            params_df.to_excel(writer, sheet_name='Параметры отчета', index=False)
            
            # Лист с пояснениями
            explanation_data = {
                'Метрика': [
                    'Historical LTV',
                    'Average Order Value (AOV)',
                    'Purchase Frequency',
                    'Customer Lifespan',
                    'Customer Value Monthly',
                    'Predicted LTV 12m',
                    'Predicted LTV 24m',
                    'Сегмент High Value',
                    'Сегмент Low Value',
                    'Статус Active',
                    'Статус At Risk',
                    'Статус Churned'
                ],
                'Описание': [
                    'Реальная выручка от клиента за весь период взаимодействия',
                    'Средний чек клиента (общая выручка / количество заказов)',
                    'Частота покупок клиента в месяц',
                    'Продолжительность жизни клиента в днях (от первой до последней покупки)',
                    'Выручка от клиента в месяц (AOV × частота покупок)',
                    'Прогнозная выручка от клиента на 12 месяцев вперед',
                    'Прогнозная выручка от клиента на 24 месяца вперед',
                    'Клиенты в верхнем квартиле по выручке (топ 25%)',
                    'Клиенты в нижнем квартиле по выручке',
                    'Клиенты с покупкой за последние 30 дней',
                    'Клиенты с покупкой 31-90 дней назад',
                    'Клиенты без покупок более 180 дней'
                ]
            }
            explanation_df = pd.DataFrame(explanation_data)
            explanation_df.to_excel(writer, sheet_name='Пояснения', index=False)
        
        logger.info(f"LTV анализ создан: {file_path}")
        logger.info(f"Обработано клиентов: {len(result_df)}, общая LTV: {df['historical_ltv'].sum():.2f}")
        
        return {
            "success": True,
            "file_path": file_path,
            "filename": filename,
            "customers_count": len(result_df),
            "total_ltv": float(df['historical_ltv'].sum()),
            "average_ltv": float(df['historical_ltv'].mean()),
        }
        
    except Exception as e:
        logger.error(f"Ошибка при создании LTV анализа: {e}", exc_info=True)
        return {"error": f"Ошибка создания отчета: {str(e)}"}


@shared_task
def generate_market_basket_analysis_report(date_from=None, date_to=None, min_support=0.005, min_confidence=0.1, min_lift=1.0):
    """
    Celery-задача для создания Excel отчета по Market Basket Analysis (Анализ корзины).
    
    Анализирует, какие товары покупаются вместе:
    - Часто встречающиеся комбинации товаров
    - Ассоциативные правила (если купил A, то купит B)
    - Метрики: Support, Confidence, Lift
    
    Parameters:
    date_from (str): Начальная дата для анализа (YYYY-MM-DD)
    date_to (str): Конечная дата для анализа (YYYY-MM-DD)
    min_support (float): Минимальная поддержка (доля транзакций), по умолчанию 0.005 (0.5%)
    min_confidence (float): Минимальная уверенность, по умолчанию 0.1 (10%)
    min_lift (float): Минимальный lift, по умолчанию 1.0
    
    Returns:
    dict: Информация о созданном файле или сообщение об ошибке
    """
    try:
        from itertools import combinations
        from collections import defaultdict, Counter
        
        # Получаем все продажи
        sales_queryset = Invoice.objects.filter(
            invoice_type=Invoice.InvoiceType.SALE
        )
        
        # Применяем фильтры по датам
        if date_from:
            sales_queryset = sales_queryset.filter(invoice_date__gte=date_from)
        if date_to:
            sales_queryset = sales_queryset.filter(invoice_date__lte=date_to)
        
        if not sales_queryset.exists():
            return {"error": "Нет данных о продажах для анализа корзины"}
        
        # Собираем транзакции (каждый заказ = транзакция)
        logger.info("Сбор транзакций для анализа корзины...")
        transactions = []
        transaction_details = []
        
        for invoice in sales_queryset.select_related('company'):
            lines = InvoiceLine.objects.filter(invoice=invoice).select_related('product')
            
            if lines.count() < 2:  # Пропускаем заказы с одним товаром
                continue
            
            products = set()
            for line in lines:
                if line.product:
                    products.add(line.product.id)
            
            if len(products) >= 2:  # Только заказы с 2+ уникальными товарами
                transactions.append(products)
                transaction_details.append({
                    'invoice_id': invoice.id,
                    'invoice_date': invoice.invoice_date,
                    'company_name': invoice.company.name if invoice.company else 'Неизвестно',
                    'products': products,
                    'products_count': len(products)
                })
        
        if len(transactions) < 10:
            return {"error": "Недостаточно транзакций для анализа корзины (нужно минимум 10 заказов с 2+ товарами)"}
        
        total_transactions = len(transactions)
        logger.info(f"Найдено транзакций: {total_transactions}")
        
        # Получаем названия товаров
        all_product_ids = set()
        for trans in transactions:
            all_product_ids.update(trans)
        
        products = Product.objects.filter(id__in=all_product_ids).select_related('brand')
        product_part_numbers = {p.id: p.name for p in products}
        product_brands = {p.id: p.brand.name if p.brand else 'Без бренда' for p in products}
        
        # 1. Вычисляем поддержку для отдельных товаров (1-itemsets)
        logger.info("Вычисление поддержки товаров...")
        item_counts = Counter()
        for trans in transactions:
            for item in trans:
                item_counts[item] += 1
        
        item_support = {item: count / total_transactions for item, count in item_counts.items()}
        
        # Фильтруем товары с достаточной поддержкой
        frequent_items = {item for item, support in item_support.items() if support >= min_support}
        
        if len(frequent_items) < 2:
            return {"error": f"Недостаточно популярных товаров с поддержкой >= {min_support*100}%"}
        
        logger.info(f"Товаров с поддержкой >= {min_support}: {len(frequent_items)}")
        
        # 2. Вычисляем поддержку для пар товаров (2-itemsets)
        logger.info("Вычисление поддержки пар товаров...")
        pair_counts = Counter()
        transactions_with_frequent_pairs = 0
        
        for trans in transactions:
            # Только частые товары
            frequent_in_trans = trans & frequent_items
            if len(frequent_in_trans) >= 2:
                transactions_with_frequent_pairs += 1
                for pair in combinations(sorted(frequent_in_trans), 2):
                    pair_counts[pair] += 1
        
        logger.info(f"Транзакций с 2+ частыми товарами: {transactions_with_frequent_pairs}")
        logger.info(f"Всего уникальных пар найдено: {len(pair_counts)}")
        
        if len(pair_counts) == 0:
            return {"error": f"Не найдено транзакций с 2+ частыми товарами. Попробуйте уменьшить min_support (сейчас {min_support*100}%)"}
        
        pair_support = {pair: count / total_transactions for pair, count in pair_counts.items()}
        
        # Фильтруем пары с достаточной поддержкой
        frequent_pairs = {pair for pair, support in pair_support.items() if support >= min_support}
        
        if len(frequent_pairs) < 1:
            # Найдем максимальную поддержку среди пар
            max_pair_support = max(pair_support.values()) if pair_support else 0
            return {"error": f"Не найдено частых пар товаров с поддержкой >= {min_support*100:.2f}%. Найдено {len(pair_counts)} уникальных пар, максимальная поддержка: {max_pair_support*100:.2f}%. Попробуйте уменьшить min_support."}
        
        logger.info(f"Пар товаров с поддержкой >= {min_support}: {len(frequent_pairs)}")
        
        # 3. Генерируем ассоциативные правила A -> B
        logger.info("Генерация ассоциативных правил...")
        rules = []
        
        for pair in frequent_pairs:
            item_a, item_b = pair
            support_ab = pair_support[pair]
            support_a = item_support[item_a]
            support_b = item_support[item_b]
            
            # Правило A -> B
            confidence_a_to_b = support_ab / support_a if support_a > 0 else 0
            lift_a_to_b = confidence_a_to_b / support_b if support_b > 0 else 0
            
            if confidence_a_to_b >= min_confidence and lift_a_to_b >= min_lift:
                rules.append({
                    'antecedent_id': item_a,
                    'antecedent_part_number': product_part_numbers.get(item_a, f'ID:{item_a}'),
                    'antecedent_brand': product_brands.get(item_a, ''),
                    'consequent_id': item_b,
                    'consequent_part_number': product_part_numbers.get(item_b, f'ID:{item_b}'),
                    'consequent_brand': product_brands.get(item_b, ''),
                    'support': support_ab,
                    'confidence': confidence_a_to_b,
                    'lift': lift_a_to_b,
                    'transactions_count': pair_counts[pair]
                })
            
            # Правило B -> A
            confidence_b_to_a = support_ab / support_b if support_b > 0 else 0
            lift_b_to_a = confidence_b_to_a / support_a if support_a > 0 else 0
            
            if confidence_b_to_a >= min_confidence and lift_b_to_a >= min_lift:
                rules.append({
                    'antecedent_id': item_b,
                    'antecedent_part_number': product_part_numbers.get(item_b, f'ID:{item_b}'),
                    'antecedent_brand': product_brands.get(item_b, ''),
                    'consequent_id': item_a,
                    'consequent_part_number': product_part_numbers.get(item_a, f'ID:{item_a}'),
                    'consequent_brand': product_brands.get(item_a, ''),
                    'support': support_ab,
                    'confidence': confidence_b_to_a,
                    'lift': lift_b_to_a,
                    'transactions_count': pair_counts[pair]
                })
        
        if len(rules) == 0:
            return {"error": f"Не найдено правил с confidence >= {min_confidence*100}% и lift >= {min_lift}"}
        
        logger.info(f"Найдено ассоциативных правил: {len(rules)}")
        
        # Создаем DataFrame с правилами
        rules_df = pd.DataFrame(rules)
        rules_df = rules_df.sort_values('lift', ascending=False)
        
        # Форматируем для отчета
        rules_report = rules_df[[
            'antecedent_part_number', 'antecedent_brand', 'consequent_part_number', 'consequent_brand',
            'support', 'confidence', 'lift', 'transactions_count'
        ]].copy()
        
        rules_report.columns = [
            'Part Number A (Если купил)', 'Бренд A', 'Part Number B (То купит)', 'Бренд B',
            'Support (Поддержка)', 'Confidence (Уверенность)', 'Lift (Подъем)', 'Количество заказов'
        ]
        
        # Форматируем проценты
        rules_report['Support (Поддержка)'] = rules_report['Support (Поддержка)'].apply(lambda x: f"{x*100:.2f}%")
        rules_report['Confidence (Уверенность)'] = rules_report['Confidence (Уверенность)'].apply(lambda x: f"{x*100:.2f}%")
        rules_report['Lift (Подъем)'] = rules_report['Lift (Подъем)'].apply(lambda x: f"{x:.2f}")
        
        # Топ товарных пар по поддержке
        top_pairs = []
        for pair, support in sorted(pair_support.items(), key=lambda x: x[1], reverse=True)[:50]:
            item_a, item_b = pair
            top_pairs.append({
                'Part Number A': product_part_numbers.get(item_a, f'ID:{item_a}'),
                'Бренд A': product_brands.get(item_a, ''),
                'Part Number B': product_part_numbers.get(item_b, f'ID:{item_b}'),
                'Бренд B': product_brands.get(item_b, ''),
                'Support (Поддержка)': f"{support*100:.2f}%",
                'Количество заказов': pair_counts[pair],
                'Доля от всех заказов': f"{support*100:.2f}%"
            })
        
        top_pairs_df = pd.DataFrame(top_pairs)
        
        # Топ отдельных товаров
        top_items = []
        for item, support in sorted(item_support.items(), key=lambda x: x[1], reverse=True)[:50]:
            top_items.append({
                'Part Number': product_part_numbers.get(item, f'ID:{item}'),
                'Бренд': product_brands.get(item, ''),
                'Support (Поддержка)': f"{support*100:.2f}%",
                'Количество заказов': item_counts[item],
                'Доля от всех заказов': f"{support*100:.2f}%"
            })
        
        top_items_df = pd.DataFrame(top_items)
        
        # Общая статистика
        stats_data = {
            'Метрика': [
                'Всего транзакций (заказов)',
                'Заказов с 2+ товарами',
                'Уникальных товаров',
                'Товаров с поддержкой >= min_support',
                'Частых пар товаров',
                'Ассоциативных правил',
                'Средний размер корзины',
                'Медианный размер корзины',
                'Макс размер корзины',
                'Мин Support',
                'Мин Confidence',
                'Мин Lift'
            ],
            'Значение': [
                total_transactions,
                len(transactions),
                len(all_product_ids),
                len(frequent_items),
                len(frequent_pairs),
                len(rules),
                f"{sum(len(t) for t in transactions) / len(transactions):.2f}",
                f"{sorted([len(t) for t in transactions])[len(transactions)//2]}",
                max(len(t) for t in transactions),
                f"{min_support*100:.2f}%",
                f"{min_confidence*100:.2f}%",
                f"{min_lift:.2f}"
            ]
        }
        stats_df = pd.DataFrame(stats_data)
        
        # Топ правил по Lift
        top_lift_rules = rules_df.nlargest(20, 'lift')[[
            'antecedent_part_number', 'antecedent_brand', 'consequent_part_number', 'consequent_brand', 'lift', 'confidence', 'support'
        ]].copy()
        top_lift_rules.columns = ['Part Number A', 'Бренд A', 'Part Number B', 'Бренд B', 'Lift', 'Confidence', 'Support']
        top_lift_rules['Lift'] = top_lift_rules['Lift'].apply(lambda x: f"{x:.2f}")
        top_lift_rules['Confidence'] = top_lift_rules['Confidence'].apply(lambda x: f"{x*100:.2f}%")
        top_lift_rules['Support'] = top_lift_rules['Support'].apply(lambda x: f"{x*100:.2f}%")
        
        # Формируем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'market_basket_analysis_{timestamp}.xlsx'
        
        # Определяем путь к файлу
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', 'analytics')
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, filename)
        
        # Сохраняем Excel файл с несколькими листами
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Основной лист с ассоциативными правилами
            rules_report.to_excel(writer, sheet_name='Ассоциативные правила', index=False)
            
            # Топ правил по Lift
            top_lift_rules.to_excel(writer, sheet_name='Топ правил (Lift)', index=False)
            
            # Топ товарных пар
            top_pairs_df.to_excel(writer, sheet_name='Топ товарных пар', index=False)
            
            # Топ отдельных товаров
            top_items_df.to_excel(writer, sheet_name='Топ товаров', index=False)
            
            # Общая статистика
            stats_df.to_excel(writer, sheet_name='Статистика', index=False)
            
            # Параметры отчета
            params_data = {
                'Параметр': [
                    'Дата создания',
                    'Период с',
                    'Период по',
                    'Всего транзакций',
                    'Найдено правил',
                    'Min Support',
                    'Min Confidence',
                    'Min Lift'
                ],
                'Значение': [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    date_from or 'Не указано',
                    date_to or 'Не указано',
                    total_transactions,
                    len(rules),
                    f"{min_support*100:.2f}%",
                    f"{min_confidence*100:.2f}%",
                    f"{min_lift:.2f}"
                ]
            }
            params_df = pd.DataFrame(params_data)
            params_df.to_excel(writer, sheet_name='Параметры', index=False)
            
            # Пояснения
            explanation_data = {
                'Термин': [
                    'Market Basket Analysis',
                    'Транзакция',
                    'Support (Поддержка)',
                    'Confidence (Уверенность)',
                    'Lift (Подъем)',
                    'Правило A → B',
                    'Интерпретация Lift > 1',
                    'Интерпретация Lift = 1',
                    'Интерпретация Lift < 1',
                    'Частый товар',
                    'Частая пара'
                ],
                'Описание': [
                    'Анализ корзины покупателя - метод поиска товаров, которые покупаются вместе',
                    'Один заказ (Invoice) с несколькими товарами',
                    'Доля транзакций, содержащих товар или набор товаров. Support(A,B) = количество заказов с A и B / всего заказов',
                    'Вероятность покупки товара B при условии покупки товара A. Confidence(A→B) = Support(A,B) / Support(A)',
                    'Показывает, насколько вероятнее покупка B при покупке A по сравнению со случайной покупкой B. Lift(A→B) = Confidence(A→B) / Support(B)',
                    'Ассоциативное правило: если клиент купил товар A, то с определенной вероятностью купит товар B',
                    'Товары A и B покупаются вместе чаще, чем случайно. Сильная положительная связь',
                    'Товары A и B независимы, нет связи',
                    'Товары A и B редко покупаются вместе. Отрицательная связь (возможно, товары-заменители)',
                    'Товар с поддержкой >= min_support (встречается достаточно часто)',
                    'Пара товаров с поддержкой >= min_support (покупаются вместе достаточно часто)'
                ]
            }
            explanation_df = pd.DataFrame(explanation_data)
            explanation_df.to_excel(writer, sheet_name='Пояснения', index=False)
        
        logger.info(f"Market Basket Analysis создан: {file_path}")
        logger.info(f"Транзакций: {total_transactions}, Правил: {len(rules)}")
        
        return {
            "success": True,
            "file_path": file_path,
            "filename": filename,
            "transactions_count": total_transactions,
            "rules_count": len(rules),
            "frequent_items_count": len(frequent_items),
            "frequent_pairs_count": len(frequent_pairs),
        }
        
    except Exception as e:
        logger.error(f"Ошибка при создании Market Basket Analysis: {e}", exc_info=True)
        return {"error": f"Ошибка создания отчета: {str(e)}"}