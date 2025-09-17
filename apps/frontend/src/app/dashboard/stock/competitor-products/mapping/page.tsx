import { Metadata } from 'next';
import PageContainer from '@/components/layout/page-container';
import { buttonVariants } from '@/components/ui/button';
import { Heading } from '@/components/ui/heading';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { CompetitorMappingView } from '@/features/stock/components/competitor-products/competitor-mapping-view';

export const metadata: Metadata = {
    title: 'Сопоставления товаров конкурентов',
    description: 'Привязка товара конкурента к нашему товару',
};

export default function CompetitorProductsMappingPage() {
    return (
        <PageContainer scrollable={false}>
            <div className='flex flex-1 flex-col space-y-4'>
                <div className='flex items-start justify-between'>
                    <Heading
                        title='Сопоставления'
                        description='Добавьте связь между нашим товаром и товаром конкурента'
                    />
                    <Link href="/dashboard/stock/competitor-products" className={cn(buttonVariants({ variant: "outline" }), 'text-xs md:text-sm')}>
                        К списку товаров конкурентов
                    </Link>
                </div>
                <Separator />
                <CompetitorMappingView />
            </div>
        </PageContainer>
    );
}


