'use client';

import { DataTableColumnHeader } from '@/components/ui/table/data-table-column-header';
import { RFQ } from '@/types/rfqs';
import { Column, ColumnDef } from '@tanstack/react-table';
import { Badge } from '@/components/ui/badge';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CellAction } from './cell-action';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';

// Маппинг статусов на русский язык и цвета
const statusMap = {
    draft: { label: 'Черновик', variant: 'secondary' as const },
    submitted: { label: 'Отправлен', variant: 'default' as const },
    in_progress: { label: 'В работе', variant: 'outline' as const },
    completed: { label: 'Завершен', variant: 'success' as const },
    cancelled: { label: 'Отменен', variant: 'destructive' as const }
};

// Маппинг приоритетов на русский язык и цвета
const priorityMap = {
    low: { label: 'Низкий', variant: 'secondary' as const },
    medium: { label: 'Средний', variant: 'default' as const },
    high: { label: 'Высокий', variant: 'warning' as const },
    urgent: { label: 'Срочный', variant: 'destructive' as const }
};

export const columns: ColumnDef<RFQ>[] = [
    {
        id: 'expand',
        header: () => null,
        cell: ({ row }) => {
            return (
                <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0"
                    onClick={() => row.toggleExpanded()}
                >
                    {row.getIsExpanded() ? (
                        <ChevronDown className="h-4 w-4" />
                    ) : (
                        <ChevronRight className="h-4 w-4" />
                    )}
                </Button>
            );
        },
        enableSorting: false,
        enableHiding: false,
    },
    {
        id: 'number',
        accessorKey: 'number',
        header: ({ column }: { column: Column<RFQ, unknown> }) => (
            <DataTableColumnHeader column={column} title='Номер RFQ' />
        ),
        cell: ({ cell }) => (
            <div className="font-medium">{cell.getValue<string>()}</div>
        ),
        meta: {
            label: 'Номер',
            placeholder: 'Искать по номеру...',
            variant: 'text'
        },
        enableColumnFilter: true
    },
    {
        id: 'company_name',
        accessorKey: 'company_name',
        header: ({ column }: { column: Column<RFQ, unknown> }) => (
            <DataTableColumnHeader column={column} title='Компания' />
        ),
        cell: ({ cell }) => <div>{cell.getValue<string>()}</div>,
        meta: {
            label: 'Компания',
            placeholder: 'Искать по компании...',
            variant: 'text'
        },
        enableColumnFilter: true
    },
    {
        id: 'status',
        accessorKey: 'status',
        header: ({ column }: { column: Column<RFQ, unknown> }) => (
            <DataTableColumnHeader column={column} title='Статус' />
        ),
        cell: ({ cell }) => {
            const status = cell.getValue<RFQ['status']>();
            const config = statusMap[status];
            return (
                <Badge variant={config.variant}>
                    {config.label}
                </Badge>
            );
        },
        filterFn: (row, id, value) => {
            return value.includes(row.getValue(id));
        },
        meta: {
            label: 'Статус'
        }
    },
    {
        id: 'priority',
        accessorKey: 'priority',
        header: ({ column }: { column: Column<RFQ, unknown> }) => (
            <DataTableColumnHeader column={column} title='Приоритет' />
        ),
        cell: ({ cell }) => {
            const priority = cell.getValue<RFQ['priority']>();
            const config = priorityMap[priority];
            return (
                <Badge variant={config.variant}>
                    {config.label}
                </Badge>
            );
        },
        filterFn: (row, id, value) => {
            return value.includes(row.getValue(id));
        },
        meta: {
            label: 'Приоритет'
        }
    },
    {
        id: 'items_count',
        accessorFn: (row) => row.items?.length || 0,
        size: 80,
        header: ({ column }: { column: Column<RFQ, unknown> }) => (
            <Tooltip>
                <TooltipTrigger asChild>
                    <span className="block min-w-0 max-w-full overflow-hidden">
                        <DataTableColumnHeader column={column} title='Поз.' className="truncate w-full" />
                    </span>
                </TooltipTrigger>
                <TooltipContent>Кол-во позиций</TooltipContent>
            </Tooltip>
        ),
        cell: ({ getValue }) => (
            <div className="text-center">{getValue<number>()}</div>
        ),
        enableHiding: true,
        meta: {
            label: 'Поз.'
        }
    },
    {
        id: 'quotations_count',
        accessorKey: 'quotations_count',
        size: 100,
        header: ({ column }: { column: Column<RFQ, unknown> }) => (
            <Tooltip>
                <TooltipTrigger asChild>
                    <span className="block min-w-0 max-w-full overflow-hidden">
                        <DataTableColumnHeader column={column} title='Предл.' className="truncate w-full" />
                    </span>
                </TooltipTrigger>
                <TooltipContent>Кол-во предложений</TooltipContent>
            </Tooltip>
        ),
        cell: ({ cell }) => {
            const value = cell.getValue<number>()
            return <div className="text-center">{typeof value === 'number' ? value : 0}</div>
        },
        enableHiding: true,
        meta: {
            label: 'Предл.'
        }
    },
    {
        id: 'sales_manager',
        accessorKey: 'sales_manager_username',
        header: ({ column }: { column: Column<RFQ, unknown> }) => (
            <DataTableColumnHeader column={column} title='Менеджер' />
        ),
        cell: ({ cell }) => <div>{cell.getValue<string>() || '-'}</div>,
        meta: {
            label: 'Менеджер'
        }
    },
    {
        id: 'created_at',
        accessorKey: 'created_at',
        header: ({ column }: { column: Column<RFQ, unknown> }) => (
            <DataTableColumnHeader column={column} title='Дата создания' />
        ),
        cell: ({ cell }) => {
            const date = cell.getValue<string>();
            if (!date) return '-';
            return format(new Date(date), 'dd.MM.yyyy', { locale: ru });
        },
        meta: {
            label: 'Дата создания'
        }
    },
    {
        id: 'deadline',
        accessorKey: 'deadline',
        header: ({ column }: { column: Column<RFQ, unknown> }) => (
            <DataTableColumnHeader column={column} title='Срок' />
        ),
        cell: ({ cell }) => {
            const date = cell.getValue<string>();
            if (!date) return '-';
            return format(new Date(date), 'dd.MM.yyyy', { locale: ru });
        },
        meta: {
            label: 'Срок'
        }
    },
    {
        id: 'actions',
        cell: ({ row }) => <CellAction data={row.original} />
    }
];
