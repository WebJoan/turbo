'use client';

import { Button } from '@/components/ui/button';
import { Download, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

interface ExportCompetitorSalesButtonProps {
    dateFrom?: string;
    dateTo?: string;
}

export default function ExportCompetitorSalesButton({ 
    dateFrom, 
    dateTo 
}: ExportCompetitorSalesButtonProps = {}) {
    const [isLoading, setIsLoading] = useState(false);
    const [progressMessage, setProgressMessage] = useState('');

    const checkTaskStatus = async (taskId: string, apiUrl: string): Promise<void> => {
        const maxAttempts = 60; // Максимум 5 минут (60 * 5 секунд)
        let attempts = 0;

        const checkStatus = async (): Promise<boolean> => {
            attempts++;

            try {
                const statusResponse = await fetch(
                    `${apiUrl}/api/stock/export-competitor-sales-status/${taskId}/`,
                    {
                        method: 'GET',
                        credentials: 'include',
                    }
                );

                if (!statusResponse.ok) {
                    if (statusResponse.headers.get('content-type')?.includes('application/json')) {
                        const errorData = await statusResponse.json();
                        throw new Error(errorData.error || 'Ошибка при проверке статуса');
                    } else {
                        throw new Error(`Ошибка сервера: ${statusResponse.status}`);
                    }
                }

                const contentType = statusResponse.headers.get('content-type');

                // Если получили файл - задача завершена
                if (contentType?.includes('spreadsheetml')) {
                    const blob = await statusResponse.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;

                    const contentDisposition = statusResponse.headers.get('Content-Disposition');
                    let filename = 'competitor_sales.xlsx';
                    if (contentDisposition) {
                        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                        if (filenameMatch) {
                            filename = filenameMatch[1];
                        }
                    }

                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);

                    toast.success('Файл с продажами конкурентов успешно скачан');
                    return true;
                }

                // Если получили JSON - задача ещё выполняется
                if (contentType?.includes('application/json')) {
                    const statusData = await statusResponse.json();

                    if (statusData.status === 'failed') {
                        throw new Error(statusData.error || 'Ошибка при экспорте');
                    }

                    setProgressMessage(`Обработка... (попытка ${attempts}/${maxAttempts})`);
                    return false;
                }

                throw new Error('Неожиданный формат ответа от сервера');

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

        throw new Error('Превышено время ожидания. Попробуйте позже.');
    };

    const handleExport = async () => {
        setIsLoading(true);
        setProgressMessage('Запуск экспорта продаж конкурентов...');

        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

            // Формируем тело запроса с параметрами периода
            const requestBody: { date_from?: string; date_to?: string } = {};
            if (dateFrom) requestBody.date_from = dateFrom;
            if (dateTo) requestBody.date_to = dateTo;

            // Запускаем задачу экспорта
            const response = await fetch(`${apiUrl}/api/stock/export-competitor-sales/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify(requestBody),
            });

            if (response.status === 401 || response.status === 403) {
                toast.error('Необходима авторизация. Пожалуйста, войдите в систему.');
                return;
            }

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Ошибка сервера:', errorText);
                throw new Error(`Ошибка сервера: ${response.status}`);
            }

            const data = await response.json();
            const taskId = data.task_id;

            if (!taskId) {
                throw new Error('Не получен task_id от сервера');
            }

            const periodInfo = dateFrom && dateTo 
                ? ` за период ${dateFrom} - ${dateTo}`
                : ' за последние 30 дней';

            toast.info(`Экспорт продаж конкурентов${periodInfo} запущен. Ожидайте...`);
            setProgressMessage('Анализ данных о продажах...');

            // Отслеживаем статус задачи
            await checkTaskStatus(taskId, apiUrl);

        } catch (error) {
            console.error('Ошибка при экспорте:', error);
            toast.error(error instanceof Error ? error.message : 'Не удалось экспортировать данные');
        } finally {
            setIsLoading(false);
            setProgressMessage('');
        }
    };

    return (
        <div className="flex flex-col gap-2">
            <Button
                onClick={handleExport}
                disabled={isLoading}
                variant="default"
                className="gap-2"
            >
                {isLoading ? (
                    <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Обработка...
                    </>
                ) : (
                    <>
                        <Download className="h-4 w-4" />
                        Экспорт продаж
                    </>
                )}
            </Button>
            {isLoading && progressMessage && (
                <p className="text-xs text-muted-foreground text-center">
                    {progressMessage}
                </p>
            )}
        </div>
    );
}

