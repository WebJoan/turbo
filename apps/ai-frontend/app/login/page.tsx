'use client'

import { signIn, getSession } from 'next-auth/react'
import { useSearchParams, useRouter } from 'next/navigation'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'

const loginSchema = z.object({
    username: z.string().min(3, 'Username должен быть не менее 3 символов'),
    password: z.string().min(6, 'Password должен быть не менее 6 символов')
})

type LoginForm = z.infer<typeof loginSchema>

export default function LoginPage() {
    const searchParams = useSearchParams()
    const router = useRouter()
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>({
        resolver: zodResolver(loginSchema)
    })

    const onSubmit = async (data: LoginForm) => {
        setIsLoading(true)
        setError(null)

        try {
            const callbackUrl = searchParams.get('callbackUrl') || '/'
            const result = await signIn('credentials', {
                username: data.username,
                password: data.password,
                redirect: false,
                callbackUrl
            })

            if (result?.error) {
                setError('Неверные учетные данные')
            } else if (result?.ok) {
                router.replace(result.url ?? callbackUrl)
            } else {
                // На случай гонки обновления сессии попробуем ещё раз получить сессию
                const session = await getSession()
                if (session) {
                    router.replace(callbackUrl)
                } else {
                    setError('Не удалось войти. Проверьте логин и пароль.')
                }
            }
        } catch (err) {
            setError('Ошибка входа в систему')
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
            <div className="max-w-md w-full space-y-8">
                <div>
                    <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
                        Вход в AI Assistant
                    </h2>
                    <p className="mt-2 text-center text-sm text-gray-600">
                        Войдите в свою учётную запись
                    </p>
                </div>

                {searchParams.get('error') === 'CredentialsSignin' && (
                    <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                        Неверные учетные данные
                    </div>
                )}

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
                    </div>

                    <div>
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                        >
                            {isLoading ? 'Вход...' : 'Войти'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}