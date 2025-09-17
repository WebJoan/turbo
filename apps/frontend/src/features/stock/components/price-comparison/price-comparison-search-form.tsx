'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search } from 'lucide-react';

export function PriceComparisonSearchForm() {
    const router = useRouter();
    const [value, setValue] = useState('');

    const onSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const id = parseInt(value, 10);
        if (!isNaN(id) && id > 0) {
            router.push(`/dashboard/stock/price-comparison/${id}`);
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>Выберите товар для анализа</CardTitle>
                <CardDescription>
                    Введите ID товара для просмотра цен конкурентов
                </CardDescription>
            </CardHeader>
            <CardContent>
                <form onSubmit={onSubmit} className="flex gap-4">
                    <div className="flex-1">
                        <Input
                            placeholder="Введите ID товара..."
                            className="w-full"
                            inputMode="numeric"
                            value={value}
                            onChange={(e) => setValue(e.target.value)}
                        />
                    </div>
                    <Button type="submit">
                        <Search className="mr-2 h-4 w-4" />
                        Найти
                    </Button>
                </form>
            </CardContent>
        </Card>
    );
}


