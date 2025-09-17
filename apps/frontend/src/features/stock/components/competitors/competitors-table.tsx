'use client';

import { DataTable } from '@/components/ui/table/data-table';
import { DataTableToolbar } from '@/components/ui/table/data-table-toolbar';
import { useDataTable } from '@/hooks/use-data-table';
import { ColumnDef } from '@tanstack/react-table';
import { parseAsInteger, useQueryState } from 'nuqs';
import { Competitor } from '@/types/stock';

interface CompetitorsTableProps {
    data: Competitor[];
    totalItems: number;
}

export function CompetitorsTable({ data, totalItems }: CompetitorsTableProps) {
    const [pageSize] = useQueryState('perPage', parseAsInteger.withDefault(10));
    const pageCount = Math.ceil(totalItems / pageSize);

    const { table } = useDataTable({
        data,
        columns: competitorsColumns,
        pageCount,
        shallow: false,
        debounceMs: 500,
    });

    return (
        <DataTable table={table}>
            <DataTableToolbar table={table} />
        </DataTable>
    );
}

const competitorsColumns: ColumnDef<Competitor>[] = [
    {
        id: 'name',
        accessorKey: 'name',
        header: 'Название',
        meta: {
            label: 'Название',
            placeholder: 'Искать конкурентов...',
            variant: 'text',
        },
        enableColumnFilter: true,
    },
    {
        id: 'b2b_site_url',
        accessorKey: 'b2b_site_url',
        header: 'B2B Сайт',
        cell: ({ cell }) => {
            const url = cell.getValue<string>();
            return url ? (
                <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 underline"
                >
                    {url}
                </a>
            ) : (
                <span className="text-gray-400">Не указан</span>
            );
        },
    },
    {
        id: 'site_url',
        accessorKey: 'site_url',
        header: 'Основной сайт',
        cell: ({ cell }) => {
            const url = cell.getValue<string>();
            return url ? (
                <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 underline"
                >
                    {url}
                </a>
            ) : (
                <span className="text-gray-400">Не указан</span>
            );
        },
    },
    {
        id: 'is_active',
        accessorKey: 'is_active',
        header: 'Активен',
        cell: ({ cell }) => (
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cell.getValue<boolean>()
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                }`}>
                {cell.getValue<boolean>() ? 'Да' : 'Нет'}
            </span>
        ),
        meta: { label: 'Статус' },
        enableColumnFilter: false,
    },
    {
        id: 'created_at',
        accessorKey: 'created_at',
        header: 'Создан',
        cell: ({ cell }) => {
            const date = new Date(cell.getValue<string>());
            return date.toLocaleDateString('ru-RU');
        },
    },
];
