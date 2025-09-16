import { type Table as TanstackTable, flexRender } from '@tanstack/react-table';
import * as React from 'react';

import { DataTablePagination } from '@/components/ui/table/data-table-pagination';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { getCommonPinningStyles } from '@/lib/data-table';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';

interface DataTableProps<TData> extends React.ComponentProps<'div'> {
  table: TanstackTable<TData>;
  actionBar?: React.ReactNode;
  renderSubComponent?: (props: { row: any }) => React.ReactElement;
  rowWrapper?: (row: any, rowElement: React.ReactElement) => React.ReactElement;
}

function AutoScrollSubRow({ row, colSpan, children }: { row: any; colSpan: number; children: React.ReactNode }) {
  const isExpanded = row.getIsExpanded();
  const containerRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!isExpanded) return;
    const el = containerRef.current;
    if (!el) return;
    const doScroll = () => {
      const viewport = el.closest('[data-slot="scroll-area-viewport"]') as HTMLElement | null;
      const tableEl = el.closest('table') as HTMLElement | null;
      const theadEl = tableEl?.querySelector('thead') as HTMLElement | null;
      const stickyHeaderHeight = theadEl?.getBoundingClientRect().height ?? 0;

      const applyScroll = (scroller: HTMLElement, scrollerRect: DOMRect) => {
        const visibleTop = scrollerRect.top + stickyHeaderHeight;
        const visibleBottom = scrollerRect.bottom;
        const elRect = el.getBoundingClientRect();
        const viewportSpace = visibleBottom - visibleTop;

        let targetTopDelta: number | null = null;
        if (elRect.height <= viewportSpace) {
          // Помещаем весь блок в видимую область сразу под шапкой
          targetTopDelta = elRect.top - visibleTop - 8;
        } else if (elRect.bottom > visibleBottom) {
          // Доскроллим, чтобы низ блока стал видимым
          targetTopDelta = elRect.bottom - visibleBottom + 8;
        } else if (elRect.top < visibleTop) {
          // Подвинем вверх, если верх блока выше зоны видимости
          targetTopDelta = elRect.top - visibleTop - 8;
        }

        if (targetTopDelta !== null && Math.abs(targetTopDelta) > 1) {
          scroller.scrollTo({ top: scroller.scrollTop + targetTopDelta, behavior: 'smooth' });
        }
      };

      if (viewport) {
        applyScroll(viewport, viewport.getBoundingClientRect());
      } else {
        // Фолбэк: прокрутка окна
        const winRect = new DOMRect(0, 0, window.innerWidth, window.innerHeight);
        const startTop = window.scrollY;
        const before = { top: window.scrollY };
        const visibleTop = winRect.top + stickyHeaderHeight; // обычно 0
        const elRect = el.getBoundingClientRect();
        let delta = 0;
        if (elRect.top < visibleTop) delta = elRect.top - visibleTop - 8;
        else if (elRect.bottom > winRect.bottom) delta = elRect.bottom - winRect.bottom + 8;
        const target = startTop + delta;
        if (Math.abs(delta) > 1) window.scrollTo({ top: target, behavior: 'smooth' });
      }
    };
    const rAF = requestAnimationFrame(doScroll);
    const t = setTimeout(doScroll, 360);
    return () => { cancelAnimationFrame(rAF); clearTimeout(t); };
  }, [isExpanded]);

  return (
    <TableRow>
      <TableCell colSpan={colSpan} className='p-0'>
        <div
          ref={containerRef}
          className='overflow-hidden'
          style={{
            maxHeight: isExpanded ? 9999 : 0,
            opacity: isExpanded ? 1 : 0,
            transition: 'max-height 300ms ease-in-out, opacity 300ms ease-in-out'
          }}
          aria-hidden={!isExpanded}
        >
          {children}
        </div>
      </TableCell>
    </TableRow>
  );
}

export function DataTable<TData>({
  table,
  actionBar,
  renderSubComponent,
  rowWrapper,
  children
}: DataTableProps<TData>) {
  return (
    <div className='flex flex-1 flex-col space-y-4'>
      {children}
      <div className='relative flex flex-1'>
        <div className='absolute inset-0 flex overflow-hidden rounded-lg border'>
          <ScrollArea className='h-full w-full'>
            <Table>
              <TableHeader className='bg-muted sticky top-0 z-10'>
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <TableHead
                        key={header.id}
                        colSpan={header.colSpan}
                        style={{
                          ...getCommonPinningStyles({ column: header.column })
                        }}
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows?.length ? (
                  table.getRowModel().rows.map((row) => {
                    const rowElement = (
                      <TableRow data-state={row.getIsSelected() && 'selected'}>
                        {row.getVisibleCells().map((cell) => (
                          <TableCell
                            key={cell.id}
                            style={{
                              ...getCommonPinningStyles({ column: cell.column })
                            }}
                          >
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext()
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                    );

                    return (
                      <React.Fragment key={row.id}>
                        {rowWrapper ? rowWrapper(row, rowElement) : rowElement}
                        {renderSubComponent && (
                          <AutoScrollSubRow row={row} colSpan={row.getVisibleCells().length}>
                            {renderSubComponent({ row })}
                          </AutoScrollSubRow>
                        )}
                      </React.Fragment>
                    );
                  })
                ) : (
                  <TableRow>
                    <TableCell
                      colSpan={table.getAllColumns().length}
                      className='h-24 text-center'
                    >
                      No results.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
            <ScrollBar orientation='horizontal' />
            <ScrollBar orientation='vertical' />
          </ScrollArea>
        </div>
      </div>
      <div className='flex flex-col gap-2.5'>
        <DataTablePagination table={table} />
        {actionBar &&
          table.getFilteredSelectedRowModel().rows.length > 0 &&
          actionBar}
      </div>
    </div>
  );
}
