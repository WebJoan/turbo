'use client';

import React, { useState } from 'react';
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
    // comment popover replaces dialog

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
                        return (
                            <React.Fragment key={item.id}>
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
                                    <TableCell>{item.product_name || '-'}</TableCell>
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

                                {/* Expandable content */}
                                {rowState?.isExpanded && (
                                    <TableRow key={`${item.id}-expanded`}>
                                        <TableCell colSpan={11} className="p-0">
                                            <div className="bg-muted/20 p-4">
                                                <h5 className="text-sm font-semibold mb-3">
                                                    Предложения от продукт-менеджеров
                                                </h5>

                                                {rowState.isLoading && (
                                                    <div className="text-sm text-muted-foreground">
                                                        Загрузка предложений...
                                                    </div>
                                                )}

                                                {rowState.error && (
                                                    <div className="text-sm text-destructive">
                                                        {rowState.error}
                                                    </div>
                                                )}

                                                {rowState.quotations && rowState.quotations.quotations.length === 0 && (
                                                    <div className="text-sm text-muted-foreground">
                                                        Предложения отсутствуют
                                                    </div>
                                                )}

                                                {rowState.quotations && rowState.quotations.quotations.length > 0 && (
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
                                                                            {format(new Date(quotation.created_at), 'dd.MM.yyyy', { locale: ru })}
                                                                        </TableCell>
                                                                    </TableRow>
                                                                ))}
                                                            </TableBody>
                                                        </Table>
                                                    </div>
                                                )}
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                )}
                            </React.Fragment>
                        );
                    })}
                </TableBody>
            </Table>
            {/* Comment dialog removed; using popover per item now */}
        </div>
    );
}
