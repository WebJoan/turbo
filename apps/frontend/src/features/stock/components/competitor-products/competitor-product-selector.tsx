'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { IconCheck, IconSelector, IconLoader2 } from '@tabler/icons-react';
import { CompetitorProduct } from '@/types/stock';
import { fetchCompetitorProductsClient } from '@/lib/stock-client';

function useDebounce<T extends (...args: any[]) => void>(callback: T, delay: number) {
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    return useCallback((...args: Parameters<T>) => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(() => callback(...args), delay);
    }, [callback, delay]);
}

interface CompetitorProductSelectorProps {
    value?: number;
    onValueChange: (value: number | undefined, product?: CompetitorProduct | null) => void;
    placeholder?: string;
    disabled?: boolean;
    competitorId?: number;
}

export function CompetitorProductSelector({
    value,
    onValueChange,
    placeholder = 'Поиск товара конкурента...',
    disabled = false,
    competitorId
}: CompetitorProductSelectorProps) {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [items, setItems] = useState<CompetitorProduct[]>([]);
    const [loading, setLoading] = useState(false);

    const latestQueryRef = useRef('');

    const searchFn = useCallback(async (q: string) => {
        latestQueryRef.current = q;
        if (!q || q.length < 2) {
            setItems([]);
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const { items, total } = await fetchCompetitorProductsClient({
                page: 1,
                page_size: 20,
                part_number: q,
                competitor_id: competitorId,
            });
            if (latestQueryRef.current === q) {
                setItems(items);
            }
        } catch (e) {
            if (latestQueryRef.current === q) setItems([]);
        } finally {
            if (latestQueryRef.current === q) setLoading(false);
        }
    }, [competitorId]);

    const debouncedSearch = useDebounce(searchFn, 300);

    useEffect(() => {
        debouncedSearch(query);
    }, [query, debouncedSearch]);

    const selected = useMemo(() => items.find(i => i.id === value) || null, [items, value]);

    const handleSelect = useCallback((id: string) => {
        const num = parseInt(id);
        const product = items.find(i => i.id === num) || null;
        if (product && num !== value) {
            onValueChange(num, product);
        } else {
            onValueChange(undefined, null);
        }
        setOpen(false);
    }, [items, value, onValueChange]);

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button variant="outline" role="combobox" aria-expanded={open} className="w-full justify-between" disabled={disabled}>
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                        {selected && (
                            <Badge variant="outline" className="shrink-0">
                                {selected.brand_name || 'Без бренда'}
                            </Badge>
                        )}
                        <span className="truncate text-left">
                            {selected ? `${selected.part_number} — ${selected.name || 'Без названия'}` : placeholder}
                        </span>
                    </div>
                    <IconSelector className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-full max-w-[500px] p-0" align="start">
                <Command shouldFilter={false}>
                    <CommandInput placeholder="Введите артикул или название..." value={query} onValueChange={setQuery} />
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
                                {items.length === 0 ? (
                                    <CommandEmpty>
                                        {query.length < 2 ? 'Введите минимум 2 символа для поиска' : 'Ничего не найдено'}
                                    </CommandEmpty>
                                ) : (
                                    <CommandGroup>
                                        {items.map((it) => (
                                            <CommandItem key={it.id} value={it.id.toString()} onSelect={handleSelect} className="flex items-center justify-between">
                                                <div className="flex items-center gap-2 flex-1 min-w-0">
                                                    <IconCheck className={cn('mr-2 h-4 w-4 shrink-0', value === it.id ? 'opacity-100' : 'opacity-0')} />
                                                    <div className="flex flex-col gap-1 flex-1 min-w-0">
                                                        <div className="flex items-center gap-2">
                                                            {it.brand_name && (
                                                                <Badge variant="outline" className="text-xs">{it.brand_name}</Badge>
                                                            )}
                                                            <span className="font-medium truncate">{it.part_number}</span>
                                                        </div>
                                                        {it.name && (
                                                            <span className="text-xs text-muted-foreground truncate">{it.name}</span>
                                                        )}
                                                        <span className="text-xs text-muted-foreground truncate">{it.competitor.name}</span>
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


