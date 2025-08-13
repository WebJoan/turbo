from langchain_core.tools import tool
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
import json
import urllib.request
import urllib.error
import urllib.parse
import csv
import io
import os
import time
import threading
import base64


def _stooq_variants(symbol: str) -> List[str]:
    s = (symbol or "").strip().lower()
    if not s:
        return []
    # Пробуем сначала .us (для американских тикеров), затем без суффикса
    variants = [f"{s}.us", s]
    # Уберём дубликаты, сохраняя порядок
    seen = set()
    uniq: List[str] = []
    for v in variants:
        if v not in seen:
            uniq.append(v)
            seen.add(v)
    return uniq


def _stooq_fetch_name(symbol_variant: str) -> Optional[str]:
    # Пробуем получить имя компании: f=sn -> Symbol,Name
    url = f"https://stooq.com/q/l/?s={symbol_variant}&f=sn&e=csv"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(raw))
        rows = [r for r in reader if r]
        if not rows:
            return None
        # Если есть заголовок, пропускаем
        if len(rows) >= 2 and rows[0] and rows[0][0].lower() == "symbol":
            data_row = rows[1]
        else:
            data_row = rows[0]
        if len(data_row) >= 2 and data_row[1].strip():
            name = data_row[1].strip()
            if name.upper() != "N/D":
                return name
        return None
    except Exception:
        return None


def _stooq_fetch_history(symbol_variant: str) -> List[Dict[str, str]]:
    # Исторические дневные данные
    url = f"https://stooq.com/q/d/l/?s={symbol_variant}&i=d"
    try:
        with urllib.request.urlopen(url, timeout=12) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(raw))
        rows = [r for r in reader if r and r.get("Close") and r["Close"].lower() != "null"]
        return rows
    except urllib.error.HTTPError as e:
        raise ValueError(f"HTTP ошибка Stooq: {e.code}")
    except urllib.error.URLError as e:
        raise ValueError(f"Сеть недоступна или таймаут Stooq: {e.reason}")
    except Exception as e:
        raise ValueError(f"Ошибка разбора данных Stooq: {e}")


@tool(return_direct=True)
def get_stock_price(stock_symbol: str):
    """Котировки через Stooq (бесплатно, без ключа).

    Возвращает: {symbol, company_name, current_price, change, change_percent, volume, market_cap, pe_ratio, fifty_two_week_high, fifty_two_week_low, timestamp}
    Некоторые поля (market_cap, pe_ratio) могут быть недоступны и заполняются как "N/A"/0.0.
    """
    raw_symbol = (stock_symbol or "").strip()
    symbol_up = raw_symbol.upper()
    if not raw_symbol:
        raise ValueError("Укажите тикер, например: AAPL")

    last_working_variant: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = None
    for variant in _stooq_variants(raw_symbol):
        try:
            h = _stooq_fetch_history(variant)
            if h and len(h) >= 1 and h[-1].get("Close") and h[-1]["Close"].lower() != "null":
                history = h
                last_working_variant = variant
                break
        except Exception:
            continue

    if not history or not last_working_variant:
        raise ValueError(f"Не удалось получить данные для тикера: {symbol_up}")

    # Имя компании
    company_name = _stooq_fetch_name(last_working_variant) or symbol_up

    # Последняя и предыдущая свечи
    # В CSV Stooq порядок по дате от старой к новой. Возьмём последние 2 валидные строки.
    valid_rows = [r for r in history if r.get("Close") and r["Close"].lower() != "null"]
    if len(valid_rows) == 0:
        raise ValueError(f"Нет валидных цен для тикера: {symbol_up}")
    last = valid_rows[-1]
    prev = valid_rows[-2] if len(valid_rows) >= 2 else None

    def _to_float(v: Optional[str]) -> float:
        try:
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    current_price = _to_float(last.get("Close"))
    previous_close = _to_float(prev.get("Close")) if prev else current_price
    change = current_price - previous_close
    change_percent = (change / previous_close * 100.0) if previous_close else 0.0
    volume = int(float(last.get("Volume") or 0))

    # 52 недели: возьмём последние 365 календарных дней
    def _to_date(s: str) -> Optional[datetime]:
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    window_rows = [r for r in valid_rows if (_to_date(r.get("Date", "")) or datetime.now(timezone.utc)) >= one_year_ago]
    if not window_rows:
        window_rows = valid_rows[-252:]  # ~252 торговых дня

    highs = [_to_float(r.get("High")) for r in window_rows if r.get("High")]
    lows = [_to_float(r.get("Low")) for r in window_rows if r.get("Low")]
    fifty_two_week_high = max(highs) if highs else current_price
    fifty_two_week_low = min(lows) if lows else current_price

    # timestamp из последней даты
    last_date = last.get("Date")
    if last_date:
        timestamp = f"{last_date}T00:00:00Z"
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "symbol": symbol_up,
        "company_name": company_name,
        "current_price": float(current_price),
        "change": float(change),
        "change_percent": float(change_percent),
        "volume": volume,
        "market_cap": "N/A",
        "pe_ratio": 0.0,
        "fifty_two_week_high": float(fifty_two_week_high),
        "fifty_two_week_low": float(fifty_two_week_low),
        "timestamp": timestamp,
    }


