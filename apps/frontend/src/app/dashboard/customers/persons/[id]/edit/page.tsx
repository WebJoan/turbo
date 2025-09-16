import { Suspense } from 'react';
import PageContainer from '@/components/layout/page-container';
import { Heading } from '@/components/ui/heading';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { PersonEditForm } from '@/features/persons/components';

export const metadata = { title: 'Редактировать персону' };

export default async function EditPersonPage(props: { params: Promise<{ id: string }> }) {
    const params = await props.params;
    const personId = Number(params.id);
    return (
        <PageContainer scrollable={true}>
            <div className="flex flex-1 flex-col space-y-6">
                <div className="flex items-start justify-between">
                    <Heading title={`Редактирование персоны #${isNaN(personId) ? '' : personId}`} description="Изменение данных контактного лица" />
                </div>
                <Separator />
                <Suspense fallback={<EditFormSkeleton />}>
                    {!isNaN(personId) && <PersonEditForm personId={personId} />}
                </Suspense>
            </div>
        </PageContainer>
    );
}

function EditFormSkeleton() {
    return (
        <div className="space-y-6">
            <div className="grid gap-6 md:grid-cols-2">
                <Skeleton className="h-10" />
                <Skeleton className="h-10" />
            </div>
            <div className="grid gap-6 md:grid-cols-3">
                <Skeleton className="h-10" />
                <Skeleton className="h-10" />
                <Skeleton className="h-10" />
            </div>
            <Skeleton className="h-24" />
            <Skeleton className="h-10 w-32" />
        </div>
    );
}


