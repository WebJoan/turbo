'use client'

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { AuthService, User, AuthUser, LoginRequest, RegisterRequest } from './auth'
import { getApiClient } from './api'

interface AuthContextType {
    user: User | null
    isLoading: boolean
    isAuthenticated: boolean
    login: (credentials: LoginRequest) => Promise<void>
    register: (data: RegisterRequest) => Promise<void>
    logout: () => void
    refreshToken: () => Promise<boolean>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
    children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
    const [user, setUser] = useState<User | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    // Инициализация аутентификации при загрузке приложения
    useEffect(() => {
        const initAuth = async () => {
            if (AuthService.isAuthenticated()) {
                const userData = AuthService.getUser()
                setUser(userData)

                // Проверяем, нужно ли обновить токен
                if (AuthService.shouldRefreshToken()) {
                    const refreshed = await refreshTokenInternal()
                    if (!refreshed) {
                        // Если не удалось обновить токен, разлогиниваем
                        logoutInternal()
                    }
                }
            }
            setIsLoading(false)
        }

        const logoutInternal = (): void => {
            AuthService.clearAuth()
            setUser(null)
        }

        const refreshTokenInternal = async (): Promise<boolean> => {
            try {
                const refreshTokenValue = AuthService.getRefreshToken()
                if (!refreshTokenValue) {
                    return false
                }

                const apiClient = await getApiClient()
                const response = await apiClient.token.tokenRefreshCreate({
                    refresh: refreshTokenValue
                } as any)

                // Обновляем access токен в localStorage
                if (AuthService.isServer) return false
                localStorage.setItem('auth.access_token', response.access)
                document.cookie = `auth.access_token=${response.access}; path=/; SameSite=lax`

                return true
            } catch (error) {
                return false
            }
        }

        initAuth()
    }, [])

    const login = async (credentials: LoginRequest): Promise<void> => {
        try {
            const apiClient = await getApiClient()
            const response = await apiClient.token.tokenCreate({
                username: credentials.username,
                password: credentials.password
            } as any)

            // Декодируем токен чтобы получить user_id
            const tokenData = AuthService.decodeToken(response.access)

            const authData: AuthUser = {
                user: {
                    id: tokenData.user_id,
                    username: credentials.username
                },
                tokens: {
                    access: response.access,
                    refresh: response.refresh
                }
            }

            AuthService.saveAuth(authData)
            setUser(authData.user)
        } catch (error) {
            throw new Error('Неверные учетные данные')
        }
    }

    const register = async (data: RegisterRequest): Promise<void> => {
        try {
            const apiClient = await getApiClient()
            await apiClient.users.usersCreate({
                username: data.username,
                password: data.password,
                password_retype: data.password_retype
            } as any)

            // После успешной регистрации автоматически логинимся
            await login({
                username: data.username,
                password: data.password
            })
        } catch (error) {
            throw new Error('Ошибка при регистрации')
        }
    }

    const logout = (): void => {
        AuthService.clearAuth()
        setUser(null)
    }

    const refreshToken = async (): Promise<boolean> => {
        try {
            const refreshTokenValue = AuthService.getRefreshToken()
            if (!refreshTokenValue) {
                return false
            }

            const apiClient = await getApiClient()
            const response = await apiClient.token.tokenRefreshCreate({
                refresh: refreshTokenValue
            } as any)

            // Обновляем access токен в localStorage
            if (AuthService.isServer) return false
            localStorage.setItem('auth.access_token', response.access)

            return true
        } catch (error) {
            return false
        }
    }

    const contextValue: AuthContextType = {
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        refreshToken
    }

    return (
        <AuthContext.Provider value={contextValue}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth(): AuthContextType {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error('useAuth должен использоваться внутри AuthProvider')
    }
    return context
}
