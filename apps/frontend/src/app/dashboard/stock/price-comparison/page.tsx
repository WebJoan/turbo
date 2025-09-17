import { Metadata } from 'next';
import PageContainer from '@/components/layout/page-container';
import { Heading } from '@/components/ui/heading';
import { Separator } from '@/components/ui/separator';
import { DataTableSkeleton } from '@/components/ui/table/data-table-skeleton';
import { searchParamsCache } from '@/lib/searchparams';
import { SearchParams } from 'nuqs/server';
import { Suspense } from 'react';
import PriceComparisonListing from '../../../../features/stock/components/price-comparison/price-comparison-listing';

export const metadata: Metadata = {
    title: 'Сравнение цен',
    description: 'Анализ ценовой политики конкурентов и мониторинг рынка',
};

export default async function PriceComparisonPage(props: { searchParams: Promise<SearchParams> }) {
    const searchParams = await props.searchParams;
    searchParamsCache.parse(searchParams);

    return (
        <PageContainer scrollable={false}>
            <div className='flex flex-1 flex-col space-y-4'>
                <div className='flex items-start justify-between'>
                    <Heading
                        title='Сравнение цен'
                        description='Анализ ценовой политики конкурентов и мониторинг рынка'
                    />
                </div>
                <Separator />
                <Suspense
                    fallback={
                        <DataTableSkeleton columnCount={5} rowCount={8} filterCount={2} />
                    }
                >
                    <PriceComparisonListing searchParams={searchParams} />
                </Suspense>
            </div>
        </PageContainer>
    );
}
