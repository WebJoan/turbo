'use client';

import { useEffect, useState } from 'react';
import { onRfqUpdated } from '@/features/rfqs/events';
import { RFQTable } from '@/features/rfqs/components/rfq-tables';
import { columns as baseColumns } from '@/features/rfqs/components/rfq-tables/columns';
import { fetchRFQsFromBackend } from '@/lib/rfqs';
import { RFQ } from '@/types/rfqs';
import { parseAsInteger, parseAsString, useQueryState } from 'nuqs';
import { DataTableSkeleton } from '@/components/ui/table/data-table-skeleton';
import { toast } from 'sonner';
import { useAuth } from '@/lib/use-auth';

export function RFQPageContent() {
    const { user, loading: authLoading } = useAuth();
    const [data, setData] = useState<RFQ[]>([]);
    const [totalItems, setTotalItems] = useState(0);
    const [loading, setLoading] = useState(true);

    // Query parameters
    const [page] = useQueryState('page', parseAsInteger.withDefault(1));
    const [perPage] = useQueryState('perPage', parseAsInteger.withDefault(10));
    const [search] = useQueryState('search', parseAsString);
    const [number] = useQueryState('number', parseAsString);
    const [company_name] = useQueryState('company_name', parseAsString);
    const [status] = useQueryState('status', parseAsString);
    const [priority] = useQueryState('priority', parseAsString);

    useEffect(() => {
        const loadRFQs = async () => {
            try {
                setLoading(true);
                const result = await fetchRFQsFromBackend({
                    page,
                    perPage,
                    search: search || undefined,
                    number: number || undefined,
                    company_name: company_name || undefined,
                    status: status || undefined,
                    priority: priority || undefined
                });
                setData(result.items);
                setTotalItems(result.total);
            } catch (error) {
                console.error('Failed to fetch RFQs:', error);
                toast.error('Не удалось загрузить запросы цен');
            } finally {
                setLoading(false);
            }
        };

        loadRFQs();
        const off = onRfqUpdated((updated) => {
            setData((prev) => {
                const idx = prev.findIndex((x) => x.id === updated.id);
                if (idx === -1) return prev;
                const next = prev.slice();
                next[idx] = { ...prev[idx], ...updated } as RFQ;
                return next;
            });
        });
        return () => {
            off();
        };
    }, [page, perPage, search, number, company_name, status, priority]);

    if (loading) {
        return (
            <DataTableSkeleton
                columnCount={baseColumns.length}
                rowCount={perPage}
                withPagination={true}
            />
        );
    }

    const columns = (() => {
        // У sales менеджеров колонка Менеджер не нужна
        if (user?.role === 'sales') {
            return baseColumns.filter((c) => c.id !== 'sales_manager');
        }
        return baseColumns;
    })();

    return (
        <RFQTable
            data={data}
            totalItems={totalItems}
            columns={columns}
        />
    );
}
