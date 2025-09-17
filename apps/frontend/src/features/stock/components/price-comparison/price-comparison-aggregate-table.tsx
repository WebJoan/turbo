'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';
import { formatPrice, formatStockStatus } from '@/lib/stock-client';
import { CompetitorPriceStockSnapshot } from '@/types/stock';
import { searchProductsFromClient } from '@/lib/client-api';
import { fetchLatestCompetitorSnapshotsClient } from '@/lib/stock-client';

type ProductLite = {
    id: number;
    name: string;
    ext_id?: string;
};

type Row = {
    product: ProductLite;
    ourCurrentPrice: number | null;
    competitorPrices: CompetitorPriceStockSnapshot[];
};

export default function PriceComparisonAggregateTable() {
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [rows, setRows] = useState<Row[]>([]);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // начальная подгрузка последних 100 снимков без фильтра
        const loadInitial = async () => {
            try {
                setLoading(true);
                setError(null);
                const snapshots = await fetchLatestCompetitorSnapshotsClient();
                // у нас нет связи с нашими товарами напрямую в снимках, поэтому пока показываем агрегат по конкурентам
                const singleRow: Row = {
                    product: { id: 0, name: 'Подборка последних цен конкурентов' },
                    ourCurrentPrice: null,
                    competitorPrices: snapshots,
                };
                setRows([singleRow]);
            } catch (e) {
                setError(e instanceof Error ? e.message : 'Ошибка загрузки');
            } finally {
                setLoading(false);
            }
        };
        loadInitial();
    }, []);

    const onSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            setLoading(true);
            setError(null);
            if (!query.trim()) {
                const snapshots = await fetchLatestCompetitorSnapshotsClient();
                const singleRow: Row = {
                    product: { id: 0, name: 'Подборка последних цен конкурентов' },
                    ourCurrentPrice: null,
                    competitorPrices: snapshots,
                };
                setRows([singleRow]);
                return;
            }
            const { items } = await searchProductsFromClient({ search: query, limit: 5 });
            // Пока нет бэкенд-API для массового сравнения, показываем по каждому найденному товару ссылку в детальную страницу
            const productRows: Row[] = items.map((p) => ({
                product: { id: p.id, name: p.name, ext_id: p.ext_id },
                ourCurrentPrice: null,
                competitorPrices: [],
            }));
            setRows(productRows);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Ошибка поиска');
        } finally {
            setLoading(false);
        }
    };

    const caption = useMemo(() => {
        if (loading) return 'Загрузка...';
        if (error) return `Ошибка: ${error}`;
        return undefined;
    }, [loading, error]);

    return (
        <Card>
            <CardHeader>
                <CardTitle>Сводная таблица: наши товары и цены конкурентов</CardTitle>
            </CardHeader>
            <CardContent>
                <form onSubmit={onSearch} className="mb-4 flex items-center gap-2">
                    <div className="relative flex-1">
                        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                            className="pl-8"
                            placeholder="Поиск нашего товара по названию/ID..."
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                        />
                    </div>
                </form>

                <Table>
                    {caption && <TableCaption>{caption}</TableCaption>}
                    <TableHeader>
                        <TableRow>
                            <TableHead>Наш товар</TableHead>
                            <TableHead>Цена конкурента</TableHead>
                            <TableHead>Конкурент</TableHead>
                            <TableHead>Артикул</TableHead>
                            <TableHead>Наличие</TableHead>
                            <TableHead>Обновлено</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {rows.length === 0 && !loading && (
                            <TableRow>
                                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                                    Нет данных
                                </TableCell>
                            </TableRow>
                        )}

                        {rows.map((row) => {
                            if (row.competitorPrices.length > 0) {
                                return row.competitorPrices.map((snap) => (
                                    <TableRow key={`snap-${snap.id}`}>
                                        <TableCell className="whitespace-nowrap font-medium">
                                            {row.product.name}
                                        </TableCell>
                                        <TableCell className="text-right whitespace-nowrap">
                                            {formatPrice(snap.price_ex_vat, snap.currency)}
                                            {snap.vat_rate && (
                                                <Badge variant="outline" className="ml-2 text-[10px]">НДС {(snap.vat_rate * 100).toFixed(0)}%</Badge>
                                            )}
                                        </TableCell>
                                        <TableCell className="whitespace-nowrap">{snap.competitor_name}</TableCell>
                                        <TableCell className="whitespace-nowrap">{snap.product_part_number}</TableCell>
                                        <TableCell className="whitespace-nowrap">{formatStockStatus(snap.stock_status)}</TableCell>
                                        <TableCell className="whitespace-nowrap">{new Date(snap.collected_at).toLocaleDateString('ru-RU')}</TableCell>
                                    </TableRow>
                                ));
                            }
                            return (
                                <TableRow key={`product-${row.product.id}`}>
                                    <TableCell className="whitespace-nowrap font-medium">
                                        <a className="underline" href={`/dashboard/stock/price-comparison/${row.product.id}`}>
                                            {row.product.name}
                                        </a>
                                    </TableCell>
                                    <TableCell colSpan={5} className="text-muted-foreground">
                                        Выберите товар для детального сравнения
                                    </TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
}


