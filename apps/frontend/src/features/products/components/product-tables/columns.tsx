'use client';
import { DataTableColumnHeader } from '@/components/ui/table/data-table-column-header';
import { ProductListItem } from '@/types/products';
import { Column, ColumnDef } from '@tanstack/react-table';
import { Text } from 'lucide-react';
import { CellAction } from './cell-action';

export const columns: ColumnDef<ProductListItem>[] = [
  {
    id: 'name',
    accessorKey: 'name',
    header: ({ column }: { column: Column<ProductListItem, unknown> }) => (
      <DataTableColumnHeader column={column} title='Name' />
    ),
    cell: ({ cell }) => <div>{cell.getValue<ProductListItem['name']>()}</div>,
    meta: {
      label: 'Name',
      placeholder: 'Искать товары...',
      variant: 'text',
      icon: Text
    },
    enableColumnFilter: true
  },
  {
    id: 'ext_id',
    accessorKey: 'ext_id',
    header: 'Код товара'
  },
  {
    id: 'brand_name',
    accessorKey: 'brand_name',
    header: 'Бренд'
  },
  {
    id: 'group_name',
    accessorKey: 'group_name',
    header: 'Группа'
  },
  {
    id: 'subgroup_name',
    accessorKey: 'subgroup_name',
    header: 'Подгруппа'
  },
  {
    id: 'assigned_manager',
    accessorFn: (row) => {
      const m = row.assigned_manager;
      if (!m) return '';
      const first = m.first_name?.trim();
      const last = m.last_name?.trim();
      return [first, last].filter(Boolean).join(' ');
    },
    header: ({ column }: { column: Column<ProductListItem, unknown> }) => (
      <DataTableColumnHeader column={column} title='Ответственный менеджер' />
    ),
    cell: ({ getValue }) => <div>{getValue<string>()}</div>
  },

  {
    id: 'actions',
    cell: ({ row }) => <CellAction data={row.original} />
  }
];