tools = [get_stock_price]


def _metal_code(metal: str) -> Optional[str]:
    m = (metal or "").strip().lower()
    mapping = {
        "gold": "XAU",
        "xau": "XAU",
        "silver": "XAG",
        "xag": "XAG",
        "platinum": "XPT",
        "xpt": "XPT",
        "palladium": "XPD",
        "xpd": "XPD",
    }
    return mapping.get(m)


@tool(return_direct=True)
def get_metal_price(metal: str, currency: str = "USD"):
    """Цена драгоценных металлов по бесплатному API Stooq.

    Поддерживаемые металлы: gold (XAU), silver (XAG), platinum (XPT), palladium (XPD).
    Валюта котировки (currency) по умолчанию USD. Возвращает последние дневные данные.

    Возвращает: {symbol, metal, currency, current_price, change, change_percent, fifty_two_week_high, fifty_two_week_low, timestamp}
    """
    code = _metal_code(metal)
    if not code:
        raise ValueError("Укажите один из металлов: gold, silver, platinum, palladium")

    cur = (currency or "USD").strip().upper()
    pair_symbol = f"{code}{cur}"
    stooq_symbol = pair_symbol.lower()  # пример: xauusd

    history = _stooq_fetch_history(stooq_symbol)
    valid_rows = [r for r in history if r.get("Close") and r["Close"].lower() != "null"]
    if not valid_rows:
        raise ValueError(f"Нет данных для пары: {pair_symbol}")

    last = valid_rows[-1]
    prev = valid_rows[-2] if len(valid_rows) >= 2 else None

    def _to_float(v: Optional[str]) -> float:
        try:
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    current_price = _to_float(last.get("Close"))
    previous_close = _to_float(prev.get("Close")) if prev else current_price
    change = current_price - previous_close
    change_percent = (change / previous_close * 100.0) if previous_close else 0.0

    # 52W окно
    def _to_date(s: str) -> Optional[datetime]:
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    window_rows = [r for r in valid_rows if (_to_date(r.get("Date", "")) or datetime.now(timezone.utc)) >= one_year_ago]
    if not window_rows:
        window_rows = valid_rows[-252:]  # ~252 торговых дня

    highs = [_to_float(r.get("High")) for r in window_rows if r.get("High")]
    lows = [_to_float(r.get("Low")) for r in window_rows if r.get("Low")]
    fifty_two_week_high = max(highs) if highs else current_price
    fifty_two_week_low = min(lows) if lows else current_price

    last_date = last.get("Date")
    timestamp = f"{last_date}T00:00:00Z" if last_date else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "symbol": pair_symbol,
        "metal": code,
        "currency": cur,
        "current_price": float(current_price),
        "change": float(change),
        "change_percent": float(change_percent),
        "fifty_two_week_high": float(fifty_two_week_high),
        "fifty_two_week_low": float(fifty_two_week_low),
        "timestamp": timestamp,
        "source": "stooq",
    }


BACKEND_API_BASE_URL = os.getenv("BACKEND_API_BASE_URL", "http://api:8000")
BACKEND_API_JWT_TOKEN = os.getenv("BACKEND_API_JWT_TOKEN")

