import { Suspense } from 'react';
import PageContainer from '@/components/layout/page-container';
import { Heading } from '@/components/ui/heading';
import { Separator } from '@/components/ui/separator';
import { RFQCreateForm } from '@/features/rfqs/components';
import { Skeleton } from '@/components/ui/skeleton';

export const metadata = {
    title: 'Создать RFQ - Запрос цен'
};

export default function NewRFQPage() {
    return (
        <PageContainer scrollable={true}>
            <div className="flex flex-1 flex-col space-y-6">
                <div className="flex items-start justify-between">
                    <Heading
                        title="Создать новый RFQ"
                        description="Создание нового запроса цен для клиента"
                    />
                </div>
                <Separator />
                <Suspense fallback={<CreateFormSkeleton />}>
                    <RFQCreateForm />
                </Suspense>
            </div>
        </PageContainer>
    );
}

function CreateFormSkeleton() {
    return (
        <div className="space-y-6">
            <div className="grid gap-6 md:grid-cols-2">
                <Skeleton className="h-10" />
                <Skeleton className="h-10" />
            </div>
            <Skeleton className="h-20" />
            <div className="space-y-4">
                <Skeleton className="h-8 w-40" />
                <div className="space-y-2">
                    <Skeleton className="h-10" />
                    <Skeleton className="h-10" />
                    <Skeleton className="h-10" />
                </div>
            </div>
            <Skeleton className="h-10 w-32" />
        </div>
    );
}
