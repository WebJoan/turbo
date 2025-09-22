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
from .models import OurPriceHistory
from .clients import PromClient, PromAuthError


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

    numeric_nodes: dict[str, dict] = {}
    for node in flat_nodes or []:
        node_id = str(node.get("id", ""))
        if not _is_numeric_id(node_id):
            continue
        text = (node.get("text") or "").strip()
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
                        "is_active": True,
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
                        obj.is_active = True
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
