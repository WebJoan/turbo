'use client';

import { DataTable } from '@/components/ui/table/data-table';
import { DataTableToolbar } from '@/components/ui/table/data-table-toolbar';
import { useDataTable } from '@/hooks/use-data-table';
import { ColumnDef, Row } from '@tanstack/react-table';
import { parseAsInteger, useQueryState } from 'nuqs';
import { RFQ } from '@/types/rfqs';
import { ExpandableRow } from './expandable-row';
import React from 'react';
import { RFQRowContextMenu } from './rfq-row-context-menu';

interface RFQTableParams<TData, TValue> {
    data: TData[];
    totalItems: number;
    columns: ColumnDef<TData, TValue>[];
}

export function RFQTable<TData, TValue>({
    data,
    totalItems,
    columns
}: RFQTableParams<TData, TValue>) {
    const [pageSize] = useQueryState('perPage', parseAsInteger.withDefault(10));

    const pageCount = Math.ceil(totalItems / pageSize);

    const { table } = useDataTable({
        data,
        columns,
        pageCount: pageCount,
        shallow: false,
        debounceMs: 500,
        // Включаем возможность раскрытия строк
        getRowCanExpand: () => true,
    });

    return (
        <DataTable
            table={table}
            rowWrapper={(row, rowElement) => (
                <RFQRowContextMenu rfq={row.original as unknown as RFQ}>
                    {rowElement}
                </RFQRowContextMenu>
            )}
            // Рендерим раскрывающийся контент для каждой строки
            renderSubComponent={({ row }: { row: Row<TData> }) => (
                <ExpandableRow rfq={row.original as unknown as RFQ} />
            )}
        >
            <DataTableToolbar table={table} />
        </DataTable>
    );
}
