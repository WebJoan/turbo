import os
import logging
from datetime import datetime
import asyncio

import mysql.connector
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from mysql.connector import Error

from goods.models import Product
from .models import (
    OurPriceHistory,
    Competitor,
    CompetitorBrand,
    CompetitorCategory,
    CompetitorProduct,
    CompetitorPriceStockSnapshot,
)
from .clients import PromClient, PromAuthError
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
def prom_login_and_get_session(username: str, password: str, headless: bool = True):
    """
    Авторизация на https://office.promelec.ru/ с возвратом cookie-сессии.

    Возвращает dict:
      - success: bool
      - session: {cookie_header, cookies, user_agent} | None
      - error: str | None
    """

    async def _run() -> dict:
        async with PromClient(headless=headless) as client:
            session = await client.login_and_get_session(username, password)
            return {
                "cookie_header": session.cookie_header,
                "cookies": session.cookies,
                "user_agent": session.user_agent,
            }

    try:
        result = asyncio.run(_run())
        logger.info(
            "PROM login OK: получили cookie_header длиной %s",
            len(result.get("cookie_header", "")),
        )
        return {"success": True, "session": result, "error": None}
    except PromAuthError as e:
        logger.warning("PROM login failed: %s", e)
        return {"success": False, "session": None, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        logger.error("PROM login error: %s", e, exc_info=True)
        return {"success": False, "session": None, "error": str(e)}


@shared_task
def prom_import_categories(username: str | None = None, password: str | None = None, headless: bool = True):
    """
    Логинится на https://office.promelec.ru/goods, открывает модалку "Рубрикатор",
    раскрывает дерево jstree и импортирует все категории конкурента в CompetitorCategory
    с корректными parent/level. Конкурент — Promelec.

    Возвращает краткую статистику по созданию/обновлению категорий.
    """
    import re
    from stock.models import Competitor, CompetitorCategory

    user = username or os.getenv("PROM_LOGIN")
    pwd = password or os.getenv("PROM_PASSWORD")
    if not user or not pwd:
        logger.error("Не заданы PROM_LOGIN/PROM_PASSWORD")
        return {"success": False, "error": "PROM_LOGIN/PROM_PASSWORD не заданы"}

    async def _run() -> list[dict]:
        async with PromClient(headless=headless) as client:
            await client.login_and_get_session(user, pwd)
            await client.page.goto("https://office.promelec.ru/goods", wait_until="domcontentloaded")
            # Открываем рубрикатор
            await client.page.wait_for_selector("#rkg_name")
            await client.page.click("#rkg_name")
            # Ждём появления дерева
            await client.page.wait_for_selector("#treeBasic .jstree-node")

            # Раскрываем дерево и забираем плоский JSON всех узлов
            flat_nodes: list[dict] = await client.page.evaluate(
                """
                () => new Promise((resolve) => {
                  const $ = (window).jQuery || (window).$;
                  const $tree = $ && $("#treeBasic");
                  if (!$tree || !$tree.length || !$tree.jstree) { resolve([]); return; }
                  const inst = $tree.jstree(true);
                  const collect = () => {
                    try { inst.open_all(); } catch (e) {}
                    setTimeout(() => {
                      try {
                        const data = inst.get_json('#', { flat: true });
                        resolve(Array.isArray(data) ? data : []);
                      } catch (e) {
                        resolve([]);
                      }
                    }, 500);
                  };
                  if (inst) {
                    if (inst._model && inst._model.data) { collect(); }
                    else { $tree.one('loaded.jstree', collect); }
                  } else {
                    resolve([]);
                  }
                })
                """
            )

            return flat_nodes

    try:
        import asyncio
        flat_nodes = asyncio.run(_run())
    except PromAuthError as e:
        logger.warning("PROM auth failed: %s", e)
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        logger.error("Ошибка при загрузке дерева категорий: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

    # Подготовка данных: оставляем только узлы с числовым id (реальные категории)
    def _is_numeric_id(value: str) -> bool:
        try:
            return bool(value) and re.fullmatch(r"\d+", str(value)) is not None
        except Exception:
            return False

    def _strip_html(value: str) -> str:
        try:
            from html import unescape
            cleaned = re.sub(r"<[^>]+>", "", value or "")
            cleaned = unescape(cleaned)
            return cleaned.strip()
        except Exception:
            return (value or "").strip()

    numeric_nodes: dict[str, dict] = {}
    for node in flat_nodes or []:
        node_id = str(node.get("id", ""))
        if not _is_numeric_id(node_id):
            continue
        raw_text = node.get("text") or ""
        text = _strip_html(raw_text)
        parent_id = str(node.get("parent", "")) if node.get("parent") is not None else ""
        numeric_nodes[node_id] = {"text": text, "parent": parent_id}

    if not numeric_nodes:
        logger.warning("В дереве не найдено узлов с числовыми ID — нечего импортировать")
        return {"success": True, "total": 0, "created": 0, "updated": 0, "skipped": 0}

    # Ищем/создаём конкурента Promelec
    competitor, _ = Competitor.objects.get_or_create(
        name="Promelec",
        defaults={
            "site_url": "",
            "b2b_site_url": "https://office.promelec.ru/",
            "is_active": True,
        },
    )
    if not competitor.b2b_site_url:
        competitor.b2b_site_url = "https://office.promelec.ru/"
        competitor.save(update_fields=["b2b_site_url"])

    created = 0
    updated = 0
    skipped = 0

    # Вычисление уровней и сохранение parent-ссылок: обрабатываем узлы в порядке, где родитель уже создан
    processed: set[str] = set()
    level_map: dict[str, int] = {}

    with transaction.atomic():
        while len(processed) < len(numeric_nodes):
            progressed = False
            for node_id, info in numeric_nodes.items():
                if node_id in processed:
                    continue
                parent_raw = info["parent"]
                text = info["text"]

                # Определяем родителя: numeric -> ссылка, иначе None (верхний уровень)
                parent_obj = None
                parent_level = 0
                if _is_numeric_id(parent_raw) and parent_raw in processed:
                    try:
                        parent_obj = CompetitorCategory.objects.get(competitor=competitor, ext_id=str(parent_raw))
                        parent_level = level_map.get(parent_raw, 0)
                    except CompetitorCategory.DoesNotExist:
                        parent_obj = None
                        parent_level = 0
                elif _is_numeric_id(parent_raw) and parent_raw not in processed:
                    # Родитель ещё не создан, пропустим пока
                    continue

                node_level = (parent_level + 1) if parent_obj else 1

                obj, is_created = CompetitorCategory.objects.update_or_create(
                    competitor=competitor,
                    ext_id=str(node_id),
                    defaults={
                        "title": text,
                        "parent": parent_obj,
                        "level": node_level,
                        "is_active": False,
                    },
                )
                if is_created:
                    created += 1
                else:
                    changed_fields: list[str] = []
                    if obj.title != text:
                        obj.title = text
                        changed_fields.append("title")
                    if obj.parent_id != (parent_obj.id if parent_obj else None):
                        obj.parent = parent_obj
                        changed_fields.append("parent")
                    if obj.level != node_level:
                        obj.level = node_level
                        changed_fields.append("level")
                    if not obj.is_active:
                        obj.is_active = False
                        changed_fields.append("is_active")
                    if changed_fields:
                        obj.save(update_fields=changed_fields)
                        updated += 1
                    else:
                        skipped += 1

                processed.add(node_id)
                level_map[node_id] = node_level
                progressed = True

            if not progressed:
                # Защитный выход, чтобы не попасть в бесконечный цикл
                pending = [nid for nid in numeric_nodes.keys() if nid not in processed]
                logger.warning("Не удалось обработать некоторые узлы из-за отсутствующих родителей: %s", pending[:10])
                break

    total = len(numeric_nodes)
    logger.info(
        "Импорт категорий PROM завершён: всего=%s, создано=%s, обновлено=%s, пропущено=%s",
        total,
        created,
        updated,
        skipped,
    )
    return {"success": True, "total": total, "created": created, "updated": updated, "skipped": skipped}


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        # Удаляем пробелы-разделители тысяч и нецифровые символы
        cleaned = (value or "").replace("\xa0", " ").replace(" ", "").strip()
        if not cleaned:
            return None
        return int(cleaned)
    except Exception:
        return None


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        cleaned = (value or "").replace("\xa0", " ").replace(" ", "").replace(",", ".").strip()
        if not cleaned:
            return None
        # Округляем до 2 знаков при необходимости
        d = Decimal(cleaned)
        return d.quantize(Decimal("0.01"))
    except (InvalidOperation, Exception):  # noqa: BLE001
        return None


def _extract_part_number(text: str) -> str:
    # Берём до первой скобки или первого перевода строки/двойного пробела
    base = (text or "").strip()
    if not base:
        return base
    for sep in [" (", "\n", "  "]:
        if sep in base:
            base = base.split(sep, 1)[0].strip()
    # Дополнительно ограничим до первого пробела, если осталось несколько слов
    if " " in base:
        base = base.split(" ", 1)[0].strip()
    return base


@shared_task
def prom_crawl_active_categories_brands(
    username: str | None = None,
    password: str | None = None,
    headless: bool = True,
    category_ext_ids: list[str] | None = None,
    brand_ext_ids: list[str] | None = None,
    max_pages_per_pair: int | None = None,
):
    """
    Проходит по всем активным категориям и активным брендам конкурента Promelec,
    открывает страницы вида https://office.promelec.ru/goods/{cat_ext}/{brand_ext}/,
    парсит таблицу товаров с пагинацией и сохраняет позиции/снимки цен/наличия.

    Args:
        username: Логин PROM (если не указан — PROM_LOGIN из окружения)
        password: Пароль PROM (если не указан — PROM_PASSWORD из окружения)
        headless: Режим браузера Playwright
        category_ext_ids: Ограничение по списку ext_id категорий конкурента
        brand_ext_ids: Ограничение по списку ext_id брендов конкурента
        max_pages_per_pair: Ограничение числа страниц для каждой пары категория×бренд

    Returns:
        dict: Статистика по обработанным парам и позициям
    """

    user = username or os.getenv("PROM_LOGIN")
    pwd = password or os.getenv("PROM_PASSWORD")
    if not user or not pwd:
        logger.error("Не заданы PROM_LOGIN/PROM_PASSWORD")
        return {"success": False, "error": "PROM_LOGIN/PROM_PASSWORD не заданы"}

    # Находим конкурента и активные категории/бренды
    competitor, _ = Competitor.objects.get_or_create(
        name="Promelec",
        defaults={
            "site_url": "",
            "b2b_site_url": "https://office.promelec.ru/",
            "is_active": True,
        },
    )
    if not competitor.b2b_site_url:
        competitor.b2b_site_url = "https://office.promelec.ru/"
        competitor.save(update_fields=["b2b_site_url"])

    categories_qs = (
        CompetitorCategory.objects.filter(competitor=competitor, is_active=True)
        .exclude(ext_id__isnull=True)
        .exclude(ext_id__exact="")
    )
    brands_qs = (
        CompetitorBrand.objects.filter(competitor=competitor, is_active=True)
        .exclude(ext_id__isnull=True)
        .exclude(ext_id__exact="")
    )
    if category_ext_ids:
        categories_qs = categories_qs.filter(ext_id__in=category_ext_ids)
    if brand_ext_ids:
        brands_qs = brands_qs.filter(ext_id__in=brand_ext_ids)

    categories = list(categories_qs.values("id", "ext_id"))
    brands = list(brands_qs.values("id", "ext_id"))

    if not categories or not brands:
        return {
            "success": True,
            "processed_pairs": 0,
            "items_created": 0,
            "items_updated": 0,
            "snapshots_created": 0,
            "skipped": 0,
            "note": "Нет активных категорий или брендов",
        }

    async def _run() -> dict:
        from bs4 import BeautifulSoup

        created_items = 0
        updated_items = 0
        created_snaps = 0
        skipped_rows = 0
        processed_pairs = 0

        async with PromClient(headless=headless) as client:
            await client.login_and_get_session(user, pwd)

            # Итерируем пары категория×бренд
            for cat in categories:
                for br in brands:
                    url = f"https://office.promelec.ru/goods/{cat['ext_id']}/{br['ext_id']}/"
                    try:
                        await client.page.goto(url, wait_until="domcontentloaded")
                        # Ждём появления таблицы или информации об отсутствии результатов
                        try:
                            await client.page.wait_for_selector("table#search_goods, #search_goods_wrapper", timeout=15000)
                            # Ждём исчезновения индикатора загрузки
                            await client.page.wait_for_selector("#search_goods_processing", state="hidden", timeout=30000)
                        except Exception:
                            # Похоже, пусто/ошибка — пропустим пару
                            logger.warning(f"Timeout waiting for table/data on {url}")
                            processed_pairs += 1
                            continue

                        pages_done = 0
                        while True:
                            # Парсим текущую страницу
                            html = await client.page.content()
                            soup = BeautifulSoup(html, "lxml")
                            tbody = soup.select_one("table#search_goods tbody")
                            rows = soup.select("table#search_goods tbody tr[id]") if tbody else []
                            logger.info(f"URL {url} (page {pages_done+1}): table found={bool(tbody)}, tbody found={bool(tbody)}, rows found={len(rows)}")
                            if pages_done == 0 and not rows:
                                # Для первой страницы сохраним HTML для отладки
                                logger.info(f"Debug HTML for {url}: {html[:1000]}...")
                            if not rows:
                                # Возможно, нет записей для пары
                                break

                            now = timezone.now()
                            with transaction.atomic():
                                for tr in rows:
                                    ext_id = str(tr.get("id") or "").strip()
                                    tds = tr.find_all("td")
                                    if not ext_id or not tds:
                                        skipped_rows += 1
                                        continue

                                    # Первая колонка: part_number и название
                                    name_cell = tr.select_one("td.G_NAME") or tds[0]
                                    title_full = name_cell.get_text(" ", strip=True)
                                    part_number = _extract_part_number(title_full)
                                    name_span = name_cell.select_one("span.text-1")
                                    name = (name_span.get_text(" ", strip=True) if name_span else title_full)[:255]

                                    # Бренд (дублируется, но сверим на всякий случай)
                                    brand_cell = tr.select_one("td.PRODUCERNAME")
                                    brand_name = brand_cell.get_text(" ", strip=True) if brand_cell else None

                                    # Кол-во в наличии и цены
                                    qty_cell = tr.select_one("td.ITEM_REMAIN")
                                    qty_in_stock = _parse_int(qty_cell.get_text(strip=True) if qty_cell else None)

                                    price_stock_cell = None
                                    try:
                                        price_stock_cell = tr.find_all("td")[4]
                                    except Exception:
                                        price_stock_cell = None
                                    price_ex_vat = _parse_decimal(price_stock_cell.get_text(strip=True) if price_stock_cell else None)

                                    delivery_cell = tr.find_all("td")[7] if len(tds) > 7 else None
                                    delivery_days_min = _parse_int(delivery_cell.get_text(strip=True)) if delivery_cell else None

                                    # Upsert CompetitorProduct по (competitor, part_number)
                                    obj, created = CompetitorProduct.objects.update_or_create(
                                        competitor=competitor,
                                        part_number=part_number,
                                        defaults={
                                            "ext_id": ext_id,
                                            "name": name,
                                            "brand_id": br["id"],
                                            "category_id": cat["id"],
                                        },
                                    )
                                    if created:
                                        created_items += 1
                                    else:
                                        # Обновим поля, если изменились
                                        changed = False
                                        if obj.ext_id != ext_id:
                                            obj.ext_id = ext_id
                                            changed = True
                                        if obj.name != name:
                                            obj.name = name
                                            changed = True
                                        if obj.brand_id != br["id"]:
                                            obj.brand_id = br["id"]
                                            changed = True
                                        if obj.category_id != cat["id"]:
                                            obj.category_id = cat["id"]
                                            changed = True
                                        if changed:
                                            obj.save(update_fields=["ext_id", "name", "brand", "category", "updated_at"])  # type: ignore[arg-type]
                                            updated_items += 1
                                        else:
                                            skipped_rows += 1

                                    # Снимок цены/наличия
                                    CompetitorPriceStockSnapshot.objects.get_or_create(
                                        competitor=competitor,
                                        competitor_product=obj,
                                        collected_at=now,
                                        defaults={
                                            "price_ex_vat": price_ex_vat,
                                            "vat_rate": None,
                                            "price_inc_vat": None,
                                            "currency": "RUB",
                                            "stock_qty": qty_in_stock,
                                            "stock_status": CompetitorPriceStockSnapshot.StockStatus.IN_STOCK
                                            if qty_in_stock and qty_in_stock > 0
                                            else CompetitorPriceStockSnapshot.StockStatus.OUT_OF_STOCK,
                                            "delivery_days_min": delivery_days_min,
                                            "delivery_days_max": None,
                                            "raw_payload": {
                                                "row_ext_id": ext_id,
                                                "title_full": title_full,
                                                "brand_name": brand_name,
                                                "qty_in_stock": qty_in_stock,
                                                "price_ex_vat": str(price_ex_vat) if price_ex_vat is not None else None,
                                                "delivery_days_min": delivery_days_min,
                                                "source_url": url,
                                            },
                                        },
                                    )
                                    created_snaps += 1

                            # Переход на следующую страницу, если доступна
                            if max_pages_per_pair is not None and pages_done + 1 >= max_pages_per_pair:
                                break

                            # Проверяем кнопку "next"
                            try:
                                next_disabled = await client.page.locator("#search_goods_paginate .page-item.next.disabled").count()
                                if next_disabled and int(next_disabled) > 0:
                                    break
                                await client.page.click("#search_goods_paginate .page-item.next a")
                                await client.page.wait_for_load_state("domcontentloaded")
                                pages_done += 1
                            except Exception:
                                break

                        processed_pairs += 1
                    except Exception as e:  # noqa: BLE001
                        logger.warning("Ошибка при обработке URL %s: %s", url, e)
                        processed_pairs += 1
                        continue

        return {
            "processed_pairs": processed_pairs,
            "items_created": created_items,
            "items_updated": updated_items,
            "snapshots_created": created_snaps,
            "skipped": skipped_rows,
        }

    try:
        result = asyncio.run(_run())
        msg = {
            "success": True,
            **result,
            "categories": len(categories),
            "brands": len(brands),
        }
        logger.info("PROM crawl завершён: %s", msg)
        return msg
    except PromAuthError as e:
        logger.warning("PROM auth failed: %s", e)
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        logger.error("Ошибка prom_crawl_active_categories_brands: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
