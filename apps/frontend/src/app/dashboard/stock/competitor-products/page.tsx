import { Metadata } from 'next';
import PageContainer from '@/components/layout/page-container';
import { buttonVariants } from '@/components/ui/button';
import { Heading } from '@/components/ui/heading';
import { Separator } from '@/components/ui/separator';
import { DataTableSkeleton } from '@/components/ui/table/data-table-skeleton';
import { searchParamsCache } from '@/lib/searchparams';
import { cn } from '@/lib/utils';
import { IconPlus } from '@tabler/icons-react';
import Link from 'next/link';
import { SearchParams } from 'nuqs/server';
import { Suspense } from 'react';
import CompetitorProductsListingPage from '@/features/stock/components/competitor-products/competitor-products-listing';

export const metadata: Metadata = {
    title: 'Товары конкурентов',
    description: 'Управление товарами конкурентов и их сопоставление',
};

export default async function CompetitorProductsPage(props: { searchParams: Promise<SearchParams> }) {
    const searchParams = await props.searchParams;
    searchParamsCache.parse(searchParams);

    return (
        <PageContainer scrollable={false}>
            <div className='flex flex-1 flex-col space-y-4'>
                <div className='flex items-start justify-between'>
                    <Heading
                        title='Товары конкурентов'
                        description='Список товаров конкурентов с возможностью сопоставления с нашими товарами'
                    />
                    <div className="flex flex-col sm:flex-row gap-2">
                        <Link href="/dashboard/stock/competitor-products/mapping" className={cn(buttonVariants({ variant: "outline" }), 'text-xs md:text-sm')}>
                            Управление сопоставлениями
                        </Link>
                        <Link href="/dashboard/stock/competitor-products/new" className={cn(buttonVariants(), 'text-xs md:text-sm')}>
                            <IconPlus className='mr-2 h-4 w-4' /> Add New
                        </Link>
                    </div>
                </div>
                <Separator />
                <Suspense
                    fallback={
                        <DataTableSkeleton columnCount={5} rowCount={8} filterCount={2} />
                    }
                >
                    <CompetitorProductsListingPage searchParams={searchParams} />
                </Suspense>
            </div>
        </PageContainer>
    );
}
