import { Metadata } from 'next';
import { PriceComparisonView } from '@/features/stock/components/price-comparison/price-comparison-view';

interface PriceComparisonDetailPageProps {
    params: {
        productId: string;
    };
}

export const metadata: Metadata = {
    title: 'Сравнение цен товара',
    description: 'Детальный анализ цен конкурентов для выбранного товара',
};

export default function PriceComparisonDetailPage({
    params: { productId }
}: PriceComparisonDetailPageProps) {
    const productIdNum = parseInt(productId, 10);

    if (isNaN(productIdNum)) {
        return (
            <div className="flex items-center justify-center p-8">
                <div className="text-center">
                    <h1 className="text-2xl font-bold text-red-600 mb-2">Ошибка</h1>
                    <p className="text-muted-foreground">Некорректный ID товара</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Сравнение цен товара</h1>
                <p className="text-muted-foreground">
                    Анализ цен конкурентов и история цен для товара #{productId}
                </p>
            </div>

            <PriceComparisonView productId={productIdNum} />
        </div>
    );
}
