'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useAuth } from '@/lib/auth-context'
import Link from 'next/link'

const registerSchema = z.object({
    username: z.string().min(3, 'Username должен быть не менее 3 символов'),
    password: z.string().min(6, 'Password должен быть не менее 6 символов'),
    password_retype: z.string().min(6, 'Подтвердите пароль')
}).refine((data) => data.password === data.password_retype, {
    message: "Пароли не совпадают",
    path: ["password_retype"],
})

type RegisterForm = z.infer<typeof registerSchema>

export default function RegisterPage() {
    const router = useRouter()
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const { register: registerUser } = useAuth()

    const { register, handleSubmit, formState: { errors } } = useForm<RegisterForm>({
        resolver: zodResolver(registerSchema)
    })

    const onSubmit = async (data: RegisterForm) => {
        setIsLoading(true)
        setError(null)

        try {
            await registerUser(data)
            router.replace('/')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Ошибка при регистрации')
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
            <div className="max-w-md w-full space-y-8">
                <div>
                    <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
                        Регистрация в AI Assistant
                    </h2>
                    <p className="mt-2 text-center text-sm text-gray-600">
                        Создайте новую учётную запись
                    </p>
                </div>

                {error && (
                    <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                        {error}
                    </div>
                )}

                <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
                    <div className="space-y-4">
                        <div>
                            <label htmlFor="username" className="block text-sm font-medium text-gray-700">
                                Имя пользователя
                            </label>
                            <input
                                {...register('username')}
                                type="text"
                                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                                placeholder="Введите имя пользователя"
                            />
                            {errors.username && (
                                <p className="mt-1 text-sm text-red-600">{errors.username.message}</p>
                            )}
                        </div>

                        <div>
                            <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                                Пароль
                            </label>
                            <input
                                {...register('password')}
                                type="password"
                                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                                placeholder="Введите пароль"
                            />
                            {errors.password && (
                                <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
                            )}
                        </div>

                        <div>
                            <label htmlFor="password_retype" className="block text-sm font-medium text-gray-700">
                                Подтвердите пароль
                            </label>
                            <input
                                {...register('password_retype')}
                                type="password"
                                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                                placeholder="Подтвердите пароль"
                            />
                            {errors.password_retype && (
                                <p className="mt-1 text-sm text-red-600">{errors.password_retype.message}</p>
                            )}
                        </div>
                    </div>

                    <div>
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                        >
                            {isLoading ? 'Регистрация...' : 'Зарегистрироваться'}
                        </button>
                    </div>

                    <div className="text-center">
                        <p className="text-sm text-gray-600">
                            Уже есть аккаунт?{' '}
                            <Link href="/login" className="font-medium text-indigo-600 hover:text-indigo-500">
                                Войти
                            </Link>
                        </p>
                    </div>
                </form>
            </div>
        </div>
    )
}
