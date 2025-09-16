'use client';
import { DataTableColumnHeader } from '@/components/ui/table/data-table-column-header';
import { Column, ColumnDef } from '@tanstack/react-table';
import { Text } from 'lucide-react';
import { PersonListItem } from '@/types/persons';
import { PersonCellAction } from './cell-action';

export const personColumns: ColumnDef<PersonListItem>[] = [
    {
        id: 'name',
        accessorFn: (row) => `${row.last_name} ${row.first_name}${row.middle_name ? ' ' + row.middle_name : ''}`,
        header: ({ column }: { column: Column<PersonListItem, unknown> }) => (
            <DataTableColumnHeader column={column} title='ФИО' />
        ),
        cell: ({ getValue }) => <div>{getValue<string>()}</div>,
        meta: {
            label: 'ФИО',
            placeholder: 'Искать персоны...',
            variant: 'text',
            icon: Text
        },
        enableColumnFilter: true
    },
    {
        id: 'company_name',
        accessorKey: 'company_name',
        header: 'Компания'
    },
    {
        id: 'email',
        accessorKey: 'email',
        header: 'Email'
    },
    {
        id: 'phone',
        accessorKey: 'phone',
        header: 'Телефон'
    },
    {
        id: 'position',
        accessorKey: 'position',
        header: 'Должность'
    },
    {
        id: 'status',
        accessorKey: 'status',
        header: 'Статус'
    },
    {
        id: 'actions',
        header: '',
        cell: ({ row }) => <PersonCellAction data={row.original} />,
        enableSorting: false,
        enableHiding: false,
    }
];


