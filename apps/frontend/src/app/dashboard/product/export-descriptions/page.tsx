'use client';

import PageContainer from '@/components/layout/page-container';
import { buttonVariants } from '@/components/ui/button';
import { Heading } from '@/components/ui/heading';
import { Separator } from '@/components/ui/separator';
import { ExportDescriptionsForm } from '@/features/products/components/export-descriptions-form';
import { cn } from '@/lib/utils';
import { IconDownload } from '@tabler/icons-react';

export default function ExportDescriptionsPage() {
    return (
        <PageContainer scrollable={false}>
            <div className='flex flex-1 flex-col space-y-4'>
                <div className='flex items-start justify-between'>
                    <Heading
                        title='Выгрузка описаний товаров'
                        description='Экспорт описательных свойств товаров с возможностью фильтрации по подгруппам и брендам в Excel файл'
                    />
                </div>
                <Separator />
                <div className='flex flex-1 flex-col space-y-4 max-w-4xl'>
                    <ExportDescriptionsForm />
                </div>
            </div>
        </PageContainer>
    );
}
