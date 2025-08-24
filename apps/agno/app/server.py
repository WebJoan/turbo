# Импорт необходимых библиотек для веб-сервера FastAPI и асинхронных операций
import fastapi
from fastapi import FastAPI  # Основной фреймворк FastAPI для веб-API
from fastapi.middleware.cors import CORSMiddleware  # CORS middleware для браузерных запросов
from fastapi.responses import StreamingResponse  # Для стриминга ответов в реальном времени
import uuid  # Для генерации уникальных идентификаторов
from typing import Any  # Подсказки типов для лучшей документации кода
import os  # Интерфейс операционной системы для переменных окружения
import uvicorn  # ASGI сервер для запуска приложений FastAPI
import asyncio  # Асинхронный ввод-вывод и управление циклом событий

# Импорт компонентов системы событий из ag_ui.core для обновлений UI в реальном времени
from ag_ui.core import (
    RunAgentInput,  # Структура входных данных для запросов агента
    StateSnapshotEvent,  # Событие для отправки текущего состояния в UI
    EventType,  # Перечисление всех возможных типов событий
    RunStartedEvent,  # Событие сигнализирующее о начале работы агента
    RunFinishedEvent,  # Событие сигнализирующее о завершении работы агента
    TextMessageStartEvent,  # Событие для начала стриминга текстового сообщения
    TextMessageEndEvent,  # Событие для завершения стриминга текстового сообщения
    TextMessageContentEvent,  # Событие для стриминга фрагментов текстового содержимого
    ToolCallStartEvent,  # Событие для начала вызовов инструментов/функций
    ToolCallEndEvent,  # Событие для завершения вызовов инструментов/функций
    ToolCallArgsEvent,  # Событие для стриминга аргументов инструментов
    StateDeltaEvent,  # Событие для инкрементальных обновлений состояния
)

# Импорт кодировщика событий для форматирования событий для стриминга
from ag_ui.encoder import EventEncoder  # Кодирует события для потребления клиентом

from typing import List  # Подсказка типа для списков



# Импорт аутентификации
from .auth import get_user_from_request  # Функция для получения пользователя из запроса

# Инициализация экземпляра приложения FastAPI
app = FastAPI(title="Agno Agent API", description="API для агента общего назначения")

# Настройка CORS middleware для разрешения браузерных запросов
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить все источники (в продакшене указать конкретные домены)
    allow_credentials=True,  # Разрешить отправку куки и авторизационных данных
    allow_methods=["*"],  # Разрешить все HTTP методы
    allow_headers=["*"],  # Разрешить все заголовки
)






