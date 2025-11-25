'use client';

import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Download, Loader2, Calendar, Filter } from 'lucide-react';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';

interface Competitor {
    id: number;
    name: string;
}

export default function ExportCompetitorSalesDialog() {
    const [open, setOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [progressMessage, setProgressMessage] = useState('');
    
    // Параметры фильтров
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [competitors, setCompetitors] = useState<Competitor[]>([]);
    const [selectedCompetitorIds, setSelectedCompetitorIds] = useState<number[]>([]);
    const [loadingCompetitors, setLoadingCompetitors] = useState(false);

    // Загружаем список конкурентов при открытии диалога
    useEffect(() => {
        if (open && competitors.length === 0) {
            loadCompetitors();
        }
    }, [open]);

    // Устанавливаем период по умолчанию (последние 30 дней)
    useEffect(() => {
        const today = new Date();
        const thirtyDaysAgo = new Date(today);
        thirtyDaysAgo.setDate(today.getDate() - 30);
        
        setDateTo(today.toISOString().split('T')[0]);
        setDateFrom(thirtyDaysAgo.toISOString().split('T')[0]);
    }, []);

    const loadCompetitors = async () => {
        setLoadingCompetitors(true);
        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${apiUrl}/api/competitors/`, {
                credentials: 'include',
            });

            if (!response.ok) {
                throw new Error('Не удалось загрузить список конкурентов');
            }

            const data = await response.json();
            setCompetitors(data.results || data);
        } catch (error) {
            console.error('Ошибка при загрузке конкурентов:', error);
            toast.error('Не удалось загрузить список конкурентов');
        } finally {
            setLoadingCompetitors(false);
        }
    };

    const toggleCompetitor = (competitorId: number) => {
        setSelectedCompetitorIds(prev => {
            if (prev.includes(competitorId)) {
                return prev.filter(id => id !== competitorId);
            } else {
                return [...prev, competitorId];
            }
        });
    };

    const toggleAllCompetitors = () => {
        if (selectedCompetitorIds.length === competitors.length) {
            setSelectedCompetitorIds([]);
        } else {
            setSelectedCompetitorIds(competitors.map(c => c.id));
        }
    };

    const checkTaskStatus = async (taskId: string, apiUrl: string): Promise<void> => {
        const maxAttempts = 60;
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

        while (attempts < maxAttempts) {
            const isComplete = await checkStatus();
            if (isComplete) {
                return;
            }
            await new Promise(resolve => setTimeout(resolve, 5000));
        }

        throw new Error('Превышено время ожидания. Попробуйте позже.');
    };

    const handleExport = async () => {
        // Валидация
        if (!dateFrom || !dateTo) {
            toast.error('Пожалуйста, укажите период');
            return;
        }

        if (new Date(dateFrom) > new Date(dateTo)) {
            toast.error('Дата начала не может быть позже даты окончания');
            return;
        }

        setIsLoading(true);
        setProgressMessage('Запуск экспорта продаж конкурентов...');

        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

            const requestBody: { 
                date_from: string; 
                date_to: string;
                competitor_ids?: number[];
            } = {
                date_from: dateFrom,
                date_to: dateTo,
            };

            // Добавляем фильтр по конкурентам только если выбраны не все
            if (selectedCompetitorIds.length > 0 && selectedCompetitorIds.length < competitors.length) {
                requestBody.competitor_ids = selectedCompetitorIds;
            }

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

            const competitorsInfo = selectedCompetitorIds.length === 0 || selectedCompetitorIds.length === competitors.length
                ? 'всех конкурентов'
                : `${selectedCompetitorIds.length} конкурент(ов)`;

            toast.info(`Экспорт продаж ${competitorsInfo} за период ${dateFrom} - ${dateTo} запущен. Ожидайте...`);
            setProgressMessage('Анализ данных о продажах...');
            setOpen(false);

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
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button
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
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Filter className="h-5 w-5" />
                        Экспорт продаж конкурентов
                    </DialogTitle>
                    <DialogDescription>
                        Настройте период и выберите конкурентов для анализа продаж
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-6 py-4">
                    {/* Период */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Calendar className="h-4 w-4 text-muted-foreground" />
                            <Label className="text-base font-semibold">Период анализа</Label>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="date-from">Дата начала</Label>
                                <Input
                                    id="date-from"
                                    type="date"
                                    value={dateFrom}
                                    onChange={(e) => setDateFrom(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="date-to">Дата окончания</Label>
                                <Input
                                    id="date-to"
                                    type="date"
                                    value={dateTo}
                                    onChange={(e) => setDateTo(e.target.value)}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Конкуренты */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Filter className="h-4 w-4 text-muted-foreground" />
                                <Label className="text-base font-semibold">Конкуренты</Label>
                            </div>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={toggleAllCompetitors}
                                disabled={loadingCompetitors}
                            >
                                {selectedCompetitorIds.length === competitors.length ? 'Снять все' : 'Выбрать все'}
                            </Button>
                        </div>

                        {loadingCompetitors ? (
                            <div className="flex items-center justify-center py-8">
                                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : competitors.length === 0 ? (
                            <div className="text-center py-8 text-muted-foreground">
                                Конкуренты не найдены
                            </div>
                        ) : (
                            <div className="border rounded-lg p-4 space-y-3 max-h-64 overflow-y-auto">
                                {competitors.map((competitor) => (
                                    <div key={competitor.id} className="flex items-center space-x-2">
                                        <Checkbox
                                            id={`competitor-${competitor.id}`}
                                            checked={selectedCompetitorIds.includes(competitor.id)}
                                            onCheckedChange={() => toggleCompetitor(competitor.id)}
                                        />
                                        <label
                                            htmlFor={`competitor-${competitor.id}`}
                                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                                        >
                                            {competitor.name}
                                        </label>
                                    </div>
                                ))}
                            </div>
                        )}
                        
                        <p className="text-xs text-muted-foreground">
                            Выбрано: {selectedCompetitorIds.length === 0 || selectedCompetitorIds.length === competitors.length
                                ? `все конкуренты (${competitors.length})`
                                : `${selectedCompetitorIds.length} из ${competitors.length}`}
                        </p>
                    </div>
                </div>

                <DialogFooter>
                    <Button
                        type="button"
                        variant="outline"
                        onClick={() => setOpen(false)}
                        disabled={isLoading}
                    >
                        Отмена
                    </Button>
                    <Button
                        type="button"
                        onClick={handleExport}
                        disabled={isLoading || !dateFrom || !dateTo}
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                Экспорт...
                            </>
                        ) : (
                            <>
                                <Download className="h-4 w-4 mr-2" />
                                Экспортировать
                            </>
                        )}
                    </Button>
                </DialogFooter>

                {isLoading && progressMessage && (
                    <div className="text-center py-2">
                        <p className="text-xs text-muted-foreground">
                            {progressMessage}
                        </p>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

