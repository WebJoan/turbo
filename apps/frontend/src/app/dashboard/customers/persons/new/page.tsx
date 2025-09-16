import { Suspense } from 'react';
import PageContainer from '@/components/layout/page-container';
import { Heading } from '@/components/ui/heading';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { PersonCreateForm } from '@/features/persons/components';

export const metadata = { title: 'Создать персону' };

export default function NewPersonPage() {
    return (
        <PageContainer scrollable={true}>
            <div className="flex flex-1 flex-col space-y-6">
                <div className="flex items-start justify-between">
                    <Heading title="Создать персону" description="Добавление контактного лица компании" />
                </div>
                <Separator />
                <Suspense fallback={<CreateFormSkeleton />}>
                    <PersonCreateForm />
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


