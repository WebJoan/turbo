"""
RAG утилиты для работы с товарами через Meilisearch и HuggingFace эмбединги
"""
import os
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from functools import lru_cache

import meilisearch
from sentence_transformers import SentenceTransformer
from langchain.schema import Document
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_core.language_models.base import BaseLanguageModel

from django.conf import settings
from goods.models import Product


@dataclass
class ProductSearchResult:
    """Результат поиска товара с релевантностью"""
    product_id: int
    name: str
    complex_name: str
    brand_name: str
    subgroup_name: str
    group_name: str
    description: str
    tech_params: Dict[str, Any]
    product_manager_name: str
    relevance_score: float
    ext_id: str


class HuggingFaceEmbedder:
    """
    Класс для работы с HuggingFace эмбедингами
    Использует модель Qwen/Qwen3-Embedding-0.6B
    """
    
    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B"):
        self.model_name = model_name
        self._model = None
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy loading модели для экономии памяти"""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model
    
    def embed_text(self, text: str) -> List[float]:
        """Создает эмбединг для текста"""
        return self.model.encode(text, convert_to_tensor=False).tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Создает эмбединги для списка текстов"""
        return self.model.encode(texts, convert_to_tensor=False).tolist()


class MeilisearchRAGService:
    """
    Сервис для работы с RAG системой через Meilisearch
    """
    
    def __init__(self):
        self.client = meilisearch.Client(
            url=settings.MEILISEARCH_HOST,
            api_key=settings.MEILISEARCH_API_KEY
        )
        self.embedder = HuggingFaceEmbedder()
        self.index_name = "products"
    
    def setup_embedder_config(self):
        """
        Настраивает Meilisearch для работы с HuggingFace эмбедингами
        """
        index = self.client.index(self.index_name)
        
        # Конфигурация эмбедера для HuggingFace модели
        # Автоопределяем размерность эмбеддинга и используем documentTemplate
        try:
            test_dim = len(self.embedder.embed_text("тест"))
        except Exception:
            test_dim = 1024  # запасной вариант

        embedder_config = {
            "qwen_embedder": {
                "source": "rest",
                "url": "http://api:8000/api/goods/rag/embed-internal/",
                "request": {
                    "method": "POST",
                    "body": "{\"text\": \"{{text}}\"}"
                },
                "headers": {
                    "Content-Type": "application/json"
                },
                "response": ["embeddings"],
                "dimensions": test_dim,
                # Встраиваем весь текст из поля rag_document_text
                "documentTemplate": "{{ rag_document_text }}"
            }
        }
        
        try:
            index.update_embedders(embedder_config)
            print(f"Эмбедер настроен для индекса {self.index_name}")
        except Exception as e:
            print(f"Ошибка настройки эмбедера: {e}")
    
    def create_product_document(self, product: Product) -> str:
        """
        Создает текстовое представление товара для эмбединга
        """
        manager = product.get_manager()
        
        # Обработка технических параметров
        tech_params_text = ""
        if product.tech_params:
            tech_params_list = []
            for key, value in product.tech_params.items():
                if value is not None:
                    tech_params_list.append(f"{key}: {value}")
            tech_params_text = ", ".join(tech_params_list)
        
        # Формирование полного описания товара
        document_parts = [
            f"Товар: {product.name}",
            f"Полное название: {product.complex_name}",
        ]
        
        if product.brand:
            document_parts.append(f"Бренд: {product.brand.name}")
        
        document_parts.extend([
            f"Группа: {product.subgroup.group.name}",
            f"Подгруппа: {product.subgroup.name}",
        ])
        
        if manager:
            document_parts.append(f"Менеджер: {manager.username}")
        
        if tech_params_text:
            document_parts.append(f"Технические параметры: {tech_params_text}")
        
        if product.description:
            document_parts.append(f"Описание: {product.description}")
        
        return ". ".join(document_parts)
    
    def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        semantic_ratio: float = 0.7,
        ranking_score_threshold: float = 0.3
    ) -> List[ProductSearchResult]:
        """
        Выполняет гибридный поиск (семантический + полнотекстовый)
        """
        index = self.client.index(self.index_name)
        
        search_params = {
            "hybrid": {
                "embedder": "qwen_embedder",
                "semanticRatio": semantic_ratio
            },
            "limit": limit,
            "rankingScoreThreshold": ranking_score_threshold,
            "attributesToRetrieve": [
                "id", "name", "complex_name", "brand_name",
                "subgroup_name", "group_name", "description",
                "tech_params", "product_manager_name", "ext_id"
            ],
        }
        
        try:
            results = index.search(query, search_params)
            
            search_results = []
            for hit in results.get("hits", []):
                search_result = ProductSearchResult(
                    product_id=hit.get("id", 0),
                    name=hit.get("name", ""),
                    complex_name=hit.get("complex_name", ""),
                    brand_name=hit.get("brand_name", ""),
                    subgroup_name=hit.get("subgroup_name", ""),
                    group_name=hit.get("group_name", ""),
                    description=hit.get("description", ""),
                    tech_params=hit.get("tech_params", {}),
                    product_manager_name=hit.get("product_manager_name", ""),
                    relevance_score=hit.get("_rankingScore", 0.0),
                    ext_id=hit.get("ext_id", "")
                )
                search_results.append(search_result)
            
            return search_results
            
        except Exception as e:
            print(f"Ошибка поиска: {e}")
            return []
    
    def get_context_for_llm(
        self,
        search_results: List[ProductSearchResult],
        max_context_length: int = 2000
    ) -> str:
        """
        Создает контекст для LLM из результатов поиска
        """
        context_parts = []
        
        for i, result in enumerate(search_results, 1):
            context_part = f"""
=== ТОВАР {i} (релевантность: {result.relevance_score:.3f}) ===
ID: {result.ext_id}
Название: {result.name}
Полное название: {result.complex_name}
Бренд: {result.brand_name}
Группа: {result.group_name} > {result.subgroup_name}
Менеджер: {result.product_manager_name}
            """.strip()
            
            if result.tech_params:
                tech_params_str = ", ".join([
                    f"{k}: {v}" for k, v in result.tech_params.items() 
                    if v is not None
                ])
                context_part += f"\nТехнические параметры: {tech_params_str}"
            
            if result.description:
                context_part += f"\nОписание: {result.description}"
            
            context_parts.append(context_part)
        
        full_context = "\n\n".join(context_parts)
        
        # Обрезаем контекст если он слишком длинный
        if len(full_context) > max_context_length:
            full_context = full_context[:max_context_length] + "..."
        
        return full_context


