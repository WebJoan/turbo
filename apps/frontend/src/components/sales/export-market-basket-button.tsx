'use client';

import { Button } from '@/components/ui/button';
import { Download, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';

interface ReportParams {
    date_from?: string;
    date_to?: string;
    min_support?: number;
    min_confidence?: number;
    min_lift?: number;
}

export default function ExportMarketBasketButton() {
    const [isLoading, setIsLoading] = useState(false);
    const [progressMessage, setProgressMessage] = useState('');
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    
    // Параметры отчета
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [minSupport, setMinSupport] = useState('0.005');
    const [minConfidence, setMinConfidence] = useState('0.1');
    const [minLift, setMinLift] = useState('1.0');

    const checkTaskStatus = async (taskId: string, apiUrl: string): Promise<void> => {
        const maxAttempts = 120; // Максимум 10 минут (120 * 5 секунд)
        let attempts = 0;

        const checkStatus = async (): Promise<boolean> => {
            attempts++;

            try {
                const statusResponse = await fetch(
                    `${apiUrl}/api/sales/report-status/${taskId}/`,
                    {
                        method: 'GET',
                        credentials: 'include',
                    }
                );

                if (!statusResponse.ok) {
                    throw new Error(`Ошибка сервера: ${statusResponse.status}`);
                }

                const statusData = await statusResponse.json();

                // Проверяем состояние задачи
                if (statusData.state === 'SUCCESS') {
                    if (statusData.status === 'error') {
                        throw new Error(statusData.message || 'Ошибка при создании отчета');
                    }

                    // Задача успешно завершена
                    const result = statusData.result;
                    
                    if (result && result.file_path) {
                        // Показываем информацию о результате
                        toast.success(
                            `Market Basket Analysis создан! Транзакций: ${result.transactions_count}, Правил: ${result.rules_count}`,
                            { duration: 5000 }
                        );
                        
                        // Создаем ссылку для скачивания файла через media URL
                        const mediaUrl = `${apiUrl}/media/${result.file_path.split('/media/')[1]}`;
                        const a = document.createElement('a');
                        a.href = mediaUrl;
                        a.download = result.filename;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        
                        return true;
                    } else {
                        throw new Error('Файл отчета не создан');
                    }
                } else if (statusData.state === 'FAILURE') {
                    throw new Error(statusData.error || 'Ошибка при выполнении задачи');
                } else if (statusData.state === 'PENDING' || statusData.state === 'STARTED') {
                    // Задача ещё выполняется
                    setProgressMessage(
                        `${statusData.message || 'Обработка данных...'} (${attempts}/${maxAttempts})`
                    );
                    return false;
                }

                // Неизвестное состояние
                setProgressMessage(`Состояние: ${statusData.state} (${attempts}/${maxAttempts})`);
                return false;

            } catch (error) {
                console.error('Ошибка при проверке статуса:', error);
                throw error;
            }
        };

        // Проверяем статус с интервалом 5 секунд
        while (attempts < maxAttempts) {
            const isComplete = await checkStatus();
            if (isComplete) {
                return;
            }
            await new Promise(resolve => setTimeout(resolve, 5000)); // 5 секунд
        }

        throw new Error('Превышено время ожидания. Попробуйте позже или проверьте логи сервера.');
    };

    const handleExport = async () => {
        setIsLoading(true);
        setProgressMessage('Запуск Market Basket Analysis...');
        setIsDialogOpen(false);

        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

            // Формируем параметры запроса
            const params: ReportParams = {};

            if (dateFrom) {
                params.date_from = dateFrom;
            }
            if (dateTo) {
                params.date_to = dateTo;
            }
            if (minSupport) {
                params.min_support = parseFloat(minSupport);
            }
            if (minConfidence) {
                params.min_confidence = parseFloat(minConfidence);
            }
            if (minLift) {
                params.min_lift = parseFloat(minLift);
            }

            // Запускаем задачу создания отчета
            const response = await fetch(`${apiUrl}/api/sales/reports/market-basket-analysis/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify(params),
            });

            if (response.status === 401 || response.status === 403) {
                toast.error('Необходима авторизация. Пожалуйста, войдите в систему.');
                return;
            }

            if (!response.ok) {
                const errorData = await response.json();
                console.error('Ошибка сервера:', errorData);
                throw new Error(errorData.message || `Ошибка сервера: ${response.status}`);
            }

            const data = await response.json();
            const taskId = data.task_id;

            if (!taskId) {
                throw new Error('Не получен task_id от сервера');
            }

            toast.info('Market Basket Analysis запущен. Ожидайте...', { duration: 3000 });
            setProgressMessage('Анализ товарных корзин и поиск ассоциаций...');

            // Отслеживаем статус задачи
            await checkTaskStatus(taskId, apiUrl);

        } catch (error) {
            console.error('Ошибка при экспорте:', error);
            toast.error(
                error instanceof Error ? error.message : 'Не удалось создать отчет',
                { duration: 5000 }
            );
        } finally {
            setIsLoading(false);
            setProgressMessage('');
        }
    };

    return (
        <div className="flex flex-col gap-2">
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogTrigger asChild>
                    <Button
                        disabled={isLoading}
                        variant="default"
                        className="gap-2"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Создание отчета...
                            </>
                        ) : (
                            <>
                                <Download className="h-4 w-4" />
                                Анализ корзины
                            </>
                        )}
                    </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-[500px]">
                    <DialogHeader>
                        <DialogTitle>Параметры Market Basket Analysis</DialogTitle>
                        <DialogDescription>
                            Анализ товаров, покупаемых вместе (ассоциативные правила)
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                            <Label htmlFor="date_from">Период анализа с (опционально)</Label>
                            <Input
                                id="date_from"
                                type="date"
                                value={dateFrom}
                                onChange={(e) => setDateFrom(e.target.value)}
                            />
                        </div>

                        <div className="grid gap-2">
                            <Label htmlFor="date_to">Период анализа по (опционально)</Label>
                            <Input
                                id="date_to"
                                type="date"
                                value={dateTo}
                                onChange={(e) => setDateTo(e.target.value)}
                            />
                        </div>

                        <div className="border-t pt-4 space-y-4">
                            <h4 className="font-medium text-sm">Параметры фильтрации</h4>
                            
                            <div className="grid gap-2">
                                <Label htmlFor="min_support">
                                    Min Support (Мин. поддержка)
                                </Label>
                                <Input
                                    id="min_support"
                                    type="number"
                                    step="0.001"
                                    min="0.001"
                                    max="1.0"
                                    value={minSupport}
                                    onChange={(e) => setMinSupport(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">
                                    0.005 = 0.5% (доля транзакций с товаром)
                                </p>
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="min_confidence">
                                    Min Confidence (Мин. уверенность)
                                </Label>
                                <Input
                                    id="min_confidence"
                                    type="number"
                                    step="0.01"
                                    min="0.01"
                                    max="1.0"
                                    value={minConfidence}
                                    onChange={(e) => setMinConfidence(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">
                                    0.1 = 10% (вероятность покупки B при покупке A)
                                </p>
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="min_lift">
                                    Min Lift (Мин. подъем)
                                </Label>
                                <Input
                                    id="min_lift"
                                    type="number"
                                    step="0.1"
                                    min="0.1"
                                    max="100.0"
                                    value={minLift}
                                    onChange={(e) => setMinLift(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">
                                    1.0 и выше = положительная связь товаров
                                </p>
                            </div>
                        </div>

                        <div className="text-sm text-muted-foreground space-y-1 border-t pt-4">
                            <p><strong>Support</strong> - доля заказов с товаром/парой</p>
                            <p><strong>Confidence</strong> - вероятность покупки B при A</p>
                            <p><strong>Lift</strong> - насколько чаще B покупается с A</p>
                            <p className="pt-2">• 7 листов: Правила, Топ Lift, Топ пары, Топ товары, Статистика, Параметры, Пояснения</p>
                        </div>
                    </div>
                    <div className="flex justify-end gap-2">
                        <Button
                            variant="outline"
                            onClick={() => setIsDialogOpen(false)}
                        >
                            Отмена
                        </Button>
                        <Button onClick={handleExport}>
                            <Download className="mr-2 h-4 w-4" />
                            Создать отчет
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
            {isLoading && progressMessage && (
                <p className="text-xs text-muted-foreground text-center">
                    {progressMessage}
                </p>
            )}
        </div>
    );
}

