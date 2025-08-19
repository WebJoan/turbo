"""
API views для работы с RAG системой поиска товаров
"""
import logging
from typing import List, Dict, Any

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.request import Request
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

from goods.rag_utils import (
    HuggingFaceEmbedder, 
    MeilisearchRAGService, 
    ProductRAGChain,
    get_rag_service,
    get_rag_chain
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
def generate_embeddings_internal(request: Request) -> Response:
    """
    Внутренний эндпоинт для генерации эмбедингов (используется Meilisearch)
    Без авторизации для внутреннего использования
    """
    try:
        data = request.data
        
        # Логируем входящие данные для отладки
        logger.info(f"Получен запрос на генерацию эмбедингов: {data}")
        
        # Meilisearch отправляет данные в формате {"text": "содержимое"} для одного документа
        # или массив строк для batch запросов
        texts = []
        
        if isinstance(data, dict) and 'text' in data:
            # Стандартный формат Meilisearch: {"text": "содержимое"}
            texts = [str(data['text'])]
        elif isinstance(data, list):
            # Batch запрос - массив строк или объектов с text
            for item in data:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict) and 'text' in item:
                    texts.append(str(item['text']))
                else:
                    texts.append(str(item))
        elif isinstance(data, dict) and 'texts' in data:
            # Альтернативный формат для множественных текстов
            item_texts = data['texts']
            if isinstance(item_texts, list):
                texts = [str(t) for t in item_texts]
            else:
                texts = [str(item_texts)]
        else:
            # Fallback - пытаемся преобразовать данные как есть
            texts = [str(data)]
        
        if not texts:
            logger.error(f"Не удалось извлечь тексты из запроса: {data}")
            return Response(
                {"error": "Не удалось извлечь тексты из запроса"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Ограничиваем количество текстов для безопасности
        if len(texts) > 100:
            texts = texts[:100]
        
        # Генерируем эмбединги
        embedder = HuggingFaceEmbedder()
        embeddings = embedder.embed_batch(texts)
        
        logger.info(f"Сгенерированы эмбединги для {len(texts)} текстов, размерность: {len(embeddings[0]) if embeddings else 0}")
        
        return Response({
            "embeddings": embeddings
        })
        
    except Exception as e:
        logger.error(f"Ошибка генерации эмбедингов: {e}")
        return Response(
            {"error": f"Ошибка генерации эмбедингов: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    request={
        "type": "object",
        "properties": {
            "texts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список текстов для генерации эмбедингов"
            }
        },
        "required": ["texts"]
    },
    responses={
        200: {
            "type": "object", 
            "properties": {
                "embeddings": {
                    "type": "array",
                    "items": {
                        "type": "array", 
                        "items": {"type": "number"}
                    },
                    "description": "Список векторных эмбедингов"
                }
            }
        }
    },
    summary="Генерация эмбедингов",
    description="Эндпоинт для генерации векторных эмбедингов с помощью HuggingFace модели"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_embeddings(request: Request) -> Response:
    """
    Генерирует векторные эмбединги для текстов с помощью HuggingFace модели
    Используется Meilisearch для векторного поиска
    """
    try:
        texts = request.data.get('texts', [])
        
        if not texts or not isinstance(texts, list):
            return Response(
                {"error": "Поле 'texts' обязательно и должно быть списком строк"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Ограничиваем количество текстов для безопасности
        if len(texts) > 100:
            return Response(
                {"error": "Максимальное количество текстов для обработки: 100"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Генерируем эмбединги
        embedder = HuggingFaceEmbedder()
        embeddings = embedder.embed_batch([str(text) for text in texts])
        
        return Response({
            "embeddings": embeddings
        })
        
    except Exception as e:
        logger.error(f"Ошибка генерации эмбедингов: {e}")
        return Response(
            {"error": f"Ошибка генерации эмбедингов: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name='query',
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Поисковый запрос о товарах'
        ),
        OpenApiParameter(
            name='limit',
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Количество результатов (по умолчанию: 10, максимум: 50)'
        ),
        OpenApiParameter(
            name='semantic_ratio',
            type=float,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Соотношение семантического поиска (0.0-1.0, по умолчанию: 0.7)'
        ),
        OpenApiParameter(
            name='threshold',
            type=float,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Минимальный порог релевантности (0.0-1.0, по умолчанию: 0.3)'
        ),
    ],
    responses={
        200: {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Исходный запрос"},
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "ext_id": {"type": "string"},
                            "name": {"type": "string"},
                            "complex_name": {"type": "string"},
                            "brand": {"type": "string"},
                            "group": {"type": "string"},
                            "manager": {"type": "string"},
                            "relevance": {"type": "number"},
                            "tech_params": {"type": "object"}
                        }
                    }
                },
                "total_found": {"type": "integer", "description": "Общее количество найденных товаров"}
            }
        }
    },
    summary="Гибридный поиск товаров",
    description="Интеллектуальный поиск товаров с помощью комбинации семантического и полнотекстового поиска",
    examples=[
        OpenApiExample(
            'Поиск по названию',
            value='резистор 10 кОм',
            request_only=True,
        ),
        OpenApiExample(
            'Поиск по характеристикам',
            value='микроконтроллер ARM 32-битный',
            request_only=True,
        ),
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hybrid_search_products(request: Request) -> Response:
    """
    Выполняет гибридный поиск товаров (семантический + полнотекстовый)
    """
    try:
        query = request.query_params.get('query', '').strip()
        if not query:
            return Response(
                {"error": "Параметр 'query' обязателен"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Парсим параметры
        limit = min(int(request.query_params.get('limit', 10)), 50)
        semantic_ratio = float(request.query_params.get('semantic_ratio', 0.7))
        threshold = float(request.query_params.get('threshold', 0.3))
        
        # Валидация параметров
        if not (0.0 <= semantic_ratio <= 1.0):
            return Response(
                {"error": "semantic_ratio должен быть от 0.0 до 1.0"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not (0.0 <= threshold <= 1.0):
            return Response(
                {"error": "threshold должен быть от 0.0 до 1.0"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Выполняем поиск
        rag_service = get_rag_service()
        search_results = rag_service.hybrid_search(
            query=query,
            limit=limit,
            semantic_ratio=semantic_ratio,
            ranking_score_threshold=threshold
        )

        # Если ничего не найдено, а запрос похож на короткий артикул/код, 
        # пробуем более строгий текстовый поиск без эмбеддингов и порога
        def _looks_like_short_code(text: str) -> bool:
            s = text.strip()
            if len(s) == 0:
                return False
            # До 12 символов и в основном буквенно-цифровой
            alnum_ratio = sum(ch.isalnum() for ch in s) / max(1, len(s))
            return len(s) <= 12 and alnum_ratio >= 0.6

        if not search_results and _looks_like_short_code(query):
            search_results = rag_service.hybrid_search(
                query=query,
                limit=limit,
                semantic_ratio=0.0,
                ranking_score_threshold=0.0
            )
        
        # Формируем ответ
        products = []
        for result in search_results:
            products.append({
                "id": result.product_id,
                "ext_id": result.ext_id,
                "name": result.name,
                "complex_name": result.complex_name,
                "brand": result.brand_name,
                "group": f"{result.group_name} > {result.subgroup_name}",
                "manager": result.product_manager_name,
                "relevance": result.relevance_score,
                "tech_params": result.tech_params,
                "description": result.description
            })
        
        return Response({
            "query": query,
            "products": products,
            "total_found": len(products),
            "search_params": {
                "limit": limit,
                "semantic_ratio": semantic_ratio,
                "threshold": threshold
            }
        })
        
    except ValueError as e:
        return Response(
            {"error": f"Неверный формат параметра: {str(e)}"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return Response(
            {"error": f"Ошибка поиска: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    request={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Вопрос о товарах на русском языке"
            },
            "search_limit": {
                "type": "integer",
                "description": "Количество товаров для поиска (по умолчанию: 5)"
            },
            "semantic_ratio": {
                "type": "number",
                "description": "Соотношение семантического поиска (по умолчанию: 0.7)"
            }
        },
        "required": ["question"]
    },
    responses={
        200: {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Исходный вопрос"},
                "answer": {"type": "string", "description": "Ответ на основе найденных товаров"},
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "ext_id": {"type": "string"},
                            "name": {"type": "string"},
                            "complex_name": {"type": "string"},
                            "brand": {"type": "string"},
                            "group": {"type": "string"},
                            "manager": {"type": "string"},
                            "relevance": {"type": "number"},
                            "tech_params": {"type": "object"}
                        }
                    }
                },
                "context_used": {"type": "string", "description": "Контекст, использованный для ответа"}
            }
        }
    },
    summary="RAG поиск с ответами",
    description="Интеллектуальный поиск товаров с генерацией ответов на естественном языке",
    examples=[
        OpenApiExample(
            'Вопрос о характеристиках',
            value={"question": "Какие есть микроконтроллеры ARM с частотой выше 100 МГц?"},
            request_only=True,
        ),
        OpenApiExample(
            'Вопрос о наличии',
            value={"question": "Есть ли в наличии резисторы номиналом 4.7 кОм?"},
            request_only=True,
        ),
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rag_search_with_answer(request: Request) -> Response:
    """
    RAG поиск товаров с генерацией ответа на естественном языке
    """
    try:
        question = request.data.get('question', '').strip()
        if not question:
            return Response(
                {"error": "Поле 'question' обязательно"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Парсим дополнительные параметры
        search_limit = min(int(request.data.get('search_limit', 5)), 20)
        semantic_ratio = float(request.data.get('semantic_ratio', 0.7))
        
        # Валидация параметров
        if not (0.0 <= semantic_ratio <= 1.0):
            return Response(
                {"error": "semantic_ratio должен быть от 0.0 до 1.0"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Выполняем RAG поиск
        rag_chain = get_rag_chain()
        result = rag_chain.search_and_answer(
            question=question,
            search_limit=search_limit,
            semantic_ratio=semantic_ratio
        )
        
        return Response({
            "question": question,
            "answer": result["answer"],
            "products": result["products"],
            "context_used": result["context_used"],
            "search_params": {
                "search_limit": search_limit,
                "semantic_ratio": semantic_ratio
            }
        })
        
    except ValueError as e:
        return Response(
            {"error": f"Неверный формат параметра: {str(e)}"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Ошибка RAG поиска: {e}")
        return Response(
            {"error": f"Ошибка RAG поиска: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    responses={
        200: {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "meilisearch_connected": {"type": "boolean"},
                "embedder_ready": {"type": "boolean"},
                "index_exists": {"type": "boolean"},
                "total_products": {"type": "integer"}
            }
        }
    },
    summary="Проверка статуса RAG системы",
    description="Проверяет готовность RAG системы и состояние индекса товаров"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rag_system_status(request: Request) -> Response:
    """
    Проверяет статус RAG системы
    """
    try:
        rag_service = get_rag_service()
        
        # Проверяем подключение к Meilisearch
        meilisearch_connected = False
        index_exists = False
        total_products = 0
        
        try:
            # Проверяем подключение
            health = rag_service.client.health()
            meilisearch_connected = health.get('status') == 'available'
            
            # Проверяем индекс
            if meilisearch_connected:
                try:
                    index = rag_service.client.index(rag_service.index_name)
                    stats = index.get_stats()
                    index_exists = True
                    total_products = stats.number_of_documents
                except:
                    index_exists = False
        except:
            meilisearch_connected = False
        
        # Проверяем готовность эмбедера
        embedder_ready = False
        try:
            # Пробуем создать простой эмбединг
            test_embedding = rag_service.embedder.embed_text("тест")
            embedder_ready = len(test_embedding) > 0
        except:
            embedder_ready = False
        
        return Response({
            "status": "ready" if all([meilisearch_connected, embedder_ready, index_exists]) else "not_ready",
            "meilisearch_connected": meilisearch_connected,
            "embedder_ready": embedder_ready,
            "index_exists": index_exists,
            "total_products": total_products,
            "index_name": rag_service.index_name
        })
        
    except Exception as e:
        logger.error(f"Ошибка проверки статуса: {e}")
        return Response(
            {"error": f"Ошибка проверки статуса: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
