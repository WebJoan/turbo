"""
URL маршруты для RAG API товаров
"""
from django.urls import path
from goods.rag_views import (
    generate_embeddings,
    generate_embeddings_internal,
    hybrid_search_products,
    rag_search_with_answer,
    rag_system_status
)

app_name = 'goods-rag'

urlpatterns = [
    # Внутренний эндпоинт для генерации эмбедингов (для Meilisearch, без авторизации)
    path('embed-internal/', generate_embeddings_internal, name='generate-embeddings-internal'),
    
    # Эндпоинт для генерации эмбедингов (с авторизацией)
    path('embed/', generate_embeddings, name='generate-embeddings'),
    
    # Гибридный поиск товаров (семантический + полнотекстовый)
    path('search/', hybrid_search_products, name='hybrid-search'),
    
    # RAG поиск с ответами на естественном языке
    path('ask/', rag_search_with_answer, name='rag-ask'),
    
    # Проверка статуса RAG системы
    path('status/', rag_system_status, name='rag-status'),
]
