import { Suspense } from 'react';
import { RFQPageContent } from './rfq-page-content';
import PageContainer from '@/components/layout/page-container';
import { Heading } from '@/components/ui/heading';
import { Separator } from '@/components/ui/separator';
import { DataTableSkeleton } from '@/components/ui/table/data-table-skeleton';
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { IconPlus } from '@tabler/icons-react';
import Link from 'next/link';
import { NewRFQButton } from './rfq-new-button';

export const metadata = {
    title: 'Дашборд: Запросы цен (RFQ)'
};

export default function RFQsPage() {
    return (
        <PageContainer scrollable={false}>
            <div className='flex flex-1 flex-col space-y-4'>
                <div className='flex items-start justify-between'>
                    <Heading
                        title='Запросы цен (RFQ)'
                        description='Управление запросами цен от клиентов'
                    />
                    <NewRFQButton />
                </div>
                <Separator />
                <Suspense
                    fallback={
                        <DataTableSkeleton columnCount={10} rowCount={10} filterCount={2} />
                    }
                >
                    <RFQPageContent />
                </Suspense>
            </div>
        </PageContainer>
    );
}
