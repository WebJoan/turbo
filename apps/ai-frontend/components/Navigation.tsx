'use client'

import { useAuth } from '@/lib/auth-context'
import { useRouter } from 'next/navigation'

export function Navigation() {
    const { user, logout } = useAuth()
    const router = useRouter()

    const handleLogout = () => {
        logout()
        router.replace('/login')
    }

    if (!user) return null

    return (
        <nav className="bg-white shadow-sm border-b">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center h-16">
                    <div className="flex items-center">
                        <h1 className="text-xl font-semibold text-gray-900">AI Assistant</h1>
                    </div>

                    <div className="flex items-center space-x-4">
                        <button
                            onClick={() => router.push('/search')}
                            className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-indigo-600 bg-indigo-50 hover:bg-indigo-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                        >
                            Поиск
                        </button>
                        <span className="text-sm text-gray-500">
                            Привет, {user.username}!
                        </span>
                        <button
                            onClick={handleLogout}
                            className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                        >
                            Выйти
                        </button>
                    </div>
                </div>
            </div>
        </nav>
    )
}
