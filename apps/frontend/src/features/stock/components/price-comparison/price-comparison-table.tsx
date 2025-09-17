'use client';

import { useMemo } from 'react';
import { ColumnDef, Column } from '@tanstack/react-table';
import { parseAsInteger, useQueryState } from 'nuqs';

import { DataTable } from '@/components/ui/table/data-table';
import { DataTableToolbar } from '@/components/ui/table/data-table-toolbar';
import { DataTableColumnHeader } from '@/components/ui/table/data-table-column-header';
import { useDataTable } from '@/hooks/use-data-table';
import { Competitor } from '@/types/stock';
import { formatPrice } from '@/lib/stock-client';

export type PriceComparisonRow = {
    id: number;
    ext_id: string;
    name: string;
    brand_name: string | null;
    our_price: number | null;
    competitorMap: Record<number, { price: number | null; currency: string; stock_qty: number | null }>;
};

interface PriceComparisonTableProps {
    data: PriceComparisonRow[];
    totalItems: number;
    competitors: Competitor[];
}

export default function PriceComparisonTable({ data, totalItems, competitors }: PriceComparisonTableProps) {
    const [pageSize] = useQueryState('perPage', parseAsInteger.withDefault(10));
    const pageCount = Math.ceil(totalItems / pageSize);

    const columns = useMemo<ColumnDef<PriceComparisonRow>[]>(() => {
        const base: ColumnDef<PriceComparisonRow>[] = [
            {
                id: 'name',
                accessorKey: 'name',
                header: ({ column }: { column: Column<PriceComparisonRow, unknown> }) => (
                    <DataTableColumnHeader column={column} title='Наименование' />
                ),
                cell: ({ cell }) => <div>{cell.getValue<PriceComparisonRow['name']>()}</div>,
                meta: {
                    label: 'Наименование',
                    placeholder: 'Искать товары...',
                    variant: 'text'
                },
                enableColumnFilter: true
            },
            {
                id: 'ext_id',
                accessorKey: 'ext_id',
                header: 'Код товара',
                meta: { label: 'Код товара', placeholder: 'Код...', variant: 'text' },
                enableColumnFilter: true
            },
            {
                id: 'brand_name',
                accessorKey: 'brand_name',
                header: 'Бренд',
                meta: { label: 'Бренд', placeholder: 'Бренд...', variant: 'text' },
                enableColumnFilter: true
            },
            {
                id: 'our_price',
                accessorKey: 'our_price',
                header: 'Наша цена',
                cell: ({ cell }) => <div className='text-right'>{formatPrice(cell.getValue<number | null>())}</div>,
                meta: { label: 'Наша цена' },
                enableColumnFilter: false
            }
        ];

        const competitorCols: ColumnDef<PriceComparisonRow>[] = competitors.map((c) => {
            const colId = `comp_${c.id}`;
            const title = (c.name || '').trim().charAt(0).toUpperCase() || '?';
            return {
                id: colId,
                accessorFn: (row) => row.competitorMap[c.id]?.price ?? null,
                header: title,
                cell: ({ row }) => {
                    const entry = row.original.competitorMap[c.id];
                    if (!entry) return <span className='text-muted-foreground'>—</span>;
                    return (
                        <div className='whitespace-nowrap text-right'>
                            <span>{formatPrice(entry.price, entry.currency)}</span>
                            {typeof entry.stock_qty === 'number' && (
                                <span className='text-xs text-muted-foreground ml-1'>({entry.stock_qty})</span>
                            )}
                        </div>
                    );
                },
                meta: { label: c.name },
                enableColumnFilter: false
            } as ColumnDef<PriceComparisonRow>;
        });

        return [...base, ...competitorCols];
    }, [competitors]);

    const { table } = useDataTable<PriceComparisonRow>({
        data,
        columns,
        pageCount,
        shallow: false,
        debounceMs: 500
    });

    return (
        <DataTable table={table}>
            <DataTableToolbar table={table} />
        </DataTable>
    );
}


