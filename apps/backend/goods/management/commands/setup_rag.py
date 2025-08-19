"""
Django management команда для настройки RAG системы
"""
import time
from typing import Dict, Any

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from goods.models import Product
from goods.rag_utils import MeilisearchRAGService, get_rag_service
from goods.indexers import ProductIndexer


class Command(BaseCommand):
    help = 'Настройка и инициализация RAG системы для поиска товаров'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--setup-embedder',
            action='store_true',
            help='Настроить конфигурацию эмбедера в Meilisearch',
        )
        parser.add_argument(
            '--reindex',
            action='store_true',
            help='Переиндексировать все товары с поддержкой RAG',
        )
        parser.add_argument(
            '--test-search',
            action='store_true',
            help='Протестировать поиск после настройки',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Размер батча для переиндексации (по умолчанию: 100)',
        )
        parser.add_argument(
            '--test-query',
            type=str,
            default='резистор',
            help='Тестовый запрос для поиска (по умолчанию: "резистор")',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Начинаем настройку RAG системы для поиска товаров')
        )
        
        try:
            # Получаем сервис RAG
            rag_service = get_rag_service()
            
            # Проверяем подключение к Meilisearch
            self._check_meilisearch_connection(rag_service)
            
            # Настройка эмбедера
            if options['setup_embedder']:
                self._setup_embedder(rag_service)
            
            # Переиндексация товаров
            if options['reindex']:
                self._reindex_products(options['batch_size'])
            
            # Тестирование поиска
            if options['test_search']:
                self._test_search(rag_service, options['test_query'])
            
            self.stdout.write(
                self.style.SUCCESS('✅ RAG система успешно настроена!')
            )
            
        except Exception as e:
            raise CommandError(f'Ошибка настройки RAG системы: {str(e)}')
    
    def _check_meilisearch_connection(self, rag_service: MeilisearchRAGService):
        """Проверяет подключение к Meilisearch"""
        self.stdout.write('📡 Проверяем подключение к Meilisearch...')
        
        try:
            health = rag_service.client.health()
            if health.get('status') == 'available':
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Meilisearch доступен: {settings.MEILISEARCH_HOST}')
                )
            else:
                raise CommandError(f'❌ Meilisearch недоступен: {health}')
        except Exception as e:
            raise CommandError(f'❌ Ошибка подключения к Meilisearch: {str(e)}')
    
    def _setup_embedder(self, rag_service: MeilisearchRAGService):
        """Настраивает конфигурацию эмбедера"""
        self.stdout.write('⚙️ Настраиваем конфигурацию эмбедера...')
        
        try:
            # Проверяем готовность HuggingFace модели
            self.stdout.write('📥 Загружаем HuggingFace модель...')
            test_embedding = rag_service.embedder.embed_text("тест")
            self.stdout.write(
                self.style.SUCCESS(f'✅ Модель загружена, размерность: {len(test_embedding)}')
            )
            
            # Настраиваем эмбедер в Meilisearch
            rag_service.setup_embedder_config()
            self.stdout.write(
                self.style.SUCCESS('✅ Конфигурация эмбедера настроена')
            )
            
        except Exception as e:
            raise CommandError(f'❌ Ошибка настройки эмбедера: {str(e)}')
    
    def _reindex_products(self, batch_size: int):
        """Переиндексирует все товары"""
        self.stdout.write(f'🔄 Переиндексируем товары (батчами по {batch_size})...')
        
        try:
            # Получаем общее количество товаров
            total_products = Product.objects.count()
            self.stdout.write(f'📊 Всего товаров для индексации: {total_products}')
            
            if total_products == 0:
                self.stdout.write(
                    self.style.WARNING('⚠️ Товары не найдены в базе данных')
                )
                return
            
            # Переиндексируем все товары атомарно
            self.stdout.write('🔄 Выполняем атомарную переиндексацию товаров...')
            try:
                ProductIndexer.index_all_atomically()
                processed = total_products
                self.stdout.write('✅ Атомарная переиндексация выполнена успешно')
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Ошибка атомарной переиндексации: {str(e)}')
                )
                self.stdout.write('🔄 Пытаемся выполнить построчную переиндексацию...')
                
                # Fallback: переиндексируем батчами через query
                processed = 0
                for start in range(0, total_products, batch_size):
                    try:
                        end = min(start + batch_size, total_products)
                        product_ids = list(Product.objects.all()[start:end].values_list('id', flat=True))
                        
                        # Индексируем батч через Query
                        from django.db.models import Q
                        ProductIndexer.index_from_query(Q(pk__in=product_ids))
                        
                        processed += len(product_ids)
                        if processed % (batch_size * 5) == 0:
                            self.stdout.write(f'📈 Обработано: {processed}/{total_products}')
                        
                    except Exception as batch_e:
                        self.stdout.write(
                            self.style.WARNING(f'⚠️ Ошибка батча {start}-{end}: {str(batch_e)}')
                        )
                    
                    # Небольшая пауза между батчами
                    time.sleep(0.5)
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Переиндексация завершена: {processed}/{total_products}')
            )
            
        except Exception as e:
            raise CommandError(f'❌ Ошибка переиндексации: {str(e)}')
    
    def _test_search(self, rag_service: MeilisearchRAGService, query: str):
        """Тестирует поиск товаров"""
        self.stdout.write(f'🔍 Тестируем поиск с запросом: "{query}"')
        
        try:
            # Обычный поиск
            results = rag_service.hybrid_search(
                query=query,
                limit=5,
                semantic_ratio=0.7
            )
            
            if results:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Найдено товаров: {len(results)}')
                )
                
                for i, result in enumerate(results, 1):
                    self.stdout.write(
                        f'  {i}. {result.name} ({result.brand_name}) - '
                        f'релевантность: {result.relevance_score:.3f}'
                    )
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️ Товары не найдены')
                )
            
            # Тест создания контекста для LLM
            if results:
                context = rag_service.get_context_for_llm(results)
                context_length = len(context)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Создан контекст для LLM: {context_length} символов')
                )
                
                if context_length > 0:
                    # Показываем начало контекста
                    preview = context[:200] + '...' if len(context) > 200 else context
                    self.stdout.write(f'📄 Превью контекста:\n{preview}')
                    
        except Exception as e:
            raise CommandError(f'❌ Ошибка тестирования поиска: {str(e)}')
    
    def _get_system_stats(self, rag_service: MeilisearchRAGService) -> Dict[str, Any]:
        """Получает статистику системы"""
        stats = {
            'meilisearch_connected': False,
            'index_exists': False,
            'total_documents': 0,
            'embedder_ready': False
        }
        
        try:
            # Проверка Meilisearch
            health = rag_service.client.health()
            stats['meilisearch_connected'] = health.get('status') == 'available'
            
            if stats['meilisearch_connected']:
                try:
                    index = rag_service.client.index(rag_service.index_name)
                    index_stats = index.get_stats()
                    stats['index_exists'] = True
                    stats['total_documents'] = index_stats.number_of_documents
                except:
                    pass
            
            # Проверка эмбедера
            try:
                test_embedding = rag_service.embedder.embed_text("тест")
                stats['embedder_ready'] = len(test_embedding) > 0
            except:
                pass
                
        except:
            pass
        
        return stats
