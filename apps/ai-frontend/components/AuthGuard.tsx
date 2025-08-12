'use client'

import { useAuth } from '@/lib/auth-context'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

interface AuthGuardProps {
    children: React.ReactNode
}

export function AuthGuard({ children }: AuthGuardProps) {
    const { isAuthenticated, isLoading } = useAuth()
    const router = useRouter()

    useEffect(() => {
        if (!isLoading && !isAuthenticated) {
            router.replace('/login')
        }
    }, [isAuthenticated, isLoading, router])

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
            </div>
        )
    }

    if (!isAuthenticated) {
        return null // Будет произведено перенаправление
    }

    return <>{children}</>
}
