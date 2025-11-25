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
    reference_date?: string;
}

export default function ExportRFMSegmentationButton() {
    const [isLoading, setIsLoading] = useState(false);
    const [progressMessage, setProgressMessage] = useState('');
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    
    // Параметры отчета
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [referenceDate, setReferenceDate] = useState('');

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
                            `RFM-сегментация создана! Клиентов: ${result.customers_count}, Сегментов: ${result.segments_count}`,
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
        setProgressMessage('Запуск RFM-сегментации...');
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
            if (referenceDate) {
                params.reference_date = referenceDate;
            }

            // Запускаем задачу создания отчета
            const response = await fetch(`${apiUrl}/api/sales/reports/rfm-segmentation/`, {
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

            toast.info('RFM-сегментация запущена. Ожидайте...', { duration: 3000 });
            setProgressMessage('Анализ клиентов и создание сегментов...');

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
                                RFM-сегментация
                            </>
                        )}
                    </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>Параметры RFM-сегментации клиентов</DialogTitle>
                        <DialogDescription>
                            Анализ клиентов по Recency, Frequency, Monetary с автоматической сегментацией
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid gap-2">
                            <Label htmlFor="reference_date">Референсная дата (опционально)</Label>
                            <Input
                                id="reference_date"
                                type="date"
                                value={referenceDate}
                                onChange={(e) => setReferenceDate(e.target.value)}
                                placeholder="Сегодня"
                            />
                            <p className="text-xs text-muted-foreground">
                                Дата для расчета Recency. По умолчанию - сегодня
                            </p>
                        </div>

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

                        <div className="text-sm text-muted-foreground space-y-1">
                            <p><strong>R (Recency)</strong> - давность последней покупки</p>
                            <p><strong>F (Frequency)</strong> - частота покупок</p>
                            <p><strong>M (Monetary)</strong> - денежная ценность</p>
                            <p className="pt-2">• Сегменты: Champions, Loyal, At Risk, Hibernating и др.</p>
                            <p>• 5 листов: RFM данные, Сводка, Распределение, Параметры, Пояснения</p>
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

