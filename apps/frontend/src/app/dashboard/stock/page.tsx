import { Metadata } from 'next';
import PageContainer from '@/components/layout/page-container';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import Link from 'next/link';
import ExportPriceComparisonButton from '@/components/stock/export-price-comparison-button';
import ExportCompetitorSalesDialog from '@/components/stock/export-competitor-sales-dialog';
import ExportCustomerDynamicsButton from '@/components/sales/export-customer-dynamics-button';
import ExportProductDynamicsButton from '@/components/sales/export-product-dynamics-button';
import ExportCohortAnalysisButton from '@/components/sales/export-cohort-analysis-button';
import ExportRFMSegmentationButton from '@/components/sales/export-rfm-segmentation-button';
import ExportLTVAnalysisButton from '@/components/sales/export-ltv-analysis-button';
import ExportMarketBasketButton from '@/components/sales/export-market-basket-button';
import {
    Building2,
    Package,
    TrendingUp,
    BarChart3,
    Plus,
    Users,
    Target,
    Database
} from 'lucide-react';

export const metadata: Metadata = {
    title: 'Управление конкурентами и ценами',
    description: 'Мониторинг конкурентов, сравнение цен и анализ рынка',
};

export default function StockDashboardPage() {
    const stats = [
        {
            title: 'Конкурентов',
            value: '12',
            description: 'Активных конкурентов',
            icon: Building2,
            href: '/dashboard/stock/competitors',
        },
        {
            title: 'Товаров конкурентов',
            value: '2,847',
            description: 'Отслеживаемых позиций',
            icon: Package,
            href: '/dashboard/stock/competitor-products',
        },
        {
            title: 'Сопоставлений',
            value: '1,245',
            description: 'Связанных товаров',
            icon: Target,
            href: '/dashboard/stock/competitor-products',
        },
        {
            title: 'Исторических записей',
            value: '15,632',
            description: 'Ценовых данных',
            icon: Database,
            href: '/dashboard/stock/price-comparison',
        },
    ];

    const quickActions = [
        {
            title: 'Добавить конкурента',
            description: 'Зарегистрировать нового конкурента',
            icon: Plus,
            href: '/dashboard/stock/competitors/new',
            variant: 'default' as const,
        },
        {
            title: 'Импорт цен',
            description: 'Загрузить цены из MySQL',
            icon: Database,
            href: '/dashboard/stock/import',
            variant: 'outline' as const,
        },
        {
            title: 'Сравнение цен',
            description: 'Анализ цен конкурентов',
            icon: TrendingUp,
            href: '/dashboard/stock/price-comparison',
            variant: 'outline' as const,
        },
        {
            title: 'Отчеты',
            description: 'Аналитика и отчеты',
            icon: BarChart3,
            href: '/dashboard/stock/reports',
            variant: 'outline' as const,
        },
    ];

    return (
        <PageContainer scrollable={false}>
            <div className="space-y-8">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Управление конкурентами</h1>
                    <p className="text-muted-foreground">
                        Мониторинг цен конкурентов, анализ рынка и сравнение предложений
                    </p>
                </div>

                {/* Статистика */}
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {stats.map((stat) => (
                        <Card key={stat.title} className="hover:shadow-md transition-shadow">
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
                                <stat.icon className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">{stat.value}</div>
                                <p className="text-xs text-muted-foreground">{stat.description}</p>
                                <Link href={stat.href}>
                                    <Button variant="ghost" size="sm" className="mt-2 h-6 px-2 text-xs">
                                        Перейти →
                                    </Button>
                                </Link>
                            </CardContent>
                        </Card>
                    ))}
                </div>

                {/* Быстрые действия */}
                <Card>
                    <CardHeader>
                        <CardTitle>Быстрые действия</CardTitle>
                        <CardDescription>
                            Часто используемые функции для работы с данными конкурентов
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="mb-6 space-y-4">
                            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 rounded-lg border">
                                <div className="flex-1">
                                    <h3 className="font-semibold text-lg mb-1">Экспорт сравнения цен</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Выгрузить все совпадения по part number с ценами конкурентов в Excel
                                    </p>
                                </div>
                                <ExportPriceComparisonButton />
                            </div>

                            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-950 dark:to-emerald-950 rounded-lg border">
                                <div className="flex-1">
                                    <h3 className="font-semibold text-lg mb-1">Экспорт продаж конкурентов</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Анализ продаж конкурентов: выберите период и конкурентов для расчета продаж
                                    </p>
                                </div>
                                <ExportCompetitorSalesDialog />
                            </div>

                            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950 dark:to-teal-950 rounded-lg border">
                                <div className="flex-1">
                                    <h3 className="font-semibold text-lg mb-1">Динамика продаж по клиентам</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Анализ выручки, количества заказов и среднего чека по клиентам в разрезе времени
                                    </p>
                                </div>
                                <ExportCustomerDynamicsButton />
                            </div>

                            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-950 dark:to-pink-950 rounded-lg border">
                                <div className="flex-1">
                                    <h3 className="font-semibold text-lg mb-1">Динамика продаж по товарам</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Анализ выручки, количества заказов, среднего чека и объема продаж по товарам
                                    </p>
                                </div>
                                <ExportProductDynamicsButton />
                            </div>

                            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-orange-50 to-amber-50 dark:from-orange-950 dark:to-amber-950 rounded-lg border">
                                <div className="flex-1">
                                    <h3 className="font-semibold text-lg mb-1">Когортный анализ клиентов</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Retention Rate и Revenue Retention по когортам. Анализ удержания клиентов
                                    </p>
                                </div>
                                <ExportCohortAnalysisButton />
                            </div>

                            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-cyan-50 to-sky-50 dark:from-cyan-950 dark:to-sky-950 rounded-lg border">
                                <div className="flex-1">
                                    <h3 className="font-semibold text-lg mb-1">RFM-сегментация клиентов</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Сегментация по Recency, Frequency, Monetary. Champions, Loyal, At Risk и др.
                                    </p>
                                </div>
                                <ExportRFMSegmentationButton />
                            </div>

                            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-rose-50 to-red-50 dark:from-rose-950 dark:to-red-950 rounded-lg border">
                                <div className="flex-1">
                                    <h3 className="font-semibold text-lg mb-1">LTV анализ клиентов</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Customer Lifetime Value: историческая и прогнозная ценность клиентов
                                    </p>
                                </div>
                                <ExportLTVAnalysisButton />
                            </div>

                            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-violet-50 to-fuchsia-50 dark:from-violet-950 dark:to-fuchsia-950 rounded-lg border">
                                <div className="flex-1">
                                    <h3 className="font-semibold text-lg mb-1">Анализ корзины (Market Basket)</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Ассоциативные правила: какие товары покупаются вместе. Support, Confidence, Lift
                                    </p>
                                </div>
                                <ExportMarketBasketButton />
                            </div>
                        </div>

                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            {quickActions.map((action) => (
                                <Link key={action.title} href={action.href}>
                                    <Card className="hover:shadow-md transition-shadow cursor-pointer">
                                        <CardContent className="flex flex-col items-center justify-center p-6">
                                            <action.icon className="h-8 w-8 mb-4 text-muted-foreground" />
                                            <h3 className="font-medium text-center mb-2">{action.title}</h3>
                                            <p className="text-sm text-muted-foreground text-center">
                                                {action.description}
                                            </p>
                                        </CardContent>
                                    </Card>
                                </Link>
                            ))}
                        </div>
                    </CardContent>
                </Card>

                {/* Информация о системе */}
                <Card>
                    <CardHeader>
                        <CardTitle>О системе мониторинга</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            <div className="space-y-2">
                                <h4 className="font-medium flex items-center gap-2">
                                    <Users className="h-4 w-4" />
                                    Конкуренты
                                </h4>
                                <p className="text-sm text-muted-foreground">
                                    Управление списком конкурентов с поддержкой B2B сайтов и парсинга
                                </p>
                            </div>

                            <div className="space-y-2">
                                <h4 className="font-medium flex items-center gap-2">
                                    <Package className="h-4 w-4" />
                                    Сопоставление товаров
                                </h4>
                                <p className="text-sm text-muted-foreground">
                                    Интеллектуальная система сопоставления товаров по параметрам и аналогам
                                </p>
                            </div>

                            <div className="space-y-2">
                                <h4 className="font-medium flex items-center gap-2">
                                    <TrendingUp className="h-4 w-4" />
                                    Анализ цен
                                </h4>
                                <p className="text-sm text-muted-foreground">
                                    Мониторинг ценовой динамики и сравнение с конкурентами
                                </p>
                            </div>
                        </div>

                        <div className="pt-4 border-t">
                            <div className="flex items-center gap-2">
                                <Badge variant="secondary">Beta</Badge>
                                <span className="text-sm text-muted-foreground">
                                    Система находится в активной разработке. Новые функции добавляются регулярно.
                                </span>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </PageContainer>
    );
}
