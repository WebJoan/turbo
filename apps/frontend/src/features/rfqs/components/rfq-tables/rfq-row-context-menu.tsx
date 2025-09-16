'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { RFQ } from '@/types/rfqs';
import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuLabel,
    ContextMenuSeparator,
    ContextMenuTrigger
} from '@/components/ui/context-menu';
import { Copy, Edit, Eye, FileText, Trash, Play } from 'lucide-react';
import { toast } from 'sonner';
import { deleteRFQ } from '@/lib/rfqs';
import { useAuth } from '@/lib/use-auth';
import { updateRFQ, fetchRFQById } from '@/lib/rfqs';
import { emitRfqUpdated } from '@/features/rfqs/events';
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle
} from '@/components/ui/alert-dialog';

interface Props {
    rfq: RFQ;
    children: React.ReactElement;
}

export function RFQRowContextMenu({ rfq, children }: Props) {
    const router = useRouter();
    const [isDeleteOpen, setIsDeleteOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const { user, loading } = useAuth();
    const isPurchaser = user?.role === 'purchaser';
    const isSales = user?.role === 'sales';
    const canToggleStatus = isSales && (rfq.status === 'draft' || rfq.status === 'submitted');
    const showToggleStatus = !loading && canToggleStatus;

    const handleCopy = () => {
        navigator.clipboard.writeText(rfq.number);
        toast.success('Номер RFQ скопирован');
    };

    const handleDelete = async () => {
        try {
            setIsDeleting(true);
            await deleteRFQ(rfq.id);
            toast.success('RFQ успешно удален');
            router.refresh();
        } catch (error) {
            toast.error('Ошибка при удалении RFQ');
            console.error(error);
        } finally {
            setIsDeleting(false);
            setIsDeleteOpen(false);
        }
    };

    return (
        <>
            <ContextMenu>
                <ContextMenuTrigger asChild>
                    {children}
                </ContextMenuTrigger>
                <ContextMenuContent>
                    <ContextMenuLabel>Действия</ContextMenuLabel>
                    <ContextMenuItem onClick={handleCopy}>
                        <Copy className='mr-2 h-4 w-4' />
                        Копировать номер
                    </ContextMenuItem>
                    <ContextMenuSeparator />
                    <ContextMenuItem onClick={() => router.push(`/dashboard/rfqs/${rfq.id}`)}>
                        <Eye className='mr-2 h-4 w-4' />
                        Просмотр
                    </ContextMenuItem>
                    {!isPurchaser && (
                        <ContextMenuItem onClick={() => router.push(`/dashboard/rfqs/${rfq.id}/edit`)}>
                            <Edit className='mr-2 h-4 w-4' />
                            Редактировать
                        </ContextMenuItem>
                    )}
                    {showToggleStatus && (
                        <ContextMenuItem
                            onClick={async () => {
                                try {
                                    const nextStatus = rfq.status === 'draft' ? 'submitted' : 'draft';
                                    await updateRFQ(rfq.id, { status: nextStatus } as Partial<RFQ>);
                                    const fresh = await fetchRFQById(rfq.id);
                                    emitRfqUpdated(fresh);
                                    toast.success(nextStatus === 'submitted' ? 'RFQ отправлен' : 'Отправка отменена');
                                    router.refresh();
                                } catch (e) {
                                    toast.error('Не удалось изменить статус');
                                    console.error(e);
                                }
                            }}
                        >
                            <FileText className='mr-2 h-4 w-4' />
                            {rfq.status === 'draft' ? 'Отправить' : 'Отменить отправку'}
                        </ContextMenuItem>
                    )}
                    {!loading && isPurchaser && rfq.status === 'submitted' && (
                        <ContextMenuItem
                            onClick={async () => {
                                try {
                                    await updateRFQ(rfq.id, { status: 'in_progress' } as Partial<RFQ>);
                                    const fresh = await fetchRFQById(rfq.id);
                                    emitRfqUpdated(fresh);
                                    toast.success('Взято в работу');
                                    router.refresh();
                                } catch (e) {
                                    toast.error('Не удалось взять в работу');
                                    console.error(e);
                                }
                            }}
                        >
                            <Play className='mr-2 h-4 w-4' />
                            Взять в работу
                        </ContextMenuItem>
                    )}
                    <ContextMenuSeparator />
                    {!isPurchaser && (
                        <ContextMenuItem onClick={() => setIsDeleteOpen(true)} variant='destructive'>
                            <Trash className='mr-2 h-4 w-4' />
                            Удалить
                        </ContextMenuItem>
                    )}
                </ContextMenuContent>
            </ContextMenu>

            <AlertDialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Вы уверены?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Это действие нельзя отменить. RFQ {rfq.number} будет удален безвозвратно.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Отмена</AlertDialogCancel>
                        <AlertDialogAction onClick={handleDelete} disabled={isDeleting}>
                            {isDeleting ? 'Удаление...' : 'Удалить'}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
}


