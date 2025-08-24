import PageContainer from '@/components/layout/page-container';
import AIChat from '@/components/ai/ai-chat';

export const metadata = {
    title: 'Дашборд: AI чат'
};

export default function AIInDashboardPage() {
    return (
        <PageContainer scrollable={false}>
            <div className='mx-auto flex w-full max-w-5xl flex-1 flex-col gap-4'>
                <div className='flex items-center justify-between'>
                    <h1 className='text-xl font-semibold'>AI чат</h1>
                </div>
                <AIChat className='h-[calc(100vh-180px)]' />
            </div>
        </PageContainer>
    );
}