# Автологин сервис-аккаунтом, если заданы креды окружения
BACKEND_API_USERNAME = os.getenv("BACKEND_API_USERNAME")
BACKEND_API_PASSWORD = os.getenv("BACKEND_API_PASSWORD")
BACKEND_API_TOKEN_URL = os.getenv("BACKEND_API_TOKEN_URL", f"{BACKEND_API_BASE_URL.rstrip('/')}/api/token/")
BACKEND_API_REFRESH_URL = os.getenv("BACKEND_API_REFRESH_URL", f"{BACKEND_API_BASE_URL.rstrip('/')}/api/token/refresh/")

_token_lock = threading.Lock()
_access_token: Optional[str] = None
_refresh_token: Optional[str] = None
_access_exp_epoch: Optional[int] = None


def _base64url_decode(input_str: str) -> bytes:
    padding = '=' * (-len(input_str) % 4)
    return base64.urlsafe_b64decode(input_str + padding)


def _extract_exp_from_jwt(token: str) -> Optional[int]:
    try:
        parts = token.split('.')
        if len(parts) < 2:
            return None
        payload_bytes = _base64url_decode(parts[1])
        payload = json.loads(payload_bytes.decode('utf-8'))
        exp = payload.get('exp')
        if isinstance(exp, int):
            return exp
        return None
    except Exception:
        return None


def _http_json(url: str, data: Dict[str, object], timeout: int = 10) -> Dict[str, object]:
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} {url}: {detail}")
    except Exception as e:
        raise RuntimeError(str(e))


def _jwt_login_if_needed() -> None:
    global _access_token, _refresh_token, _access_exp_epoch
    if not BACKEND_API_USERNAME or not BACKEND_API_PASSWORD:
        return
    if _access_token and _access_exp_epoch and (time.time() < _access_exp_epoch - 120):
        return
    with _token_lock:
        if _access_token and _access_exp_epoch and (time.time() < _access_exp_epoch - 120):
            return
        payload = {"username": BACKEND_API_USERNAME, "password": BACKEND_API_PASSWORD}
        data = _http_json(BACKEND_API_TOKEN_URL, payload, timeout=10)
        access = str(data.get("access") or "")
        refresh = str(data.get("refresh") or "")
        if not access:
            raise RuntimeError("Не удалось получить access токен от DRF /api/token/")
        _access_token = access
        _refresh_token = refresh or None
        _access_exp_epoch = _extract_exp_from_jwt(access)


def _jwt_refresh_if_needed() -> None:
    global _access_token, _refresh_token, _access_exp_epoch
    if not _refresh_token:
        return
    if _access_exp_epoch and time.time() < _access_exp_epoch - 60:
        return
    with _token_lock:
        if _access_exp_epoch and time.time() < _access_exp_epoch - 60:
            return
        try:
            data = _http_json(BACKEND_API_REFRESH_URL, {"refresh": _refresh_token}, timeout=10)
            access = str(data.get("access") or "")
            if access:
                _access_token = access
                _access_exp_epoch = _extract_exp_from_jwt(access)
                return
        except Exception:
            pass
        # Если рефреш не удался — пробуем перелогиниться
        _access_token = None
        _refresh_token = None
        _access_exp_epoch = None
        _jwt_login_if_needed()


def _get_backend_access_token() -> Optional[str]:
    # Приоритет: явный токен из окружения
    if BACKEND_API_JWT_TOKEN:
        return BACKEND_API_JWT_TOKEN
    # Если заданы креды — логинимся и поддерживаем токен свежим
    try:
        _jwt_login_if_needed()
        _jwt_refresh_if_needed()
        return _access_token
    except Exception:
        return None


def _make_authenticated_request(url: str, method: str = "GET", data: Optional[Dict] = None, timeout: int = 10):
    """Вспомогательная функция для выполнения аутентифицированных запросов к Django API."""
    req_data = None
    if data and method in ["POST", "PUT", "PATCH"]:
        req_data = json.dumps(data).encode("utf-8")
    
    req = urllib.request.Request(url, data=req_data, method=method)
    
    # Добавляем Content-Type для POST/PUT/PATCH запросов
    if req_data:
        req.add_header("Content-Type", "application/json")
    
    # Добавляем JWT аутентификацию: сначала явный токен, иначе авто‑логин по кредам
    token = _get_backend_access_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            response_data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        return response_data
    except urllib.error.HTTPError as e:
        error_detail = ""
        try:
            error_detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        return {"error": f"HTTP {e.code}", "detail": error_detail}
    except Exception as e:
        return {"error": str(e)}


