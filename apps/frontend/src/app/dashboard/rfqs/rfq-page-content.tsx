'use client';

import { useEffect, useState } from 'react';
import { RFQTable } from '@/features/rfqs/components/rfq-tables';
import { columns } from '@/features/rfqs/components/rfq-tables/columns';
import { fetchRFQsFromBackend } from '@/lib/rfqs';
import { RFQ } from '@/types/rfqs';
import { parseAsInteger, parseAsString, useQueryState } from 'nuqs';
import { DataTableSkeleton } from '@/components/ui/table/data-table-skeleton';
import { toast } from 'sonner';

export function RFQPageContent() {
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
    }, [page, perPage, search, number, company_name, status, priority]);

    if (loading) {
        return (
            <DataTableSkeleton
                columnCount={columns.length}
                rowCount={perPage}
                withPagination={true}
            />
        );
    }

    return (
        <RFQTable
            data={data}
            totalItems={totalItems}
            columns={columns}
        />
    );
}
