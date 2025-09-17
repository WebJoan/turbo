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
      <DataTableColumnHeader column={column} title='Наименование' />
    ),
    cell: ({ cell }) => <div className="max-w-[200px] truncate">{cell.getValue<ProductListItem['name']>()}</div>,
    meta: {
      label: 'Наименование',
      placeholder: 'Искать товары...',
      variant: 'text',
      icon: Text
    },
    enableColumnFilter: true,
    size: 200
  },
  {
    id: 'ext_id',
    accessorKey: 'ext_id',
    header: 'Код товара',
    meta: { label: 'Код товара' },
    size: 120
  },
  {
    id: 'brand_name',
    accessorKey: 'brand_name',
    header: 'Бренд',
    meta: { label: 'Бренд' },
    size: 100
  },
  {
    id: 'group_name',
    accessorKey: 'group_name',
    header: 'Группа',
    meta: { label: 'Группа' },
    size: 120
  },
  {
    id: 'subgroup_name',
    accessorKey: 'subgroup_name',
    header: 'Подгруппа',
    meta: { label: 'Подгруппа' },
    size: 120
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
    cell: ({ getValue }) => <div className="max-w-[150px] truncate">{getValue<string>()}</div>,
    meta: { label: 'Ответственный менеджер' },
    size: 150
  },

  {
    id: 'actions',
    cell: ({ row }) => <CellAction data={row.original} />,
    size: 80,
    enableResizing: false
  }
];