# (FINAM-интеграция удалена)


MEILISEARCH_URL = os.getenv("MEILISEARCH_URL", os.getenv("MEILI_URL", "http://meilisearch:7700"))
MEILISEARCH_API_KEY = os.getenv("MEILISEARCH_API_KEY", os.getenv("MEILI_MASTER_KEY"))


@tool(return_direct=True)
def search_products_smart(
    category: Optional[str] = None,
    subcategory: Optional[str] = None, 
    brand: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 10,
    sort_by: Optional[str] = None,
    include_tech_params: bool = True
):
    """Умный поиск товаров в каталоге с автоматическим определением фильтров.
    
    Этот инструмент понимает естественные запросы и автоматически строит правильные фильтры.
    
    Параметры:
    - category: фильтр по основной категории (группе товаров) 
    - subcategory: фильтр по подкатегории (подгруппе товаров)
    - brand: фильтр по бренду (например: "ST", "TI", "Analog Devices")
    - query: основной поисковый запрос (название, артикул, техпараметры) - ОПЦИОНАЛЬНЫЙ
    - limit: количество результатов (по умолчанию 10)
    - sort_by: сортировка ("name", "brand", "relevance") 
    - include_tech_params: включить технические параметры в результат
    
    Примеры использования:
    - search_products_smart(brand="ST") - все товары бренда ST
    - search_products_smart(category="МИКРОСХЕМЫ *") - все микросхемы
    - search_products_smart(subcategory="Потенциометры") - все потенциометры
    - search_products_smart(category="Разъемы") - все разъемы
    - search_products_smart(query="STM32", brand="ST") - поиск STM32 от ST
    """
    
    # Подготавливаем базовый запрос
    search_query = (query or "").strip()
    filters = []
    
    # Строим фильтры на основе параметров
    if brand:
        filters.append(f'brand_name = "{brand}"')
    
    if category:
        filters.append(f'group_name = "{category}"')
        
    if subcategory:
        filters.append(f'subgroup_name = "{subcategory}"')
    
    # Объединяем фильтры
    filter_string = " AND ".join(filters) if filters else None
    
    # Настраиваем сортировку
    sort_rules = []
    if sort_by == "name":
        sort_rules = ["name:asc"]
    elif sort_by == "brand":
        sort_rules = ["brand_name:asc", "name:asc"]
    # По умолчанию используется релевантность Meilisearch
    
    # Определяем какие поля возвращать
    attributes_to_retrieve = [
        "ext_id", "name", "brand_name", "group_name", "subgroup_name", 
        "product_manager_name", "complex_name", "description"
    ]
    if include_tech_params:
        attributes_to_retrieve.append("tech_params")

    # Выполняем поиск через базовую функцию
    result = _execute_meilisearch_query(
        query=search_query if search_query else None,
        filters=filter_string,
        limit=limit,
        sort=sort_rules,
        attributes_to_retrieve=attributes_to_retrieve
    )
    
    if "error" in result:
        return result
    
    # Обогащаем результат контекстной информацией для AI
    hits = result.get("hits", [])
    total = result.get("estimatedTotalHits", 0)
    
    # Группируем результаты по брендам для лучшего понимания
    brands = {}
    categories = {}
    
    for hit in hits:
        brand_name = hit.get("brand_name", "Неизвестный")
        if brand_name not in brands:
            brands[brand_name] = 0
        brands[brand_name] += 1
        
        group_name = hit.get("group_name", "Неизвестная")
        if group_name not in categories:
            categories[group_name] = 0
        categories[group_name] += 1
    
    # Формируем умный ответ
    response = {
        "query": search_query,
        "total_found": total,
        "showing": len(hits),
        "products": hits,
        "search_context": {
            "brands_found": brands,
            "categories_found": categories,
            "applied_filters": {
                "brand": brand,
                "category": category, 
                "subcategory": subcategory
            }
        },
        "processing_time_ms": result.get("processingTimeMs", 0)
    }
    
    return response


