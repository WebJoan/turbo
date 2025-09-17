'use client';

import { DataTable } from '@/components/ui/table/data-table';
import { DataTableToolbar } from '@/components/ui/table/data-table-toolbar';
import { useDataTable } from '@/hooks/use-data-table';
import { ColumnDef } from '@tanstack/react-table';
import { parseAsInteger, useQueryState } from 'nuqs';
import { CompetitorProduct } from '@/types/stock';

interface CompetitorProductsTableProps {
    data: CompetitorProduct[];
    totalItems: number;
}

export function CompetitorProductsTable({ data, totalItems }: CompetitorProductsTableProps) {
    const [pageSize] = useQueryState('perPage', parseAsInteger.withDefault(10));
    const pageCount = Math.ceil(totalItems / pageSize);

    const { table } = useDataTable({
        data,
        columns: competitorProductsColumns,
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

const competitorProductsColumns: ColumnDef<CompetitorProduct>[] = [
    {
        id: 'competitor.name',
        accessorFn: (row) => row.competitor.name,
        header: 'Конкурент',
        meta: { label: 'Конкурент' },
        size: 120,
    },
    {
        id: 'part_number',
        accessorKey: 'part_number',
        header: 'Part Number',
        meta: {
            label: 'Part Number',
            placeholder: 'Искать по артикулу...',
            variant: 'text',
        },
        enableColumnFilter: true,
        size: 140,
    },
    {
        id: 'brand_name',
        accessorKey: 'brand_name',
        header: 'Бренд',
        meta: { label: 'Бренд' },
        size: 100,
    },
    {
        id: 'name',
        accessorKey: 'name',
        header: 'Наименование',
        meta: {
            label: 'Наименование',
            placeholder: 'Искать по названию...',
            variant: 'text',
        },
        enableColumnFilter: true,
        size: 200,
    },
    {
        id: 'mapped_product_name',
        accessorKey: 'mapped_product_name',
        header: 'Наш товар',
        cell: ({ cell }) => {
            const mappedName = cell.getValue<string>();
            return mappedName ? (
                <span className="text-green-600 font-medium">{mappedName}</span>
            ) : (
                <span className="text-gray-400">Не сопоставлен</span>
            );
        },
        size: 150,
    },
    {
        id: 'ext_id',
        accessorKey: 'ext_id',
        header: 'Внешний ID',
        meta: { label: 'Внешний ID' },
        size: 120,
    },
    {
        id: 'created_at',
        accessorKey: 'created_at',
        header: 'Создан',
        cell: ({ cell }) => {
            const date = new Date(cell.getValue<string>());
            return date.toLocaleDateString('ru-RU');
        },
        size: 100,
    },
];