class ProductRAGChain:
    """
    RAG цепочка для ответов на вопросы о товарах
    """
    
    def __init__(self, llm: Optional[BaseLanguageModel] = None):
        self.rag_service = MeilisearchRAGService()
        self.llm = llm
        
        # Промпт для ответов о товарах
        self.prompt_template = PromptTemplate(
            template="""Ты - помощник по поиску товаров в каталоге компании. 
Используй следующий контекст из каталога товаров для ответа на вопрос пользователя.

КОНТЕКСТ ИЗ КАТАЛОГА:
{context}

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

ИНСТРУКЦИИ:
- Отвечай только на основе предоставленного контекста
- Если в контексте нет информации для ответа, скажи "Информации по данному запросу не найдено в каталоге"
- Предоставляй конкретную информацию о товарах: ID, название, бренд, параметры
- Если найдено несколько товаров, перечисли их все с основными характеристиками
- Упоминай менеджера, ответственного за товар, если это релевантно
- Будь кратким и информативным

ОТВЕТ:""",
            input_variables=["context", "question"]
        )
    
    def search_and_answer(
        self,
        question: str,
        search_limit: int = 5,
        semantic_ratio: float = 0.7
    ) -> Dict[str, Any]:
        """
        Выполняет поиск товаров и генерирует ответ с помощью LLM
        """
        # Поиск релевантных товаров
        search_results = self.rag_service.hybrid_search(
            query=question,
            limit=search_limit,
            semantic_ratio=semantic_ratio
        )
        
        if not search_results:
            return {
                "answer": "Товары по вашему запросу не найдены в каталоге.",
                "products": [],
                "context_used": ""
            }
        
        # Создание контекста для LLM
        context = self.rag_service.get_context_for_llm(search_results)
        
        # Генерация ответа с помощью LLM (если доступен)
        if self.llm:
            try:
                chain = LLMChain(llm=self.llm, prompt=self.prompt_template)
                answer = chain.run(context=context, question=question)
            except Exception as e:
                answer = f"Ошибка генерации ответа: {e}\n\nНайденные товары:\n{context}"
        else:
            # Простой ответ без LLM
            answer = f"Найденные товары по запросу '{question}':\n\n{context}"
        
        return {
            "answer": answer,
            "products": [
                {
                    "id": r.product_id,
                    "ext_id": r.ext_id,
                    "name": r.name,
                    "complex_name": r.complex_name,
                    "brand": r.brand_name,
                    "group": f"{r.group_name} > {r.subgroup_name}",
                    "manager": r.product_manager_name,
                    "relevance": r.relevance_score,
                    "tech_params": r.tech_params
                } for r in search_results
            ],
            "context_used": context
        }


@lru_cache(maxsize=1)
def get_rag_service() -> MeilisearchRAGService:
    """Синглтон для RAG сервиса"""
    return MeilisearchRAGService()


@lru_cache(maxsize=1) 
def get_rag_chain(llm: Optional[BaseLanguageModel] = None) -> ProductRAGChain:
    """Синглтон для RAG цепочки"""
    return ProductRAGChain(llm=llm)
