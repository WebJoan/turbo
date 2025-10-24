SHELL := /bin/bash

# Настройки
COMPOSE ?= docker compose
SERVICE ?=
APP ?=
ARGS ?=

.PHONY: help up down restart ps logs build pull clean reset \
        api-shell migrate makemigrations collectstatic superuser test \
        web-install web-dev openapi update-products index-products reindex-smart test-search test-rag \
        setup-embedder reindex-rag setup-embedder-reindex rag-test-search rag-status \
        prom-login prom-import-brands prom-import-categories prom-crawl-goods prom-crawl-category rebuild-backend \
        import-prom-from-ftp

.DEFAULT_GOAL := help

help: ## Показать это сообщение помощи
	@echo "Доступные команды:"
	@echo "  make up                 - Поднять все сервисы в фоне"
	@echo "  make down               - Остановить и удалить контейнеры"
	@echo "  make restart [SERVICE=] - Перезапустить (все или указанный сервис)"
	@echo "  make ps                 - Статус контейнеров"
	@echo "  make logs [SERVICE=]    - Логи (всех или указанного сервиса)"
	@echo "  make build [SERVICE=]   - Сборка образов"
	@echo "  make pull [SERVICE=]    - Обновить образы"
	@echo "  make clean              - Остановить и удалить осиротевшие контейнеры"
	@echo "  make reset              - Полная очистка: контейнеры + тома"
	@echo "  make migrate [ARGS=]    - Django migrate"
	@echo "  make makemigrations APP=имя [ARGS=] - Django makemigrations"
	@echo "  make api-shell          - Открыть Django shell в контейнере api"
	@echo "  make superuser [ARGS=]  - Создать суперпользователя"
	@echo "  make collectstatic      - Собрать статику"
	@echo "  make test [ARGS=]       - Запустить тесты бэкенда (pytest)"
	@echo "  make web-install        - pnpm install -r во фронтенде"
	@echo "  make web-dev            - Запустить фронтенд dev-сервер"
	@echo "  make openapi            - Сгенерировать типы OpenAPI во фронтенде"
	@echo "  make update-products    - Обновить товары из MySQL"
	@echo "  make index-products     - Стандартная индексация товаров в MeiliSearch"
	@echo "  make reindex-smart      - Улучшенная переиндексация с новыми настройками"
	@echo "  make test-search        - Протестировать улучшенный поиск товаров"
	@echo "  make test-rag QUERY=\"текст\" - Протестировать RAG систему поиска товаров"
	@echo "  make setup-embedder     - Настроить эмбеддер в Meilisearch"
	@echo "  make reindex-rag        - Переиндексировать товары для RAG"
	@echo "  make setup-embedder-reindex - Настроить эмбеддер и переиндексировать"
	@echo "  make rag-test-search QUERY=\"GX12M\" - Протестировать RAG-поиск через manage.py"
	@echo "  make rag-status         - Показать статус Meilisearch и индекса"
	@echo "  make prom-login PROM_LOGIN=логин PROM_PASSWORD=пароль - Логин в PROM (Celery)"
	@echo "  make prom-import-brands PROM_LOGIN=логин PROM_PASSWORD=пароль - Спарсить бренды с PROM"
	@echo "  make prom-import-categories PROM_LOGIN=логин PROM_PASSWORD=пароль - Спарсить рубрикатор (категории) с PROM"
	@echo "  make prom-crawl-goods PROM_LOGIN=логин PROM_PASSWORD=пароль [CAT=1,2] [BRAND=10,20] [PAGES=3] - Обход активных категорий×брендов и парсинг товаров"
	@echo "  make prom-crawl-category PROM_LOGIN=логин PROM_PASSWORD=пароль CAT_ID=2545 [PAGES=3] - Парсинг товаров из конкретной категории PROM (без брендов)"
	@echo "  make import-prom-from-ftp - Импортировать данные PROM из FTP (Item.csv)"
	@echo "  make rebuild-backend    - Пересобрать backend образы с Playwright"

# Базовые операции с docker compose
up: ## Поднять все сервисы (в фоне)
	$(COMPOSE) up --build

