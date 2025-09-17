'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { IconCheck, IconSelector, IconLoader2 } from '@tabler/icons-react';
import { cn } from '@/lib/utils';
import { searchProductsFromClient, ProductListItem } from '@/lib/client-api';

// Простая функция дебаунса
function useDebounce<T extends (...args: any[]) => void>(callback: T, delay: number) {
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    return useCallback((...args: Parameters<T>) => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }

        timeoutRef.current = setTimeout(() => {
            callback(...args);
        }, delay);
    }, [callback, delay]);
}

interface ProductSelectorProps {
    value?: number;
    onValueChange: (value: number | undefined) => void;
    onProductSelect?: (product: ProductListItem | null) => void;
    placeholder?: string;
    disabled?: boolean;
}

export function ProductSelector({
    value,
    onValueChange,
    onProductSelect,
    placeholder = "Поиск товара...",
    disabled = false
}: ProductSelectorProps) {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [products, setProducts] = useState<ProductListItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedProduct, setSelectedProduct] = useState<ProductListItem | null>(null);

    // Трекер последнего запроса, чтобы игнорировать устаревшие ответы
    const latestQueryRef = useRef('');

    // Стабильная функция поиска (не меняет идентичность между рендерами)
    const searchFn = useCallback(async (searchQuery: string) => {
        // Всегда помечаем текущий запрос как последний, чтобы игнорировать устаревшие ответы
        latestQueryRef.current = searchQuery;
        if (!searchQuery || searchQuery.length < 2) {
            setProducts([]);
            setLoading(false);
            return;
        }

        setLoading(true);
        try {
            const result = await searchProductsFromClient({
                search: searchQuery,
                limit: 20
            });
            // Игнорируем ответ, если уже начат новый поиск
            if (latestQueryRef.current === searchQuery) {
                setProducts(result.items);
            }
        } catch (error) {
            console.error('Ошибка поиска товаров:', error);
            if (latestQueryRef.current === searchQuery) {
                setProducts([]);
            }
        } finally {
            if (latestQueryRef.current === searchQuery) {
                setLoading(false);
            }
        }
    }, []);

    // Дебаунсированный поиск товаров
    const debouncedSearch = useDebounce(searchFn, 300);

    // Поиск при изменении query
    useEffect(() => {
        debouncedSearch(query);
    }, [query, debouncedSearch]);

    // Найти выбранный товар при изменении value
    useEffect(() => {
        if (value && !selectedProduct) {
            // Поиск товара по ID если он еще не загружен
            const found = products.find(p => p.id === value);
            if (found) {
                setSelectedProduct(found);
            }
        } else if (!value && selectedProduct) {
            setSelectedProduct(null);
        }
    }, [value, selectedProduct, products]);

    const handleSelect = useCallback((productId: string) => {
        const numId = parseInt(productId);
        const product = products.find(p => p.id === numId);

        if (product && numId !== value) {
            setSelectedProduct(product);
            onValueChange(numId);
            onProductSelect?.(product);
        } else {
            setSelectedProduct(null);
            onValueChange(undefined);
            onProductSelect?.(null);
        }

        setOpen(false);
    }, [value, products, onValueChange, onProductSelect]);

    const displayValue = selectedProduct
        ? `${selectedProduct.name} (${selectedProduct.brand_name || 'Без бренда'})`
        : placeholder;

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    className="w-full justify-between"
                    disabled={disabled}
                >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                        {selectedProduct && (
                            <Badge variant="outline" className="shrink-0">
                                {selectedProduct.brand_name || 'Без бренда'}
                            </Badge>
                        )}
                        <span className="truncate text-left">
                            {selectedProduct ? selectedProduct.name : placeholder}
                        </span>
                    </div>
                    <IconSelector className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-full max-w-[400px] p-0" align="start">
                <Command shouldFilter={false}>
                    <CommandInput
                        placeholder="Введите название или артикул товара..."
                        value={query}
                        onValueChange={setQuery}
                    />
                    <CommandList>
                        {loading ? (
                            <CommandEmpty>
                                <div className="flex items-center justify-center py-6">
                                    <IconLoader2 className="h-4 w-4 animate-spin mr-2" />
                                    Поиск...
                                </div>
                            </CommandEmpty>
                        ) : (
                            <>
                                {products.length === 0 ? (
                                    <CommandEmpty>
                                        {query.length < 2
                                            ? "Введите минимум 2 символа для поиска"
                                            : "Товары не найдены"
                                        }
                                    </CommandEmpty>
                                ) : (
                                    <CommandGroup>
                                        {products.map((product) => (
                                            <CommandItem
                                                key={product.id}
                                                value={product.id.toString()}
                                                onSelect={handleSelect}
                                                className="flex items-center justify-between"
                                            >
                                                <div className="flex items-center gap-2 flex-1 min-w-0">
                                                    <IconCheck
                                                        className={cn(
                                                            "mr-2 h-4 w-4 shrink-0",
                                                            value === product.id
                                                                ? "opacity-100"
                                                                : "opacity-0"
                                                        )}
                                                    />
                                                    <div className="flex flex-col gap-1 flex-1 min-w-0">
                                                        <div className="flex items-center gap-2">
                                                            {product.brand_name && (
                                                                <Badge variant="outline" className="text-xs">
                                                                    {product.brand_name}
                                                                </Badge>
                                                            )}
                                                            <span className="font-medium truncate">
                                                                {product.name}
                                                            </span>
                                                        </div>
                                                        {product.complex_name && (
                                                            <span className="text-xs text-muted-foreground truncate">
                                                                {product.complex_name}
                                                            </span>
                                                        )}
                                                        <span className="text-xs text-muted-foreground truncate">
                                                            {product.subgroup_name} • {product.group_name}
                                                        </span>
                                                    </div>
                                                </div>
                                            </CommandItem>
                                        ))}
                                    </CommandGroup>
                                )}
                            </>
                        )}
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    );
}
