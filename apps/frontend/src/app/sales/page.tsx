'use client';

import { useState } from 'react';
import { SalesFilters } from '@/types/sales';
import { SalesFiltersComponent } from '@/features/sales/components/sales-filters';
import { SalesSummaryComponent } from '@/features/sales/components/sales-summary';
import { ProductSalesChart } from '@/features/sales/components/product-sales-chart';
import { TopCustomersChart } from '@/features/sales/components/top-customers-chart';
import { TopProductsChart } from '@/features/sales/components/top-products-chart';
import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger
} from '@/components/ui/tabs';

export default function SalesAnalyticsPage() {
    const [filters, setFilters] = useState<SalesFilters>({
        period_type: 'month',
        date_from: new Date(
            new Date().getFullYear(),
            new Date().getMonth() - 6,
            1
        )
            .toISOString()
            .split('T')[0],
        date_to: new Date().toISOString().split('T')[0]
    });

    const handleFiltersChange = (newFilters: SalesFilters) => {
        setFilters(newFilters);
    };

    return (
        <div className="flex-1 space-y-4 p-4 pt-6 md:p-8">
            <div className="flex items-center justify-between space-y-2">
                <h2 className="text-3xl font-bold tracking-tight">Аналитика продаж</h2>
            </div>

            {/* Фильтры */}
            <SalesFiltersComponent
                onFiltersChange={handleFiltersChange}
                initialFilters={filters}
            />

            {/* Сводная статистика */}
            <SalesSummaryComponent filters={filters} />

            {/* Вкладки с различными видами аналитики */}
            <Tabs defaultValue="customers" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="customers">По клиентам</TabsTrigger>
                    <TabsTrigger value="products">По товарам</TabsTrigger>
                </TabsList>

                <TabsContent value="customers" className="space-y-4">
                    <div className="grid gap-4">
                        <TopCustomersChart filters={filters} limit={20} />
                    </div>
                </TabsContent>

                <TabsContent value="products" className="space-y-4">
                    <div className="grid gap-4">
                        <TopProductsChart filters={filters} limit={20} />
                        <ProductSalesChart filters={filters} chartType="area" />
                    </div>
                </TabsContent>
            </Tabs>
        </div>
    );
}

