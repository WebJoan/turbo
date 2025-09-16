'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, MessageSquareText, FileText, Paperclip } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
// removed dialog imports; comments use popover now
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from '@/components/ui/table';
import { RFQItem, RFQItemQuotationsResponse } from '@/types/rfqs';
import { fetchRFQItemQuotations } from '@/lib/rfqs';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { useAuth } from '@/lib/use-auth';
import { ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuTrigger } from '@/components/ui/context-menu';
import { useRouter } from 'next/navigation';
import { QuotationCreateDialog } from '../quotation-create-dialog';
// removed upload dialog; files теперь грузятся через форму создания предложения

interface ItemsTableProps {
    items: RFQItem[];
}

// Маппинг статусов предложений
const quotationStatusMap = {
    draft: { label: 'Черновик', variant: 'secondary' as const },
    submitted: { label: 'Отправлено', variant: 'default' as const },
    accepted: { label: 'Принято', variant: 'success' as const },
    rejected: { label: 'Отклонено', variant: 'destructive' as const },
    expired: { label: 'Просрочено', variant: 'outline' as const }
};

interface ExpandableRowState {
    [key: number]: {
        isExpanded: boolean;
        quotations: RFQItemQuotationsResponse | null;
        isLoading: boolean;
        error: string | null;
    };
}