down: ## Остановить и удалить контейнеры
	$(COMPOSE) down

restart: ## Перезапустить сервис(ы). Пример: make restart SERVICE=api
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) restart $(SERVICE); \
	else \
		$(COMPOSE) restart; \
	fi

ps: ## Показать статус контейнеров
	$(COMPOSE) ps

logs: ## Поток логов. Пример: make logs SERVICE=api
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) logs -f $(SERVICE); \
	else \
		$(COMPOSE) logs -f; \
	fi

build: ## Сборка образов
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) build $(SERVICE); \
	else \
		$(COMPOSE) build; \
	fi

pull: ## Обновить образы из реестра
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) pull $(SERVICE); \
	else \
		$(COMPOSE) pull; \
	fi

clean: ## Остановить и удалить осиротевшие контейнеры/сети
	$(COMPOSE) down --remove-orphans

reset: ## Полная очистка: контейнеры + тома
	$(COMPOSE) down -v --remove-orphans

# Бэкенд (Django / uv) — выполняется в контейнере api
api-shell: ## Открыть Django shell
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py shell"

migrate: ## Выполнить миграции
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py migrate $(ARGS)"

makemigrations: ## Создать миграции для приложения: make makemigrations APP=app_name
	@if [ -z "$(APP)" ]; then \
		echo "Укажите APP=имя_приложения"; exit 1; \
	fi
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py makemigrations $(APP) $(ARGS)"

superuser: ## Создать суперпользователя
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py createsuperuser $(ARGS)"

collectstatic: ## Собрать статику
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py collectstatic --noinput"

test: ## Запустить тесты (pytest)
	$(COMPOSE) exec api bash -lc "uv run -- pytest -q $(ARGS)"

# Фронтенд (pnpm) — выполняется в контейнере web
web-install: ## Установка зависимостей (pnpm -r)
	$(COMPOSE) exec web bash -lc "pnpm install -r"

web-dev: ## Запуск dev-сервера фронтенда
	$(COMPOSE) exec web bash -lc "pnpm --filter web dev"

openapi: ## Генерация типов OpenAPI во фронтенде
	$(COMPOSE) exec web bash -lc "pnpm run openapi:generate"

update-clients: ## Запустить Celery-задачу обновления клиентов из MySQL
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py shell -c \"from customers.tasks import update_clients_from_mysql; update_clients_from_mysql.delay(); print('queued: update_clients_from_mysql')\""

update-products: ## Запустить Celery-задачу обновления товаров из MySQL
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py shell -c \"from goods.tasks import update_products_from_mysql; update_products_from_mysql.delay(); print('queued: update_products_from_mysql')\""

update-datasheets: ## Запустить Celery-задачу обновления даташитов
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py shell -c \"from goods.tasks import download_all_datasheets; download_all_datasheets.delay(); print('queued: download_all_datasheets')\""

update-drawings: ## Запустить Celery-задачу обновления чертежей
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py shell -c \"from goods.tasks import download_all_drawings; download_all_drawings.delay(); print('queued: download_all_drawings')\""

index-products: ## Запустить Celery-задачу индексации товаров в MeiliSearch
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py shell -c \"from goods.tasks import index_products_atomically; index_products_atomically.delay(); print('queued: index_products_atomically')\""

reindex-smart: ## Запустить улучшенную Celery-задачу переиндексации с новыми настройками
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py shell -c \"from goods.tasks import reindex_products_smart; reindex_products_smart.delay(); print('🚀 queued: reindex_products_smart - Улучшенная переиндексация запущена!')\""

import-histprice: ## Запустить Celery-задачу импорта истории цен из MySQL
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py shell -c \"from stock.tasks import import_histprice_from_mysql; import_histprice_from_mysql.delay(); print('queued: import_histprice_from_mysql')\""

import-prom-from-ftp: ## Импортировать данные PROM из FTP (Item.csv)
	$(COMPOSE) exec api bash -lc "uv run -- python manage.py shell -c \"from stock.tasks import import_prom_from_ftp; import_prom_from_ftp.delay(); print('queued: import_prom_from_ftp')\""
