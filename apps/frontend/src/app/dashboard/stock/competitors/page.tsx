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
import CompetitorsListingPage from '@/features/stock/components/competitors/competitors-listing';

export const metadata: Metadata = {
    title: 'Конкуренты',
    description: 'Управление списком конкурентов',
};

export default async function CompetitorsPage(props: { searchParams: Promise<SearchParams> }) {
    const searchParams = await props.searchParams;
    searchParamsCache.parse(searchParams);

    return (
        <PageContainer scrollable={false}>
            <div className='flex flex-1 flex-col space-y-4'>
                <div className='flex items-start justify-between'>
                    <Heading
                        title='Конкуренты'
                        description='Управление конкурентами и их B2B платформами'
                    />
                    <Link
                        href='/dashboard/stock/competitors/new'
                        className={cn(buttonVariants(), 'text-xs md:text-sm')}
                    >
                        <IconPlus className='mr-2 h-4 w-4' /> Add New
                    </Link>
                </div>
                <Separator />
                <Suspense
                    fallback={
                        <DataTableSkeleton columnCount={5} rowCount={8} filterCount={2} />
                    }
                >
                    <CompetitorsListingPage searchParams={searchParams} />
                </Suspense>
            </div>
        </PageContainer>
    );
}
