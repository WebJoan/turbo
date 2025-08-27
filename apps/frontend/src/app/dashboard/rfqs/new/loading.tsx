import PageContainer from '@/components/layout/page-container';
import { Heading } from '@/components/ui/heading';
import { Separator } from '@/components/ui/separator';
import FormCardSkeleton from '@/components/form-card-skeleton';
import { DataTableSkeleton } from '@/components/ui/table/data-table-skeleton';

export default function Loading() {
    return (
        <PageContainer scrollable={true}>
            <div className="flex flex-1 flex-col space-y-6">
                <div className="flex items-start justify-between">
                    <Heading title="Создать новый RFQ" description="Загрузка формы создания RFQ" />
                </div>
                <Separator />
                <div className="space-y-6">
                    <FormCardSkeleton />
                    <DataTableSkeleton columnCount={10} rowCount={4} withPagination={false} />
                </div>
            </div>
        </PageContainer>
    );
}


