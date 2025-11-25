# WordStat API MCP сервер для Agno агента
"""
MCP сервер для работы с WordStat API Яндекса.
Предоставляет инструменты для анализа поисковых запросов и статистики.
"""

import os
import json
import requests
import asyncio
from typing import List, Optional, Dict, Any
from fastmcp import FastMCP
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Инициализация FastMCP сервера
app = FastMCP(
    name="WordStat MCP Server",
    description="Сервер для работы с WordStat API Яндекса. Предоставляет инструменты для анализа поисковых запросов."
)

# Базовый URL API
WORDSTAT_BASE_URL = "https://api.wordstat.yandex.net/v1"

# Получаем токен авторизации из переменных окружения
# Пробуем оба варианта названия переменной для совместимости
WORDSTAT_TOKEN = os.getenv("WORDSTAT_API_TOKEN") or os.getenv("WORDSTAT_TOKEN")

def make_wordstat_request(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Выполняет HTTP запрос к WordStat API.

    Args:
        endpoint: Конечная точка API (без базового URL)
        payload: Тело запроса в формате JSON

    Returns:
        Ответ API в виде словаря

    Raises:
        Exception: При ошибке запроса или авторизации
    """
    if not WORDSTAT_TOKEN:
        raise Exception("WORDSTAT_API_TOKEN не найден в переменных окружения")

    url = f"{WORDSTAT_BASE_URL}/{endpoint}"
    headers = {
        "Content-Type": "application/json;charset=utf-8",
        "Authorization": f"Bearer {WORDSTAT_TOKEN}"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Ошибка при запросе к WordStat API: {str(e)}")

@app.tool()
async def get_regions_tree() -> Dict[str, Any]:
    """
    Получить дерево регионов, поддерживаемых WordStat API.

    Возвращает иерархическую структуру регионов для использования в других методах API.
    Этот метод не расходует квоту запросов.

    Returns:
        Словарь с деревом регионов
    """
    try:
        result = make_wordstat_request("getRegionsTree", {})
        return {
            "success": True,
            "data": result,
            "message": "Дерево регионов успешно получено"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Не удалось получить дерево регионов"
        }

@app.tool()
async def get_top_requests(
    phrase: str,
    num_phrases: Optional[int] = 50,
    regions: Optional[List[int]] = None,
    devices: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Получить топ популярных запросов, содержащих указанную фразу.

    Args:
        phrase: Фраза для поиска (можно использовать язык запросов)
        num_phrases: Количество фраз в ответе (максимум 2000, по умолчанию 50)
        regions: Список идентификаторов регионов (по умолчанию все регионы)
        devices: Список типов устройств ["all", "desktop", "phone", "tablet"] (по умолчанию "all")

    Returns:
        Словарь с топом запросов и статистикой
    """
    try:
        # Валидация параметров
        if not phrase or not phrase.strip():
            return {
                "success": False,
                "error": "Параметр 'phrase' обязателен и не может быть пустым",
                "message": "Необходимо указать поисковую фразу"
            }

        if num_phrases and (num_phrases < 1 or num_phrases > 2000):
            return {
                "success": False,
                "error": "num_phrases должен быть от 1 до 2000",
                "message": "Неверное количество фраз в ответе"
            }

        if devices:
            valid_devices = ["all", "desktop", "phone", "tablet"]
            invalid_devices = [d for d in devices if d not in valid_devices]
            if invalid_devices:
                return {
                    "success": False,
                    "error": f"Недопустимые типы устройств: {invalid_devices}",
                    "message": f"Допустимые значения: {valid_devices}"
                }

        # Формируем payload
        payload = {
            "phrase": phrase.strip()
        }

        if num_phrases and num_phrases != 50:
            payload["numPhrases"] = num_phrases

        if regions:
            payload["regions"] = regions

        if devices:
            payload["devices"] = devices

        result = make_wordstat_request("topRequests", payload)

        return {
            "success": True,
            "data": result,
            "phrase": phrase,
            "total_count": result.get("totalCount", 0),
            "top_requests_count": len(result.get("topRequests", [])),
            "associations_count": len(result.get("associations", [])),
            "message": f"Получен топ запросов для фразы '{phrase}'"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "phrase": phrase,
            "message": "Не удалось получить топ запросов"
        }

@app.tool()
async def get_dynamics(
    phrase: str,
    period: str,
    from_date: str,
    to_date: Optional[str] = None,
    regions: Optional[List[int]] = None,
    devices: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Получить динамику числа запросов во времени по заданной фразе.

    Args:
        phrase: Фраза для анализа (допускается только оператор +)
        period: Период агрегации ("monthly", "weekly", "daily")
        from_date: Начало периода в формате YYYY-MM-DD
        to_date: Конец периода в формате YYYY-MM-DD (опционально)
        regions: Список идентификаторов регионов (опционально)
        devices: Список типов устройств ["all", "desktop", "phone", "tablet"] (опционально)

    Returns:
        Словарь с динамикой запросов
    """
    try:
        # Валидация параметров
        if not phrase or not phrase.strip():
            return {
                "success": False,
                "error": "Параметр 'phrase' обязателен и не может быть пустым",
                "message": "Необходимо указать поисковую фразу"
            }

        valid_periods = ["monthly", "weekly", "daily"]
        if period not in valid_periods:
            return {
                "success": False,
                "error": f"period должен быть одним из: {valid_periods}",
                "message": "Неверный период агрегации"
            }

        if devices:
            valid_devices = ["all", "desktop", "phone", "tablet"]
            invalid_devices = [d for d in devices if d not in valid_devices]
            if invalid_devices:
                return {
                    "success": False,
                    "error": f"Недопустимые типы устройств: {invalid_devices}",
                    "message": f"Допустимые значения: {valid_devices}"
                }

        # Формируем payload
        payload = {
            "phrase": phrase.strip(),
            "period": period,
            "fromDate": from_date
        }

        if to_date:
            payload["toDate"] = to_date

        if regions:
            payload["regions"] = regions

        if devices:
            payload["devices"] = devices

        result = make_wordstat_request("dynamics", payload)

        return {
            "success": True,
            "data": result,
            "phrase": phrase,
            "period": period,
            "from_date": from_date,
            "to_date": to_date,
            "dynamics_count": len(result.get("dynamics", [])),
            "message": f"Получена динамика запросов для фразы '{phrase}'"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "phrase": phrase,
            "message": "Не удалось получить динамику запросов"
        }

@app.tool()
async def get_regions_distribution(
    phrase: str,
    region_type: Optional[str] = "all",
    devices: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Получить распределение числа запросов по регионам за последние 30 дней.

    Args:
        phrase: Фраза для анализа
        region_type: Тип регионов ("cities", "regions", "all") по умолчанию "all"
        devices: Список типов устройств ["all", "desktop", "phone", "tablet"] (опционально)

    Returns:
        Словарь с распределением по регионам
    """
    try:
        # Валидация параметров
        if not phrase or not phrase.strip():
            return {
                "success": False,
                "error": "Параметр 'phrase' обязателен и не может быть пустым",
                "message": "Необходимо указать поисковую фразу"
            }

        valid_region_types = ["cities", "regions", "all"]
        if region_type not in valid_region_types:
            return {
                "success": False,
                "error": f"regionType должен быть одним из: {valid_region_types}",
                "message": "Неверный тип регионов"
            }

        if devices:
            valid_devices = ["all", "desktop", "phone", "tablet"]
            invalid_devices = [d for d in devices if d not in valid_devices]
            if invalid_devices:
                return {
                    "success": False,
                    "error": f"Недопустимые типы устройств: {invalid_devices}",
                    "message": f"Допустимые значения: {valid_devices}"
                }

        # Формируем payload
        payload = {
            "phrase": phrase.strip(),
            "regionType": region_type
        }

        if devices:
            payload["devices"] = devices

        result = make_wordstat_request("regions", payload)

        return {
            "success": True,
            "data": result,
            "phrase": phrase,
            "region_type": region_type,
            "regions_count": len(result.get("regions", [])),
            "message": f"Получено распределение запросов по регионам для фразы '{phrase}'"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "phrase": phrase,
            "message": "Не удалось получить распределение по регионам"
        }

@app.tool()
async def get_user_info() -> Dict[str, Any]:
    """
    Получить информацию о пользователе: лимиты запросов, остаток дневной квоты.

    Returns:
        Словарь с информацией о пользователе
    """
    try:
        result = make_wordstat_request("userInfo", {})

        return {
            "success": True,
            "data": result,
            "message": "Информация о пользователе успешно получена"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Не удалось получить информацию о пользователе"
        }

if __name__ == "__main__":
    # Запуск MCP сервера
    import mcp.server.stdio
    mcp.server.stdio.stdio_server(app.to_server())