# ОСНОВНОЙ ENDPOINT API: Обработка запросов к агенту общего назначения
# Этот endpoint получает запросы и стримит ответы в реальном времени
@app.post("/agno-agent")
async def agno_agent(input_data: RunAgentInput):
    """
    Главный endpoint для взаимодействия с агентом.
    Принимает запросы пользователей и возвращает стримовые ответы.
    """
    try:
        # АСИНХРОННЫЙ ГЕНЕРАТОР: Стримит события клиенту в реальном времени
        # Эта функция генерирует поток событий, которые отправляются фронтенду
        async def event_generator():
            # Шаг 1: Инициализация инфраструктуры стриминга событий
            encoder = EventEncoder()  # Кодирует события для передачи
            event_queue = asyncio.Queue()  # Очередь для обработки событий из рабочего процесса

            # Шаг 2: Определение callback функции для отправки событий
            # Эта функция вызывается шагами рабочего процесса для отправки обновлений в UI
            def emit_event(event):
                event_queue.put_nowait(event)  # Добавить событие в очередь без блокировки

            # Шаг 3: Генерация уникального идентификатора сообщения для этого разговора
            message_id = str(uuid.uuid4())

            # Шаг 4: Отправка начального события "запуск начат" клиенту
            # Сигнализирует UI, что агент начал обработку
            yield encoder.encode(
                RunStartedEvent(
                    type=EventType.RUN_STARTED,
                    thread_id=getattr(input_data, "thread_id", None) or str(uuid.uuid4()),
                    run_id=getattr(input_data, "run_id", None) or str(uuid.uuid4()),
                )
            )

            # Шаг 5: Отправка текущего снимка состояния клиенту
            # Предоставляет начальное состояние
            yield encoder.encode(
                StateSnapshotEvent(
                    type=EventType.STATE_SNAPSHOT,
                    snapshot={
                        "messages": getattr(input_data, "messages", []) or [],
                        "state": getattr(input_data, "state", {}) or {},
                        "tool_logs": [],
                    },
                )
            )
            
            # Шаг 6: Симуляция обработки запроса (здесь должна быть ваша логика агента)
            # В реальном приложении здесь будет вызов вашего агента/модели
            await asyncio.sleep(0.5)  # Имитация времени обработки
            
            # Шаг 7: Начало стриминга текстового сообщения
            # Сигнал UI, что начинается текстовое сообщение
            yield encoder.encode(
                TextMessageStartEvent(
                    type=EventType.TEXT_MESSAGE_START,
                    message_id=message_id,
                    role="assistant",  # Сообщение от ИИ-ассистента
                )
            )

            # Шаг 8: Генерация ответа (заглушка - здесь должна быть ваша логика)
            # Если есть последнее пользовательское сообщение, ответим на него эхо-сообщением
            response_text = "Привет! Я агент общего назначения. Как дела? Чем могу помочь?"
            try:
                messages = getattr(input_data, "messages", []) or []
                user_messages = [m for m in messages if getattr(m, "role", getattr(m, "get", lambda _k: None)("role")) == "user"]
                last_user = None
                if messages:
                    # Попытка получить последнее сообщение пользователя, с учётом форматов dict/obj
                    for m in reversed(messages):
                        role = getattr(m, "role", None)
                        if role is None and isinstance(m, dict):
                            role = m.get("role")
                        if role == "user":
                            last_user = m
                            break
                if last_user is not None:
                    content = getattr(last_user, "content", None)
                    if content is None and isinstance(last_user, dict):
                        content = last_user.get("content")
                    if content:
                        response_text = f"Вы сказали: {content}"
            except Exception:
                pass
            
            # Шаг 9: Разбиение сообщения на части для эффекта печати
            # Разделение содержимого на 50 частей для плавного вывода
            n_parts = 50
            part_length = max(1, len(response_text) // n_parts)  # Убедиться, что минимум 1 символ на часть
            parts = [
                response_text[i : i + part_length]
                for i in range(0, len(response_text), part_length)
            ]
            
            # Шаг 10: Обработка крайнего случая, когда разделение создает слишком много частей
            if len(parts) > n_parts:
                parts = parts[: n_parts - 1] + ["".join(parts[n_parts - 1 :])]
            
            # Шаг 11: Стрим каждого фрагмента содержимого с задержкой для эффекта печати
            for part in parts:
                yield encoder.encode(
                    TextMessageContentEvent(
                        type=EventType.TEXT_MESSAGE_CONTENT,
                        message_id=message_id,
                        delta=part,  # Фрагмент содержимого сообщения
                    )
                )
                await asyncio.sleep(0.03)  # Небольшая задержка для эффекта печати

            # Шаг 12: Завершение стриминга текстового сообщения
            # Сигнал UI, что текстовое сообщение завершено
            yield encoder.encode(
                TextMessageEndEvent(
                    type=EventType.TEXT_MESSAGE_END,
                    message_id=message_id,
                )
            )

            # Шаг 13: Очистка логов инструментов после завершения
            # Отправка события для сброса логов инструментов в UI
            yield encoder.encode(
                StateDeltaEvent(
                    type=EventType.STATE_DELTA,
                    delta=[{"op": "replace", "path": "/tool_logs", "value": []}],
                )
            )

            # Шаг 14: Отправка финального события "запуск завершен"
            # Сигнал клиенту, что весь запуск агента завершен
            yield encoder.encode(
                RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id=getattr(input_data, "thread_id", None) or str(uuid.uuid4()),
                    run_id=getattr(input_data, "run_id", None) or str(uuid.uuid4()),
                )
            )


        # Шаг 15: Возврат стримингового ответа клиенту
        # FastAPI будет стримить события как Server-Sent Events (SSE)
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        # Шаг 16: Обработка любых ошибок во время выполнения
        print(f"❌ Ошибка: {e}")  # Логирование ошибки для отладки
        
        async def error_generator():
            try:
                error_encoder = EventEncoder()
                yield error_encoder.encode(
                    TextMessageContentEvent(
                        type=EventType.TEXT_MESSAGE_CONTENT,
                        message_id=str(uuid.uuid4()),
                        delta="Извините, произошла ошибка. Попробуйте еще раз.",
                    )
                )
            except:
                yield "data: Извините, произошла ошибка. Попробуйте еще раз.\n\n"
        
        return StreamingResponse(error_generator(), media_type="text/event-stream")


# ENDPOINT ДЛЯ ПРОВЕРКИ СОСТОЯНИЯ: Простая проверка работоспособности сервера
@app.get("/health")
async def health_check():
    """Проверка состояния сервера."""
    return {
        "status": "ok",
        "message": "Сервер agno работает нормально"
    }


# ENDPOINT ДЛЯ ИНФОРМАЦИИ О ПОЛЬЗОВАТЕЛЕ: Получение данных авторизованного пользователя
@app.get("/user")
async def get_current_user(request: fastapi.Request):
    """Получить информацию о текущем пользователе из JWT токена."""
    try:
        user_info = get_user_from_request(request)
        if user_info:
            return {
                "authenticated": True,
                "user": {
                    "id": user_info.user_id,
                    "username": user_info.username
                }
            }
        else:
            return {"authenticated": False, "user": None}
    except Exception as e:
        print(f"❌ Ошибка получения пользователя: {e}")
        return {"authenticated": False, "error": str(e)}


# ФУНКЦИЯ ЗАПУСКА СЕРВЕРА: Инициализация и запуск сервера FastAPI
def main():
    """Запуск uvicorn сервера."""
    # Шаг 1: Получение порта из переменной окружения или значение по умолчанию 8000
    port = int(os.getenv("PORT", "8000"))
    
    # Шаг 2: Запуск uvicorn ASGI сервера с конфигурацией
    uvicorn.run(
        "app.server:app",  # Ссылка на модуль:приложение
        host="0.0.0.0",  # Прослушивание на всех сетевых интерфейсах
        port=port,  # Номер порта
        reload=True,  # Авто-перезагрузка при изменении кода (режим разработки)
    )


# Точка входа для прямого запуска скрипта
if __name__ == "__main__":
    main()
