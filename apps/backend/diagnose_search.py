#!/usr/bin/env python3
"""
Диагностический скрипт для выявления проблем с поиском товаров.
Запускать через: uv run python diagnose_search.py
"""

import os
import sys
import django
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

# Настройка Django
#os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings.development')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings.production')

django.setup()

from goods.models import Product, Brand, ProductGroup
from meilisearch import Client
from django.conf import settings
from django.db.models import Q

def diagnose_database():
    """Диагностирует содержимое базы данных."""
    
    print("🔍 ДИАГНОСТИКА БАЗЫ ДАННЫХ")
    print("=" * 50)
    
    # Общая статистика
    total_products = Product.objects.count()
    total_brands = Brand.objects.count()
    total_groups = ProductGroup.objects.count()
    
    print(f"📊 Общая статистика:")
    print(f"   • Всего товаров: {total_products}")
    print(f"   • Всего брендов: {total_brands}")
    print(f"   • Всего групп: {total_groups}")
    
    # Проверяем бренды похожие на Texas Instruments
    print(f"\n🏷️  Поиск брендов содержащих 'Texas' или 'TI':")
    ti_brands = Brand.objects.filter(
        Q(name__icontains='texas') | 
        Q(name__icontains='ti') |
        Q(name__icontains='instrument')
    ).values_list('name', flat=True)
    
    if ti_brands:
        for brand in ti_brands:
            products_count = Product.objects.filter(brand__name=brand).count()
            print(f"   • {brand}: {products_count} товаров")
    else:
        print("   ❌ Бренды похожие на Texas Instruments не найдены")
    
    # Проверяем группы похожие на "Микросхемы"
    print(f"\n🔧 Поиск групп содержащих 'микросхем' или 'chip':")
    chip_groups = ProductGroup.objects.filter(
        Q(name__icontains='микросхем') |
        Q(name__icontains='микро') |
        Q(name__icontains='chip') |
        Q(name__icontains='ic')
    ).values_list('name', flat=True)
    
    if chip_groups:
        for group in chip_groups:
            products_count = Product.objects.filter(subgroup__group__name=group).count()
            print(f"   • {group}: {products_count} товаров")
    else:
        print("   ❌ Группы похожие на 'Микросхемы' не найдены")
    
    # Топ-10 брендов по количеству товаров
    print(f"\n🏆 Топ-10 брендов по количеству товаров:")
    brand_stats = Product.objects.values('brand__name').annotate(
        count=models.Count('id')
    ).order_by('-count')[:10]
    
    for i, stat in enumerate(brand_stats, 1):
        brand_name = stat['brand__name'] or 'Без бренда'
        print(f"   {i:2d}. {brand_name}: {stat['count']} товаров")
    
    # Топ-10 групп товаров
    print(f"\n📦 Топ-10 групп товаров:")
    group_stats = Product.objects.values('subgroup__group__name').annotate(
        count=models.Count('id')
    ).order_by('-count')[:10]
    
    for i, stat in enumerate(group_stats, 1):
        group_name = stat['subgroup__group__name'] or 'Без группы'
        print(f"   {i:2d}. {group_name}: {stat['count']} товаров")
    
    return total_products > 0

def diagnose_meilisearch():
    """Диагностирует состояние Meilisearch индекса."""
    
    print(f"\n🔍 ДИАГНОСТИКА MEILISEARCH")
    print("=" * 50)
    
    try:
        client = Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_API_KEY)
        index = client.index("products")
        
        # Статистика индекса
        stats = index.get_stats()
        print(f"📊 Статистика индекса:")
        print(f"   • Документов: {stats.number_of_documents}")
        print(f"   • Размер: {stats.index_size} байт")
        print(f"   • Статус: {getattr(stats, 'status', 'unknown')}")
        
        # Настройки индекса
        settings_info = index.get_settings()
        filterable = settings_info.get('filterableAttributes', [])
        searchable = settings_info.get('searchableAttributes', [])
        
        print(f"\n🔧 Настройки индекса:")
        print(f"   • Filterable attributes: {len(filterable)} шт.")
        print(f"     {', '.join(filterable[:5])}{'...' if len(filterable) > 5 else ''}")
        print(f"   • Searchable attributes: {len(searchable)} шт.")
        print(f"     {', '.join(searchable[:5])}{'...' if len(searchable) > 5 else ''}")
        
        # Проверка фильтрации по брендам
        if stats.number_of_documents > 0:
            print(f"\n🧪 Тестирование фильтров:")
            
            # Получаем все уникальные бренды из индекса
            try:
                all_results = index.search("", {"limit": 1000})
                brands_in_index = set()
                groups_in_index = set()
                
                for hit in all_results.hits:
                    brand = hit.get('brand_name')
                    group = hit.get('group_name')
                    if brand:
                        brands_in_index.add(brand)
                    if group:
                        groups_in_index.add(group)
                
                print(f"   • Уникальных брендов в индексе: {len(brands_in_index)}")
                brands_list = sorted(brands_in_index)[:10]
                print(f"     Примеры: {', '.join(brands_list)}")
                
                print(f"   • Уникальных групп в индексе: {len(groups_in_index)}")
                groups_list = sorted(groups_in_index)[:10]
                print(f"     Примеры: {', '.join(groups_list)}")
                
                # Проверяем есть ли Texas Instruments
                ti_variants = [b for b in brands_in_index if 'texas' in b.lower() or 'ti' in b.lower()]
                if ti_variants:
                    print(f"   ✅ Найдены бренды TI: {', '.join(ti_variants)}")
                else:
                    print(f"   ❌ Бренды Texas Instruments не найдены в индексе")
                
                # Проверяем микросхемы
                chip_variants = [g for g in groups_in_index if 'микросхем' in g.lower() or 'chip' in g.lower()]
                if chip_variants:
                    print(f"   ✅ Найдены группы микросхем: {', '.join(chip_variants)}")
                else:
                    print(f"   ❌ Группы микросхем не найдены в индексе")
                    
            except Exception as e:
                print(f"   ⚠️  Не удалось получить данные из индекса: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения к Meilisearch: {e}")
        return False

def suggest_solutions():
    """Предлагает решения найденных проблем."""
    
    print(f"\n💡 РЕКОМЕНДАЦИИ")
    print("=" * 50)
    
    print("1. 🔄 Выполните переиндексацию:")
    print("   make reindex-smart")
    
    print(f"\n2. 🔍 Используйте точные названия из базы:")
    print("   Проверьте точные названия брендов и групп выше")
    
    print(f"\n3. 🧪 Протестируйте поиск:")
    print("   make test-search")
    
    print(f"\n4. 📝 Примеры правильных запросов:")
    print("   search_products_smart('STM32', brand='ST')")  
    print("   search_products_smart('резистор', category='Резисторы')")

def main():
    """Основная функция диагностики."""
    
    print("🚨 ДИАГНОСТИКА СИСТЕМЫ ПОИСКА ТОВАРОВ")
    print("=" * 60)
    
    # Проверяем базу данных
    db_ok = diagnose_database()
    
    if not db_ok:
        print("\n❌ В базе данных нет товаров!")
        return
    
    # Проверяем Meilisearch
    meilisearch_ok = diagnose_meilisearch()
    
    if not meilisearch_ok:
        print("\n❌ Meilisearch недоступен!")
        return
    
    # Предлагаем решения
    suggest_solutions()

if __name__ == "__main__":
    from django.db import models
    main()

