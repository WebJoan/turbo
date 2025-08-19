"""
Django management команда для тестирования RAG системы
"""
from django.core.management.base import BaseCommand, CommandError

from goods.rag_utils import get_rag_service, get_rag_chain


class Command(BaseCommand):
    help = 'Тестирование RAG системы поиска товаров'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'query',
            type=str,
            help='Поисковый запрос для тестирования',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Количество результатов поиска (по умолчанию: 5)',
        )
        parser.add_argument(
            '--semantic-ratio',
            type=float,
            default=0.7,
            help='Соотношение семантического поиска 0.0-1.0 (по умолчанию: 0.7)',
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.3,
            help='Минимальный порог релевантности 0.0-1.0 (по умолчанию: 0.3)',
        )
        parser.add_argument(
            '--with-llm',
            action='store_true',
            help='Тестировать с использованием LLM для ответов (требует настройки LLM)',
        )
        parser.add_argument(
            '--benchmark',
            action='store_true',
            help='Провести бенчмарк производительности',
        )
    
    def handle(self, *args, **options):
        query = options['query']
        
        self.stdout.write(
            self.style.SUCCESS(f'🔍 Тестируем RAG поиск с запросом: "{query}"')
        )
        
        try:
            rag_service = get_rag_service()
            
            # Проверяем статус системы
            self._check_system_status(rag_service)
            
            # Основной тест поиска
            self._test_hybrid_search(rag_service, options)
            
            # Тест с LLM (если указано)
            if options['with_llm']:
                self._test_with_llm(query, options)
            
            # Бенчмарк (если указан)
            if options['benchmark']:
                self._run_benchmark(rag_service, query, options)
                
        except Exception as e:
            raise CommandError(f'Ошибка тестирования: {str(e)}')
    
    def _check_system_status(self, rag_service):
        """Проверяет статус системы"""
        self.stdout.write('📊 Проверяем статус RAG системы...')
        
        # Проверка Meilisearch
        try:
            health = rag_service.client.health()
            if health.get('status') == 'available':
                self.stdout.write(
                    self.style.SUCCESS('✅ Meilisearch доступен')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Meilisearch недоступен')
                )
                return False
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка подключения к Meilisearch: {e}')
            )
            return False
        
        # Проверка индекса
        try:
            index = rag_service.client.index(rag_service.index_name)
            stats = index.get_stats()
            doc_count = stats.number_of_documents
            
            if doc_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Индекс товаров содержит {doc_count} документов')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️ Индекс товаров пуст')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка проверки индекса: {e}')
            )
            return False
        
        # Проверка эмбедера
        try:
            test_embedding = rag_service.embedder.embed_text("тест")
            if len(test_embedding) > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ HuggingFace эмбедер готов (размерность: {len(test_embedding)})')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️ Проблема с эмбедером')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка эмбедера: {e}')
            )
            return False
        
        return True
    
    def _test_hybrid_search(self, rag_service, options):
        """Тестирует гибридный поиск"""
        query = options['query']
        limit = options['limit']
        semantic_ratio = options['semantic_ratio']
        threshold = options['threshold']
        
        self.stdout.write('\n🔍 Тестируем гибридный поиск...')
        self.stdout.write(f'Параметры: limit={limit}, semantic_ratio={semantic_ratio}, threshold={threshold}')
        
        try:
            import time
            start_time = time.time()
            
            results = rag_service.hybrid_search(
                query=query,
                limit=limit,
                semantic_ratio=semantic_ratio,
                ranking_score_threshold=threshold
            )
            
            search_time = time.time() - start_time
            
            if results:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Найдено {len(results)} товаров за {search_time:.3f} сек')
                )
                
                self.stdout.write('\n📋 Результаты поиска:')
                for i, result in enumerate(results, 1):
                    self.stdout.write(
                        f'  {i}. [{result.ext_id}] {result.name}'
                    )
                    self.stdout.write(
                        f'     Бренд: {result.brand_name} | Группа: {result.group_name} > {result.subgroup_name}'
                    )
                    self.stdout.write(
                        f'     Релевантность: {result.relevance_score:.3f} | Менеджер: {result.product_manager_name}'
                    )
                    
                    if result.tech_params:
                        tech_preview = str(result.tech_params)[:100] + '...' if len(str(result.tech_params)) > 100 else str(result.tech_params)
                        self.stdout.write(f'     Технические параметры: {tech_preview}')
                    
                    if result.description:
                        desc_preview = result.description[:100] + '...' if len(result.description) > 100 else result.description
                        self.stdout.write(f'     Описание: {desc_preview}')
                    
                    self.stdout.write('')  # Пустая строка для разделения
                
                # Тест создания контекста
                context = rag_service.get_context_for_llm(results)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Контекст для LLM создан ({len(context)} символов)')
                )
                
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️ Товары не найдены')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка поиска: {e}')
            )
    
    def _test_with_llm(self, query, options):
        """Тестирует RAG с LLM"""
        self.stdout.write('\n🤖 Тестируем RAG с LLM...')
        
        try:
            rag_chain = get_rag_chain()
            
            import time
            start_time = time.time()
            
            result = rag_chain.search_and_answer(
                question=query,
                search_limit=options['limit'],
                semantic_ratio=options['semantic_ratio']
            )
            
            llm_time = time.time() - start_time
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Ответ получен за {llm_time:.3f} сек')
            )
            
            self.stdout.write('\n💬 Ответ LLM:')
            self.stdout.write('-' * 50)
            self.stdout.write(result['answer'])
            self.stdout.write('-' * 50)
            
            self.stdout.write(f'\n📊 Использовано товаров: {len(result["products"])}')
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️ LLM недоступен или не настроен: {e}')
            )
    
    def _run_benchmark(self, rag_service, query, options):
        """Запускает бенчмарк производительности"""
        self.stdout.write('\n⚡ Запускаем бенчмарк производительности...')
        
        import time
        
        # Тестовые запросы
        test_queries = [
            query,
            'резистор 10 кОм',
            'микроконтроллер ARM',
            'конденсатор 100 мкФ',
            'светодиод красный',
        ]
        
        total_time = 0
        successful_searches = 0
        
        for i, test_query in enumerate(test_queries, 1):
            try:
                start_time = time.time()
                
                results = rag_service.hybrid_search(
                    query=test_query,
                    limit=options['limit'],
                    semantic_ratio=options['semantic_ratio'],
                    ranking_score_threshold=options['threshold']
                )
                
                search_time = time.time() - start_time
                total_time += search_time
                successful_searches += 1
                
                self.stdout.write(
                    f'  {i}. "{test_query}" -> {len(results)} результатов за {search_time:.3f} сек'
                )
                
            except Exception as e:
                self.stdout.write(
                    f'  {i}. "{test_query}" -> Ошибка: {e}'
                )
        
        if successful_searches > 0:
            avg_time = total_time / successful_searches
            self.stdout.write(
                self.style.SUCCESS(f'\n📈 Среднее время поиска: {avg_time:.3f} сек')
            )
            self.stdout.write(
                self.style.SUCCESS(f'📈 Успешных поисков: {successful_searches}/{len(test_queries)}')
            )
        else:
            self.stdout.write(
                self.style.ERROR('❌ Все поиски завершились ошибкой')
            )
