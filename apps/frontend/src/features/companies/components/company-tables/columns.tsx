'use client';
import { DataTableColumnHeader } from '@/components/ui/table/data-table-column-header';
import { Column, ColumnDef } from '@tanstack/react-table';
import { Text } from 'lucide-react';
import { CompanyListItem } from '@/types/companies';

export const companyColumns: ColumnDef<CompanyListItem>[] = [
    {
        id: 'name',
        accessorKey: 'name',
        header: ({ column }: { column: Column<CompanyListItem, unknown> }) => (
            <DataTableColumnHeader column={column} title='Название' />
        ),
        cell: ({ cell }) => <div>{cell.getValue<CompanyListItem['name']>()}</div>,
        meta: {
            label: 'Компания',
            placeholder: 'Искать компании...',
            variant: 'text',
            icon: Text
        },
        enableColumnFilter: true
    },
    {
        id: 'short_name',
        accessorKey: 'short_name',
        header: 'Краткое название'
    },
    {
        id: 'inn',
        accessorKey: 'inn',
        header: 'ИНН'
    },
    {
        id: 'ext_id',
        accessorKey: 'ext_id',
        header: 'Внешний ID'
    }
];


