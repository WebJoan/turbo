'use client';

import { RFQ } from '@/types/rfqs';
import { ItemsTable } from '../rfq-items/items-table';

interface ExpandableRowProps {
    rfq: RFQ;
}

export function ExpandableRow({ rfq }: ExpandableRowProps) {
    return (
        <div className="p-4 bg-muted/20">
            <div className="mb-4">
                <h4 className="text-sm font-semibold mb-2">Информация о запросе</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <span className="text-muted-foreground">Описание:</span>
                        <p className="mt-1">{rfq.description || 'Не указано'}</p>
                    </div>
                    <div>
                        <span className="text-muted-foreground">Заметки:</span>
                        <p className="mt-1">{rfq.notes || 'Нет заметок'}</p>
                    </div>
                    <div>
                        <span className="text-muted-foreground">Условия оплаты:</span>
                        <p className="mt-1">{rfq.payment_terms || 'Не указаны'}</p>
                    </div>
                    <div>
                        <span className="text-muted-foreground">Условия поставки:</span>
                        <p className="mt-1">{rfq.delivery_terms || 'Не указаны'}</p>
                    </div>
                    <div className="col-span-2">
                        <span className="text-muted-foreground">Адрес доставки:</span>
                        <p className="mt-1">{rfq.delivery_address || 'Не указан'}</p>
                    </div>
                </div>
            </div>

            <div>
                <h4 className="text-sm font-semibold mb-2">Позиции запроса ({rfq.items?.length || 0})</h4>
                {rfq.items && rfq.items.length > 0 ? (
                    <ItemsTable items={rfq.items} />
                ) : (
                    <div className="border rounded-lg p-4">
                        <div className="text-center text-muted-foreground">
                            Нет позиций
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