def _execute_meilisearch_query(
    query: Optional[str] = None,
    filters: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    sort: Optional[List[str]] = None,
    attributes_to_retrieve: Optional[List[str]] = None,
    highlight: bool = True,
):
    """Базовая функция для выполнения запросов к Meilisearch."""
    q = (query or "").strip()
    if not q and not filters:
        raise ValueError("Укажите хотя бы query или filters для поиска")

    url = f"{MEILISEARCH_URL.rstrip('/')}/indexes/products/search"
    body: Dict[str, object] = {"q": q, "limit": max(1, int(limit)), "offset": max(0, int(offset))}

    if filters:
        body["filter"] = filters
    if sort:
        body["sort"] = [str(s) for s in sort if str(s).strip()]
    if attributes_to_retrieve:
        body["attributesToRetrieve"] = [str(a) for a in attributes_to_retrieve if str(a).strip()]
    if highlight:
        body["attributesToHighlight"] = ["*"]
        body["highlightPreTag"] = "<em>"
        body["highlightPostTag"] = "</em>"

    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    # Поддержим оба варианта заголовков ключа API
    if MEILISEARCH_API_KEY:
        req.add_header("Authorization", f"Bearer {MEILISEARCH_API_KEY}")
        req.add_header("X-Meilisearch-API-Key", MEILISEARCH_API_KEY)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        # Нормализуем ответ
        return {
            "hits": data.get("hits", []),
            "limit": data.get("limit"),
            "offset": data.get("offset"),
            "estimatedTotalHits": data.get("estimatedTotalHits"),
            "processingTimeMs": data.get("processingTimeMs"),
            "query": data.get("query", q),
        }
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = ""
        return {"error": f"HTTP {e.code}", "detail": detail}
    except Exception as e:
        return {"error": str(e)}


@tool(return_direct=True)  
def search_products_meilisearch(
    query: Optional[str] = None,
    filters: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    sort: Optional[List[str]] = None,
    attributes_to_retrieve: Optional[List[str]] = None,
    highlight: bool = True,
):
    """Базовый поиск товаров в Meilisearch (для обратной совместимости).
    
    Рекомендуется использовать search_products_smart для более умного поиска.
    """
    return _execute_meilisearch_query(
        query=query,
        filters=filters, 
        limit=limit,
        offset=offset,
        sort=sort,
        attributes_to_retrieve=attributes_to_retrieve,
        highlight=highlight
    )


@tool(return_direct=True)
def get_rfqs(partnumber: Optional[str] = None, brand: Optional[str] = None, page: int = 1):
    """Получить список RFQ из Django.

    Параметры фильтрации: partnumber, brand (частичное совпадение). Пагинация: page.
    Возвращает ответ пагинации DRF с полем results.
    """
    params = []
    if partnumber:
        params.append(("partnumber", partnumber))
    if brand:
        params.append(("brand", brand))
    params.append(("page", str(page)))
    query = "&".join([f"{k}={urllib.parse.quote(v)}" for k, v in params]) if params else ""
    url = f"{BACKEND_API_BASE_URL}/api/rfqs/" + (f"?{query}" if query else "")
    return _make_authenticated_request(url, method="GET", timeout=10)


def _pick_best_company_match(name: str, candidates: List[Dict]) -> Optional[Dict]:
    """Эвристика выбора лучшего совпадения по названию компании.
    1) Точное совпадение по name (без регистра)
    2) Точное совпадение по short_name (без регистра)
    3) Кандидат, в котором запрос является подстрокой name/short_name (без регистра)
    4) Первый в списке
    """
    q = (name or "").strip().lower()
    if not q or not candidates:
        return candidates[0] if candidates else None
    # 1) exact by name
    for c in candidates:
        if str(c.get("name", "")).strip().lower() == q:
            return c
    # 2) exact by short_name
    for c in candidates:
        if str(c.get("short_name", "")).strip().lower() == q:
            return c
    # 3) substring
    for c in candidates:
        n = str(c.get("name", "")).strip().lower()
        sn = str(c.get("short_name", "")).strip().lower()
        if q and (q in n or (sn and q in sn)):
            return c
    # 4) fallback
    return candidates[0]