export function ItemsTable({ items }: ItemsTableProps) {
    const [expandedRows, setExpandedRows] = useState<ExpandableRowState>({});
    const rowRefs = useRef<Record<number, HTMLDivElement | null>>({});
    const [presenceMap, setPresenceMap] = useState<Record<number, boolean>>({});
    // comment popover replaces dialog
    const { user, loading } = useAuth();
    const isPurchaser = user?.role === 'purchaser';
    const router = useRouter();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [dialogItemId, setDialogItemId] = useState<number | null>(null);
    // upload dialog удалён; используем загрузку файлов внутри формы создания предложения

    const scrollExpandedIntoView = useCallback((rfqItemId: number) => {
        const el = rowRefs.current[rfqItemId];
        if (!el) return;
        const viewport = el.closest('[data-slot="scroll-area-viewport"]') as HTMLElement | null;
        const tableEl = el.closest('table') as HTMLElement | null;
        const theadEl = tableEl?.querySelector('thead') as HTMLElement | null;
        const stickyHeaderHeight = theadEl?.getBoundingClientRect().height ?? 0;

        const applyScroll = (scroller: HTMLElement, scrollerRect: DOMRect) => {
            const visibleTop = scrollerRect.top + stickyHeaderHeight;
            const visibleBottom = scrollerRect.bottom;
            const elRect = el.getBoundingClientRect();
            const viewportSpace = visibleBottom - visibleTop;

            let targetTopDelta: number | null = null;
            if (elRect.height <= viewportSpace) {
                targetTopDelta = elRect.top - visibleTop - 8;
            } else if (elRect.bottom > visibleBottom) {
                targetTopDelta = elRect.bottom - visibleBottom + 8;
            } else if (elRect.top < visibleTop) {
                targetTopDelta = elRect.top - visibleTop - 8;
            }

            if (targetTopDelta !== null && Math.abs(targetTopDelta) > 1) {
                scroller.scrollTo({ top: scroller.scrollTop + targetTopDelta, behavior: 'smooth' });
            }
        };

        if (viewport) {
            applyScroll(viewport, viewport.getBoundingClientRect());
        } else {
            const winRect = new DOMRect(0, 0, window.innerWidth, window.innerHeight);
            const startTop = window.scrollY;
            const visibleTop = winRect.top + stickyHeaderHeight;
            const elRect = el.getBoundingClientRect();
            let delta = 0;
            if (elRect.top < visibleTop) delta = elRect.top - visibleTop - 8;
            else if (elRect.bottom > winRect.bottom) delta = elRect.bottom - winRect.bottom + 8;
            const target = startTop + delta;
            if (Math.abs(delta) > 1) window.scrollTo({ top: target, behavior: 'smooth' });
        }
    }, []);

    const handleToggle = async (rfqItemId: number) => {
        const current = expandedRows[rfqItemId];
        const newExpanded = !current?.isExpanded;

        setExpandedRows(prev => ({
            ...prev,
            [rfqItemId]: {
                ...prev[rfqItemId],
                isExpanded: newExpanded
            }
        }));

        // Автопрокрутка к раскрытому блоку
        if (newExpanded) {
            // 1) сразу после layout
            requestAnimationFrame(() => scrollExpandedIntoView(rfqItemId));
            // 2) после завершения CSS-анимации раскрытия (≈300ms)
            setTimeout(() => scrollExpandedIntoView(rfqItemId), 360);
        }

        // Загружаем данные только при первом раскрытии
        if (newExpanded && !current?.quotations && !current?.isLoading) {
            setExpandedRows(prev => ({
                ...prev,
                [rfqItemId]: {
                    ...prev[rfqItemId],
                    isLoading: true,
                    error: null
                }
            }));

            try {
                const data = await fetchRFQItemQuotations(rfqItemId);
                setExpandedRows(prev => ({
                    ...prev,
                    [rfqItemId]: {
                        ...prev[rfqItemId],
                        quotations: data,
                        isLoading: false
                    }
                }));
            } catch (err) {
                console.error(`Ошибка загрузки предложений для RFQItem ${rfqItemId}:`, err);

                let errorMessage = 'Ошибка загрузки предложений';
                if (err instanceof Error) {
                    // Проверяем, если это 404 - RFQItem не найден
                    if (err.message.includes('404')) {
                        errorMessage = 'Позиция запроса не найдена';
                    } else {
                        errorMessage = err.message;
                    }
                }

                setExpandedRows(prev => ({
                    ...prev,
                    [rfqItemId]: {
                        ...prev[rfqItemId],
                        error: errorMessage,
                        isLoading: false
                    }
                }));
            }
        }
    };

    const openCreateDialog = (rfqItemId: number) => {
        setDialogItemId(rfqItemId);
        setDialogOpen(true);
    };

    // upload dialog удалён

    const refreshQuotations = async (rfqItemId: number) => {
        try {
            const data = await fetchRFQItemQuotations(rfqItemId);
            setExpandedRows(prev => ({
                ...prev,
                [rfqItemId]: {
                    ...prev[rfqItemId],
                    quotations: data,
                    isLoading: false
                }
            }));
        } catch { }
    };

    // Предварительно подгружаем наличие предложений для позиций без поля has_quotations
    useEffect(() => {
        let cancelled = false;
        const idsToCheck = items
            .filter((i) => typeof (i as any).has_quotations !== 'boolean')
            .map((i) => i.id);
        if (idsToCheck.length === 0) return;
        const run = async () => {
            try {
                const results = await Promise.all(
                    idsToCheck.map(async (id) => {
                        try {
                            const data = await fetchRFQItemQuotations(id);
                            return [id, (data?.quotations?.length || 0) > 0] as const;
                        } catch {
                            return [id, false] as const;
                        }
                    })
                );
                if (cancelled) return;
                setPresenceMap((prev) => {
                    const next = { ...prev };
                    for (const [id, has] of results) next[id] = has;
                    return next;
                });
            } catch {
                // ignore
            }
        };
        run();
        return () => {
            cancelled = true;
        };
    }, [items]);

    return (
        <div className="border rounded-lg overflow-hidden">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead className="w-[40px]"></TableHead>
                        <TableHead className="w-[60px]">№</TableHead>
                        <TableHead>Название товара</TableHead>
                        <TableHead>Производитель</TableHead>
                        <TableHead>Артикул</TableHead>
                        <TableHead className="text-right">Количество</TableHead>
                        <TableHead>Ед. изм.</TableHead>
                        <TableHead>Статус</TableHead>
                        <TableHead>Спецификация</TableHead>
                        <TableHead>Комментарии</TableHead>
                        <TableHead>Файлы</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {items.map((item) => {
                        const rowState = expandedRows[item.id];
                        const hasQuotations = (typeof (item as any).has_quotations === 'boolean')
                            ? (item as any).has_quotations
                            : (presenceMap[item.id] ?? (rowState?.quotations ? rowState.quotations.quotations.length > 0 : false));
                        return (
                            <React.Fragment key={item.id}>
                                <ContextMenu>
                                    <ContextMenuTrigger asChild>
                                        <TableRow>
                                            <TableCell>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-8 w-8 p-0"
                                                    onClick={() => handleToggle(item.id)}
                                                >
                                                    {rowState?.isExpanded ? (
                                                        <ChevronDown className="h-4 w-4" />
                                                    ) : (
                                                        <ChevronRight className="h-4 w-4" />
                                                    )}
                                                </Button>
                                            </TableCell>
                                            <TableCell className="font-medium">{item.line_number}</TableCell>
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <span
                                                                className={`inline-block h-2.5 w-2.5 rounded-full ${hasQuotations ? 'bg-green-500' : 'bg-red-500'}`}
                                                                aria-label={hasQuotations ? 'Есть предложение' : 'Нет предложения'}
                                                            />
                                                        </TooltipTrigger>
                                                        <TooltipContent>
                                                            {hasQuotations ? 'Есть предложение от менеджера закупок' : 'Нет предложения от менеджера закупок'}
                                                        </TooltipContent>
                                                    </Tooltip>
                                                    <span>{item.product_name || '-'}</span>
                                                </div>
                                            </TableCell>
                                            <TableCell>{item.manufacturer || '-'}</TableCell>
                                            <TableCell className="font-mono text-xs">
                                                {item.is_new_product ? (item.part_number || '-') : (item.product_ext_id || '-')}
                                            </TableCell>
                                            <TableCell className="text-right">{item.quantity}</TableCell>
                                            <TableCell>{item.unit}</TableCell>
                                            <TableCell>
                                                <Badge variant={item.is_new_product ? 'secondary' : 'default'}>
                                                    {item.is_new_product ? 'Новый' : 'Из базы'}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="max-w-[200px]">
                                                {item.specifications ? (
                                                    <Popover>
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <PopoverTrigger asChild>
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        className="h-8 w-8 p-0"
                                                                        aria-label="Показать спецификацию"
                                                                    >
                                                                        <FileText className="h-4 w-4" />
                                                                    </Button>
                                                                </PopoverTrigger>
                                                            </TooltipTrigger>
                                                            <TooltipContent>Спецификация</TooltipContent>
                                                        </Tooltip>
                                                        <PopoverContent className="w-96 max-h-64 overflow-auto">
                                                            <div className="whitespace-pre-wrap break-words text-sm">
                                                                {item.specifications}
                                                            </div>
                                                        </PopoverContent>
                                                    </Popover>
                                                ) : (
                                                    <span>-</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="max-w-[200px]">
                                                {item.comments ? (
                                                    <Popover>
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <PopoverTrigger asChild>
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        className="h-8 w-8 p-0"
                                                                        aria-label="Показать комментарий"
                                                                    >
                                                                        <MessageSquareText className="h-4 w-4" />
                                                                    </Button>
                                                                </PopoverTrigger>
                                                            </TooltipTrigger>
                                                            <TooltipContent>Комментарии</TooltipContent>
                                                        </Tooltip>
                                                        <PopoverContent className="w-96 max-h-64 overflow-auto">
                                                            <div className="whitespace-pre-wrap break-words text-sm">
                                                                {item.comments}
                                                            </div>
                                                        </PopoverContent>
                                                    </Popover>
                                                ) : (
                                                    <span>-</span>
                                                )}
                                            </TableCell>
                                            <TableCell className="max-w-[160px]">
                                                {item.files && item.files.length > 0 ? (
                                                    <Popover>
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <PopoverTrigger asChild>
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        className="h-8 w-8 p-0"
                                                                        aria-label="Показать файлы"
                                                                    >
                                                                        <Paperclip className="h-4 w-4" />
                                                                    </Button>
                                                                </PopoverTrigger>
                                                            </TooltipTrigger>
                                                            <TooltipContent>Файлы ({item.files.length})</TooltipContent>
                                                        </Tooltip>
                                                        <PopoverContent className="w-96">
                                                            <div className="space-y-3">
                                                                {item.files.map((f) => {
                                                                    const name = (f.file || '').split('/').pop() || 'файл';
                                                                    return (
                                                                        <div key={f.id} className="flex items-start justify-between gap-3">
                                                                            <div className="min-w-0 flex-1">
                                                                                <a
                                                                                    href={f.file}
                                                                                    target="_blank"
                                                                                    rel="noopener noreferrer"
                                                                                    className="text-sm font-medium hover:underline break-words"
                                                                                >
                                                                                    {name}
                                                                                </a>
                                                                                {f.description && (
                                                                                    <div className="text-xs text-muted-foreground mt-0.5 break-words">
                                                                                        {f.description}
                                                                                    </div>
                                                                                )}
                                                                            </div>
                                                                            <Badge variant="secondary" className="shrink-0">
                                                                                {f.file_type}
                                                                            </Badge>
                                                                        </div>
                                                                    );
                                                                })}
                                                            </div>
                                                        </PopoverContent>
                                                    </Popover>
                                                ) : (
                                                    <span>-</span>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    </ContextMenuTrigger>
                                    <ContextMenuContent>
                                        {!loading && isPurchaser && (
                                            <ContextMenuItem onClick={() => openCreateDialog(item.id)}>
                                                Дать предложение
                                            </ContextMenuItem>
                                        )}
                                    </ContextMenuContent>
                                </ContextMenu>

                                {/* Expandable content with animation */}
                                <TableRow key={`${item.id}-expanded`}>
                                    <TableCell colSpan={11} className="p-0">
                                        <div
                                            ref={(el) => { rowRefs.current[item.id] = el; }}
                                            className="overflow-hidden"
                                            style={{
                                                maxHeight: rowState?.isExpanded ? 9999 : 0,
                                                opacity: rowState?.isExpanded ? 1 : 0,
                                                transition: 'max-height 300ms ease-in-out, opacity 300ms ease-in-out'
                                            }}
                                            aria-hidden={!rowState?.isExpanded}
                                        >
                                            <div className="bg-muted/20 p-4">
                                                <h5 className="text-sm font-semibold mb-3">
                                                    Предложения от продукт-менеджеров
                                                </h5>

                                                {rowState?.isLoading && (
                                                    <div className="text-sm text-muted-foreground">
                                                        Загрузка предложений...
                                                    </div>
                                                )}

                                                {rowState?.error && (
                                                    <div className="text-sm text-destructive">
                                                        {rowState?.error}
                                                    </div>
                                                )}

                                                {rowState?.quotations && rowState.quotations.quotations.length === 0 && (
                                                    <div className="text-sm text-muted-foreground">
                                                        Предложения отсутствуют
                                                    </div>
                                                )}

                                                {rowState?.quotations && rowState.quotations.quotations.length > 0 && (
                                                    <div className="border rounded-lg overflow-hidden">
                                                        <Table>
                                                            <TableHeader>
                                                                <TableRow>
                                                                    <TableHead>Предложение</TableHead>
                                                                    <TableHead>Product менеджер</TableHead>
                                                                    <TableHead>Статус</TableHead>
                                                                    <TableHead>Товар</TableHead>
                                                                    <TableHead>Кол-во</TableHead>
                                                                    <TableHead className="text-right">Цена за ед.</TableHead>
                                                                    <TableHead className="text-right">Общая цена</TableHead>
                                                                    <TableHead>Валюта</TableHead>
                                                                    <TableHead>Срок поставки</TableHead>
                                                                    <TableHead>Файлы</TableHead>
                                                                    <TableHead>Создано</TableHead>
                                                                </TableRow>
                                                            </TableHeader>
                                                            <TableBody>
                                                                {rowState.quotations.quotations.map(({ quotation, quotation_item }) => (
                                                                    <TableRow key={`${quotation.id}-${quotation_item.id}`}>
                                                                        <TableCell className="font-medium">
                                                                            {quotation.number}
                                                                        </TableCell>
                                                                        <TableCell>
                                                                            {quotation.product_manager_username || '-'}
                                                                        </TableCell>
                                                                        <TableCell>
                                                                            <Badge variant={quotationStatusMap[quotation.status].variant}>
                                                                                {quotationStatusMap[quotation.status].label}
                                                                            </Badge>
                                                                        </TableCell>
                                                                        <TableCell>
                                                                            <div className="max-w-[200px]">
                                                                                <div className="font-medium truncate">
                                                                                    {quotation_item.product_name || quotation_item.proposed_product_name || '-'}
                                                                                </div>
                                                                                {quotation_item.proposed_manufacturer && (
                                                                                    <div className="text-xs text-muted-foreground truncate">
                                                                                        {quotation_item.proposed_manufacturer}
                                                                                    </div>
                                                                                )}
                                                                                {quotation_item.proposed_part_number && (
                                                                                    <div className="text-xs text-muted-foreground font-mono truncate">
                                                                                        {quotation_item.proposed_part_number}
                                                                                    </div>
                                                                                )}
                                                                            </div>
                                                                        </TableCell>
                                                                        <TableCell className="text-center">
                                                                            {quotation_item.quantity}
                                                                        </TableCell>
                                                                        <TableCell className="text-right font-mono">
                                                                            {parseFloat(quotation_item.unit_price).toLocaleString('ru-RU', {
                                                                                minimumFractionDigits: 2,
                                                                                maximumFractionDigits: 4
                                                                            })}
                                                                        </TableCell>
                                                                        <TableCell className="text-right font-mono font-medium">
                                                                            {parseFloat(quotation_item.total_price).toLocaleString('ru-RU', {
                                                                                minimumFractionDigits: 2,
                                                                                maximumFractionDigits: 2
                                                                            })}
                                                                        </TableCell>
                                                                        <TableCell>
                                                                            {quotation.currency_symbol} {quotation.currency_code}
                                                                        </TableCell>
                                                                        <TableCell>
                                                                            {quotation_item.delivery_time || quotation.delivery_time || '-'}
                                                                        </TableCell>
                                                                        <TableCell>
                                                                            {quotation_item.files && quotation_item.files.length > 0 ? (
                                                                                <Popover>
                                                                                    <Tooltip>
                                                                                        <TooltipTrigger asChild>
                                                                                            <PopoverTrigger asChild>
                                                                                                <Button
                                                                                                    variant="ghost"
                                                                                                    size="icon"
                                                                                                    className="h-8 w-8 p-0"
                                                                                                    aria-label="Показать файлы"
                                                                                                >
                                                                                                    <Paperclip className="h-4 w-4" />
                                                                                                </Button>
                                                                                            </PopoverTrigger>
                                                                                        </TooltipTrigger>
                                                                                        <TooltipContent>Файлы ({quotation_item.files.length})</TooltipContent>
                                                                                    </Tooltip>
                                                                                    <PopoverContent className="w-96">
                                                                                        <div className="space-y-3">
                                                                                            {quotation_item.files.map((f: any) => {
                                                                                                const name = (f.file || '').split('/').pop() || 'файл';
                                                                                                return (
                                                                                                    <div key={f.id} className="flex items-start justify-between gap-3">
                                                                                                        <div className="min-w-0 flex-1">
                                                                                                            <a
                                                                                                                href={f.file}
                                                                                                                target="_blank"
                                                                                                                rel="noopener noreferrer"
                                                                                                                className="text-sm font-medium hover:underline break-words"
                                                                                                            >
                                                                                                                {name}
                                                                                                            </a>
                                                                                                            {f.description && (
                                                                                                                <div className="text-xs text-muted-foreground mt-0.5 break-words">
                                                                                                                    {f.description}
                                                                                                                </div>
                                                                                                            )}
                                                                                                        </div>
                                                                                                        <Badge variant="secondary" className="shrink-0">
                                                                                                            {f.file_type}
                                                                                                        </Badge>
                                                                                                    </div>
                                                                                                );
                                                                                            })}
                                                                                        </div>
                                                                                    </PopoverContent>
                                                                                </Popover>
                                                                            ) : (
                                                                                <span>-</span>
                                                                            )}
                                                                        </TableCell>
                                                                        <TableCell>
                                                                            {format(new Date(quotation.created_at), 'dd.MM.yyyy', { locale: ru })}
                                                                        </TableCell>
                                                                    </TableRow>
                                                                ))}
                                                            </TableBody>
                                                        </Table>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            </React.Fragment>
                        );
                    })}
                </TableBody>
            </Table>
            {dialogItemId !== null && (
                <QuotationCreateDialog
                    open={dialogOpen}
                    onOpenChange={(o: boolean) => {
                        setDialogOpen(o);
                        if (!o) setDialogItemId(null);
                    }}
                    rfqItemId={dialogItemId}
                    onCreated={() => {
                        // раскрыть строку и перезагрузить котировки
                        setExpandedRows(prev => ({
                            ...prev,
                            [dialogItemId]: {
                                ...(prev[dialogItemId] || { isExpanded: true, isLoading: true, quotations: null, error: null }),
                                isExpanded: true,
                                isLoading: true,
                            }
                        }));
                        refreshQuotations(dialogItemId);
                    }}
                />
            )}
            {/* upload dialog удалён */}
        </div>
    );
}
