'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { RFQ } from '@/types/rfqs';
import { Button } from '@/components/ui/button';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { MoreHorizontal, Edit, Trash, Eye, Copy, FileText } from 'lucide-react';
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
import { deleteRFQ } from '@/lib/rfqs';
import { toast } from 'sonner';

interface CellActionProps {
    data: RFQ;
}

export function CellAction({ data }: CellActionProps) {
    const router = useRouter();
    const [isDeleteOpen, setIsDeleteOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    const handleDelete = async () => {
        try {
            setIsDeleting(true);
            await deleteRFQ(data.id);
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

    const handleCopy = () => {
        navigator.clipboard.writeText(data.number);
        toast.success('Номер RFQ скопирован');
    };

    return (
        <>
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button variant="ghost" className="h-8 w-8 p-0">
                        <span className="sr-only">Открыть меню</span>
                        <MoreHorizontal className="h-4 w-4" />
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                    <DropdownMenuLabel>Действия</DropdownMenuLabel>
                    <DropdownMenuItem onClick={handleCopy}>
                        <Copy className="mr-2 h-4 w-4" />
                        Копировать номер
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => router.push(`/dashboard/rfqs/${data.id}`)}>
                        <Eye className="mr-2 h-4 w-4" />
                        Просмотр
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => router.push(`/dashboard/rfqs/${data.id}/edit`)}>
                        <Edit className="mr-2 h-4 w-4" />
                        Редактировать
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => router.push(`/dashboard/rfqs/${data.id}/quotation`)}>
                        <FileText className="mr-2 h-4 w-4" />
                        Создать предложение
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                        onClick={() => setIsDeleteOpen(true)}
                        className="text-destructive"
                    >
                        <Trash className="mr-2 h-4 w-4" />
                        Удалить
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>

            <AlertDialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Вы уверены?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Это действие нельзя отменить. RFQ {data.number} будет удален безвозвратно.
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