def _resolve_company_id_by_name(company_name: str) -> Optional[int]:
    search = urllib.parse.quote((company_name or "").strip())
    url = f"{BACKEND_API_BASE_URL}/api/companies/?search={search}"
    resp = _make_authenticated_request(url, method="GET", timeout=10)
    if not isinstance(resp, dict):
        return None
    # DRF пагинация возвращает {count, next, previous, results: [...]}
    candidates: List[Dict] = []
    if "results" in resp and isinstance(resp["results"], list):
        candidates = resp["results"]
    elif isinstance(resp, list):  # на случай если пагинации нет
        candidates = resp  # type: ignore
    else:
        # Возможно вернулся объект с ошибкой
        if resp.get("error"):
            return None
    best = _pick_best_company_match(company_name, candidates)
    if best and isinstance(best.get("id"), int):
        return best["id"]
    try:
        return int(best.get("id")) if best and best.get("id") is not None else None
    except Exception:
        return None


@tool(return_direct=True)
def find_company_by_name(name: str, limit: int = 10):
    """Найти компанию по названию. Возвращает список совпадений с полями id, name, short_name, inn.

    Использует эндпоинт /api/companies/?search=.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Укажите название компании")
    url = f"{BACKEND_API_BASE_URL}/api/companies/?search={urllib.parse.quote(name)}"
    resp = _make_authenticated_request(url, method="GET", timeout=10)
    # Приведём ответ к единому формату с results
    if isinstance(resp, dict) and "results" in resp:
        # Ограничим количество выводимых результатов
        resp["results"] = list(resp.get("results", []))[: max(1, int(limit))]
        return resp
    if isinstance(resp, list):
        return {"results": resp[: max(1, int(limit))]}
    return resp


@tool(return_direct=True)
def create_rfq(
    partnumber: Optional[str] = None,
    brand: Optional[str] = None,
    qty: Optional[int] = None,
    target_price: Optional[float] = None,
    company_id: Optional[int] = None,
    company_name: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    # Поля шапки RFQ (необязательные)
    priority: Optional[str] = None,
    deadline: Optional[str] = None,
    delivery_address: Optional[str] = None,
    payment_terms: Optional[str] = None,
    delivery_terms: Optional[str] = None,
    notes: Optional[str] = None,
    contact_person_id: Optional[int] = None,
    # Полный формат: массив строк RFQ
    items: Optional[List[Dict]] = None,
):
    """Создать RFQ в Django (POST /api/rfqs/), поддерживает два формата.

    Вариант A (простой): передайте `partnumber`, `brand`, `qty` (+ опционально `target_price`, `company_id` или `company_name`, `title`, `description`).
    Вариант B (структурный): передайте `items` — массив позиций, а также любые поля шапки (`company_id`, `title`, `description`, `priority`, `deadline`, `delivery_address`, `payment_terms`, `delivery_terms`, `notes`, `contact_person_id`).

    Структура items[i]: { product: int (id товара) | опц., product_name: str, manufacturer: str, part_number: str, quantity: int, unit: str="шт", specifications: str, comments: str, is_new_product: bool, line_number: int }
    """
    url = f"{BACKEND_API_BASE_URL}/api/rfqs/"
    payload: Dict[str, object] = {}

    # Простой формат
    if partnumber is not None:
        payload["partnumber"] = str(partnumber).strip()
    if brand is not None:
        payload["brand"] = str(brand).strip()
    if qty is not None:
        try:
            payload["qty"] = int(qty)
        except Exception:
            pass
    if target_price is not None:
        try:
            payload["target_price"] = float(target_price)
        except Exception:
            pass

    # Шапка RFQ
    # Разрешаем указание company_name вместо company_id. В таком случае попытаемся найти id по имени.
    if company_id is None and company_name:
        try:
            resolved_id = _resolve_company_id_by_name(company_name)
            if resolved_id is not None:
                company_id = resolved_id
        except Exception:
            pass
    if company_id is not None:
        try:
            payload["company_id"] = int(company_id)
        except Exception:
            pass
    if contact_person_id is not None:
        try:
            payload["contact_person_id"] = int(contact_person_id)
        except Exception:
            pass

    for field_name, value in [
        ("title", title),
        ("description", description),
        ("priority", priority),
        ("deadline", deadline),
        ("delivery_address", delivery_address),
        ("payment_terms", payment_terms),
        ("delivery_terms", delivery_terms),
        ("notes", notes),
    ]:
        if value is not None and str(value).strip() != "":
            payload[field_name] = value

    # Полный формат: массив строк
    if items:
        normalized_items: List[Dict] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            item_payload: Dict[str, object] = {}
            # Числовые поля
            if "product" in raw and raw.get("product") is not None:
                try:
                    item_payload["product"] = int(raw.get("product"))
                except Exception:
                    pass
            if "quantity" in raw and raw.get("quantity") is not None:
                try:
                    item_payload["quantity"] = int(raw.get("quantity"))
                except Exception:
                    continue  # quantity обязателен
            if "line_number" in raw and raw.get("line_number") is not None:
                try:
                    item_payload["line_number"] = int(raw.get("line_number"))
                except Exception:
                    pass
            # Строковые поля
            for k in [
                "product_name",
                "manufacturer",
                "part_number",
                "unit",
                "specifications",
                "comments",
            ]:
                if k in raw and raw.get(k) is not None:
                    item_payload[k] = str(raw.get(k))
            # Булево
            if "is_new_product" in raw and raw.get("is_new_product") is not None:
                item_payload["is_new_product"] = bool(raw.get("is_new_product"))

            # Минимальная проверка
            if "quantity" in item_payload:
                normalized_items.append(item_payload)
        if normalized_items:
            payload["items"] = normalized_items

    result = _make_authenticated_request(url, method="POST", data=payload, timeout=15)
    # Более дружелюбные сообщения об ошибках
    if isinstance(result, dict) and result.get("error"):
        detail = result.get("detail", "")
        if result["error"] == "HTTP 400" and "Нет компаний для привязки RFQ" in detail:
            return {
                "error": "Компания не найдена",
                "detail": "В бекенде нет ни одной компании. Создайте компанию или передайте company_id.",
            }
    return result

# --- Django Database Tools ---
@tool(return_direct=True)
def get_product_by_ext_id(ext_id: str):
    """Получить товар по точному ext_id из базы данных Django.
    
    Параметры:
    - ext_id: точный внешний ID товара (важное поле для менеджеров)
    
    Возвращает подробную информацию о товаре включая:
    - основные данные (название, описание)
    - информацию о группе, подгруппе, бренде
    - назначенного менеджера
    - технические параметры
    """
    ext_id = (ext_id or "").strip()
    if not ext_id:
        raise ValueError("Параметр ext_id обязателен")
    
    url = f"{BACKEND_API_BASE_URL}/api/products/by_ext_id/?ext_id={urllib.parse.quote(ext_id)}"
    result = _make_authenticated_request(url, method="GET", timeout=10)
    
    # Обрабатываем специальный случай 404 для более понятного сообщения
    if result.get("error") == "HTTP 404":
        return {"error": f"Товар с ext_id '{ext_id}' не найден", "ext_id": ext_id}
    
    return result


@tool(return_direct=True)
def search_products_database(
    search: Optional[str] = None,
    ext_id: Optional[str] = None,
    name: Optional[str] = None,
    brand_name: Optional[str] = None,
    group_name: Optional[str] = None,
    subgroup_name: Optional[str] = None,
    manager_id: Optional[int] = None,
    ordering: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    """Поиск товаров в базе данных Django с различными фильтрами.
    
    Параметры:
    - search: общий поиск по всем ключевым полям (ext_id, название, описание, бренд)
    - ext_id: поиск по части ext_id (для частичного совпадения)
    - name: поиск по названию товара
    - brand_name: фильтр по названию бренда
    - group_name: фильтр по группе товаров
    - subgroup_name: фильтр по подгруппе товаров
    - manager_id: ID менеджера (учитывает иерархию: товар -> бренд -> подгруппа)
    - ordering: сортировка (name, ext_id, created_at, updated_at, можно добавить -)
    - page: номер страницы (по умолчанию 1)
    - page_size: размер страницы (по умолчанию 20, максимум 100)
    
    Возвращает: список товаров с базовой информацией и пагинацией
    """
    params = []
    
    if search:
        params.append(("search", search))
    if ext_id:
        params.append(("ext_id_contains", ext_id))
    if name:
        params.append(("name", name))
    if brand_name:
        params.append(("brand_name", brand_name))
    if group_name:
        params.append(("group_name", group_name))
    if subgroup_name:
        params.append(("subgroup_name", subgroup_name))
    if manager_id:
        params.append(("manager_id", str(manager_id)))
    if ordering:
        params.append(("ordering", ordering))
    
    params.append(("page", str(page)))
    params.append(("page_size", str(min(max(page_size, 1), 100))))  # ограничиваем 1-100
    
    query = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params])
    url = f"{BACKEND_API_BASE_URL}/api/products/?" + query
    
    return _make_authenticated_request(url, method="GET", timeout=15)


@tool(return_direct=True)
def get_product_details(product_id: int):
    """Получить подробную информацию о товаре по его ID из базы данных Django.
    
    Параметры:
    - product_id: ID товара в базе данных
    
    Возвращает полную информацию о товаре включая технические параметры
    """
    try:
        product_id = int(product_id)
    except (ValueError, TypeError):
        raise ValueError("product_id должен быть числом")
    
    url = f"{BACKEND_API_BASE_URL}/api/products/{product_id}/"
    result = _make_authenticated_request(url, method="GET", timeout=10)
    
    # Обрабатываем специальный случай 404 для более понятного сообщения
    if result.get("error") == "HTTP 404":
        return {"error": f"Товар с ID {product_id} не найден"}
    
    return result


@tool(return_direct=True)
def get_products_by_manager(manager_id: int, page: int = 1, page_size: int = 20):
    """Получить все товары назначенные конкретному менеджеру.
    
    Учитывает иерархию назначения менеджера:
    1. Товар назначен напрямую менеджеру
    2. Товар принадлежит бренду, назначенному менеджеру  
    3. Товар принадлежит подгруппе, назначенной менеджеру
    
    Параметры:
    - manager_id: ID менеджера
    - page: номер страницы
    - page_size: размер страницы (максимум 100)
    """
    try:
        manager_id = int(manager_id)
    except (ValueError, TypeError):
        raise ValueError("manager_id должен быть числом")
    
    params = [
        ("manager_id", str(manager_id)),
        ("page", str(page)),
        ("page_size", str(min(max(page_size, 1), 100)))
    ]
    
    query = "&".join([f"{k}={urllib.parse.quote(v)}" for k, v in params])
    url = f"{BACKEND_API_BASE_URL}/api/products/by_manager/?" + query
    
    return _make_authenticated_request(url, method="GET", timeout=15)


@tool(return_direct=True)
def get_product_groups():
    """Получить список всех групп товаров."""
    url = f"{BACKEND_API_BASE_URL}/api/product-groups/"
    return _make_authenticated_request(url, method="GET", timeout=10)


@tool(return_direct=True)
def get_product_subgroups(group_id: Optional[int] = None):
    """Получить список подгрупп товаров, опционально отфильтрованных по группе.
    
    Параметры:
    - group_id: ID группы для фильтрации (опционально)
    """
    params = []
    if group_id:
        try:
            group_id = int(group_id)
            params.append(("group", str(group_id)))
        except (ValueError, TypeError):
            raise ValueError("group_id должен быть числом")
    
    query = "&".join([f"{k}={urllib.parse.quote(v)}" for k, v in params])
    url = f"{BACKEND_API_BASE_URL}/api/product-subgroups/?" + (query if query else "")
    
    return _make_authenticated_request(url, method="GET", timeout=10)


@tool(return_direct=True)
def get_brands():
    """Получить список всех брендов."""
    url = f"{BACKEND_API_BASE_URL}/api/brands/"
    return _make_authenticated_request(url, method="GET", timeout=10)


tools = [
    get_stock_price,
    get_metal_price,
    search_products_meilisearch,
    get_rfqs,
    create_rfq,
    find_company_by_name,
    #search_duckduckgo,
    search_products_smart,
    # Новые инструменты для работы с базой данных товаров
    get_product_by_ext_id,
    search_products_database,
    get_product_details,
    get_products_by_manager,
    get_product_groups,
    get_product_subgroups,
    get_brands,
]
