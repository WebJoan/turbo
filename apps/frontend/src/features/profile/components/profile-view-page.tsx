"use client";
import { useAuth } from '@/lib/use-auth';

export default function ProfileViewPage() {
  const { user } = useAuth();
  return (
    <div className='flex w-full flex-col p-4'>
      <div className='space-y-2'>
        <h2 className='text-xl font-semibold'>Профиль</h2>
        <div className='text-sm'>
          <div><span className='text-muted-foreground'>Пользователь:</span> {user?.fullName || user?.username || ''}</div>
          <div><span className='text-muted-foreground'>Email:</span> {user?.email || ''}</div>
        </div>
      </div>
    </div>
  );
}
