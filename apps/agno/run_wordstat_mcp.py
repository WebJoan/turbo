#!/usr/bin/env python3
"""
Скрипт для запуска WordStat MCP сервера.
"""

import sys
import os

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.wordstat_mcp import app
import mcp.server.stdio

if __name__ == "__main__":
    print("🚀 Запуск WordStat MCP сервера...", file=sys.stderr)
    print("Сервер предоставляет инструменты для работы с WordStat API Яндекса", file=sys.stderr)
    print("Доступные инструменты:", file=sys.stderr)
    print("- get_regions_tree: получение дерева регионов", file=sys.stderr)
    print("- get_top_requests: топ популярных запросов", file=sys.stderr)
    print("- get_dynamics: динамика запросов во времени", file=sys.stderr)
    print("- get_regions_distribution: распределение по регионам", file=sys.stderr)
    print("- get_user_info: информация о пользователе", file=sys.stderr)
    print("", file=sys.stderr)

    # Запуск MCP сервера
    mcp.server.stdio.stdio_server(app.to_server())
